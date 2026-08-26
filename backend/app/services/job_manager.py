import re
import uuid
import time
import asyncio
import concurrent.futures
from typing import Optional, List, Dict
from pathlib import Path
import pandas as pd
from app.core.database import DatabaseManager
from app.core.master_data import MasterDataEngine
from app.services.storage import StorageService
from app.services.parsers.eml_parser import EMLParser
from app.services.parsers.plugins.maersk_plugin import MaerskPlugin
from app.services.parsers.plugins.one_plugin import ONEPlugin
from app.services.parsers.plugins.msc_plugin import MSCPlugin
from app.services.parsers.plugins.generic_excel_plugin import GenericExcelPlugin
from app.services.validators import RateValidationEngine
from app.services.exporter import FreightifyExporter
from app.models.canonical import CanonicalRateSheet, JobSummary

from app.services.parsers.azure_doc_intel import AzureDocumentIntelligenceParser
from app.services.ai_column_mapper import AIColumnMapper

class JobManager:
    _instance = None
    _executor = concurrent.futures.ThreadPoolExecutor(max_workers=2, thread_name_prefix="rate_worker")

    def __init__(self):
        self.db = DatabaseManager.get_instance()
        self.eml_parser = EMLParser()
        self.maersk_plugin = MaerskPlugin()
        self.one_plugin = ONEPlugin()
        self.msc_plugin = MSCPlugin()
        self.generic_excel_plugin = GenericExcelPlugin()
        self.azure_parser = AzureDocumentIntelligenceParser()
        self.validator = RateValidationEngine()
        self.exporter = FreightifyExporter()

    @classmethod
    def get_instance(cls) -> "JobManager":
        if cls._instance is None:
            cls._instance = JobManager()
        return cls._instance

    def submit_job(self, file_bytes: bytes, filename: str, export_policy: str = "PARTIAL", notes: Optional[str] = None) -> str:
        job_id = f"job_{int(time.time())}_{uuid.uuid4().hex[:4]}"
        file_path = StorageService.save_upload(file_bytes, f"{job_id}_{filename}")
        
        self.db.create_job(job_id, filename, len(file_bytes), export_policy)
        
        # Offload pipeline completely to background thread pool so FastAPI/Uvicorn event loop is NEVER blocked
        self._executor.submit(self._run_pipeline_sync, job_id, file_path, filename, export_policy, notes)

        return job_id

    def _run_pipeline_sync(self, job_id: str, file_path: Path, original_filename: str, export_policy: str, notes: Optional[str] = None):
        start_time = time.time()
        try:
            # 1. PARSING PHASE
            self.db.update_job_status(job_id, "PARSING", progress=15, log_msg="Starting rate sheet parsing & extraction...")

            # Fresh parser instances per job execution
            eml_parser = EMLParser()
            maersk_plugin = MaerskPlugin()
            one_plugin = ONEPlugin()
            generic_excel_plugin = GenericExcelPlugin()
            azure_parser = AzureDocumentIntelligenceParser()

            sheet: Optional[CanonicalRateSheet] = None
            fn = original_filename.lower()

            # ── Route to appropriate parser ──
            if fn.endswith(".eml") or fn.endswith(".msg"):
                self.db.update_job_status(job_id, "PARSING", progress=20, log_msg="Parsing email: extracting all attachments...")
                sheet = eml_parser.parse(file_path, job_id)

            elif azure_parser.can_parse(file_path, original_filename):
                self.db.update_job_status(job_id, "PARSING", progress=25, log_msg="Invoking Microsoft Azure Document Intelligence layout OCR model...")
                sheet = azure_parser.parse(file_path, job_id)

            elif fn.endswith(".xlsx") or fn.endswith(".xls") or fn.endswith(".xlsm"):
                if fn.endswith(".xls"):
                    self.db.update_job_status(job_id, "PARSING", progress=22, log_msg="Converting legacy .xls format to .xlsx...")
                    try:
                        dfs = pd.read_excel(file_path, sheet_name=None, engine='xlrd')
                        new_path = file_path.with_suffix(".xlsx")
                        with pd.ExcelWriter(new_path, engine='openpyxl') as writer:
                            for sheet_name, df in dfs.items():
                                df.to_excel(writer, sheet_name=sheet_name, index=False)
                        file_path = new_path
                        original_filename = original_filename + "x"
                    except Exception as e:
                        self.db.update_job_status(job_id, "PARSING", progress=22, log_msg=f"Warning: Failed to convert .xls: {e}")

                if maersk_plugin.can_parse(file_path, original_filename):
                    self.db.update_job_status(job_id, "PARSING", progress=25, log_msg="Detected Maersk rate card format, using BAS+Surcharges parser...")
                    sheet = maersk_plugin.parse(file_path, job_id)
                elif one_plugin.can_parse(file_path, original_filename):
                    self.db.update_job_status(job_id, "PARSING", progress=25, log_msg="Detected ONE rate card format...")
                    sheet = one_plugin.parse(file_path, job_id)
                else:
                    self.db.update_job_status(job_id, "PARSING", progress=25, log_msg="Using intelligent generic Excel parser with auto-header detection...")
                    sheet = generic_excel_plugin.parse(file_path, job_id)

            else:
                # Unknown format — try generic Excel as last resort
                self.db.update_job_status(job_id, "PARSING", progress=25, log_msg="Unknown file format, attempting generic parse...")
                try:
                    sheet = self.generic_excel_plugin.parse(file_path, job_id)
                except Exception:
                    sheet = CanonicalRateSheet(
                        job_id=job_id,
                        file_name=original_filename,
                        rates=[],
                        summary=JobSummary(total_rows=0)
                    )

            # If deterministic parser found no rates or sheet is empty, trigger Autonomous AI Extraction (GPT-4o)
            if sheet is None or len(sheet.rates) == 0:
                self.db.update_job_status(job_id, "PARSING", progress=30, log_msg="Standard table parser found 0 rows — activating Autonomous AI Extractor (GPT-4o Multimodal/Text)...")
                try:
                    raw_text = ""
                    with open(file_path, "rb") as f:
                        raw_bytes = f.read()
                    raw_text = raw_bytes.decode("utf-8", errors="ignore")

                    ai_mapper = AIColumnMapper.get_instance()
                    ai_sheet = ai_mapper.extract_rates_from_raw_text(raw_text, original_filename, job_id, notes=notes)
                    if ai_sheet and len(ai_sheet.rates) > 0:
                        sheet = ai_sheet
                        self.db.update_job_status(job_id, "PARSING", progress=35, log_msg=f"Autonomous AI Extractor successfully extracted {len(sheet.rates)} rates!")
                except Exception as ai_err:
                    print(f"[AI Ingestion] AI fallback error: {ai_err}")

            if sheet is None:
                sheet = CanonicalRateSheet(job_id=job_id, file_name=original_filename, rates=[], summary=JobSummary(total_rows=0))

            self.db.update_job_status(job_id, "NORMALIZING", progress=40, log_msg=f"Extracted {len(sheet.rates)} rate rows into Canonical JSON format.")

            # Enrich from supplementary notes if provided
            if notes and notes.strip():
                self.db.update_job_status(job_id, "NORMALIZING", progress=45, log_msg="Enriching rate card with supplementary email / contract notes...")
                c_match = re.search(r'\b(?:contract|agreement|service\s*contract|sc)\s*(?:no|number|#)?[:\s]+([A-Za-z0-9\-_/]{4,})', notes, re.IGNORECASE)
                if c_match and not sheet.contract_number:
                    sheet.contract_number = c_match.group(1).strip()
                v_match = re.search(r'(?:validity|effective)?[:\s]*(\d{1,2}\s+[a-zA-Z]{3,9}(?:\s+\d{4})?|\d{1,2}[\-/][a-zA-Z]{3,9}[\-/]\d{2,4}|\d{4}[\-/]\d{1,2}[\-/]\d{1,2})\s*(?:to|\-|\~)\s*(\d{1,2}\s+[a-zA-Z]{3,9}(?:\s+\d{4})?|\d{1,2}[\-/][a-zA-Z]{3,9}[\-/]\d{2,4}|\d{4}[\-/]\d{1,2}[\-/]\d{1,2})', notes, re.IGNORECASE)
                if v_match and not sheet.validity_start:
                    sheet.validity_start = v_match.group(1).strip()
                    sheet.validity_end = v_match.group(2).strip()
                for r in sheet.rates:
                    if not r.contract_number and sheet.contract_number:
                        r.contract_number = sheet.contract_number
                    if not r.validity_start and sheet.validity_start:
                        r.validity_start = sheet.validity_start
                    if not r.validity_end and sheet.validity_end:
                        r.validity_end = sheet.validity_end

            # 2. DESTINATION GROUP EXPANSION
            pre_expansion_count = len(sheet.rates)
            sheet.rates = self.validator.expand_destination_groups(sheet.rates)
            if len(sheet.rates) != pre_expansion_count:
                self.db.update_job_status(
                    job_id, "NORMALIZING", progress=50,
                    log_msg=f"Expanded {pre_expansion_count} rows to {len(sheet.rates)} rows (destination group expansion)"
                )

            # 3. FILTER JUNK ROWS
            pre_filter_count = len(sheet.rates)
            sheet.rates = [r for r in sheet.rates if not self.validator.is_junk_row(r)]
            junk_removed = pre_filter_count - len(sheet.rates)
            if junk_removed > 0:
                self.db.update_job_status(
                    job_id, "NORMALIZING", progress=55,
                    log_msg=f"Filtered {junk_removed} non-rate rows (headers, notes, comments)"
                )

            # 4. VALIDATION PHASE
            self.db.update_job_status(job_id, "VALIDATING", progress=60, log_msg="Running Master Data Validation Engine against 13,670 UNLOCODEs & SCAC codes...")
            
            valid_cnt = 0
            warn_cnt = 0
            err_cnt = 0
            crit_cnt = 0

            for idx, r in enumerate(sheet.rates):
                validated_row = self.validator.validate_row(r)
                sheet.rates[idx] = validated_row

                if validated_row.validation_status == "VALID": valid_cnt += 1
                elif validated_row.validation_status == "WARNING": warn_cnt += 1
                elif validated_row.validation_status == "ERROR": err_cnt += 1
                elif validated_row.validation_status == "CRITICAL": crit_cnt += 1

            if warn_cnt > 0 or err_cnt > 0 or crit_cnt > 0:
                # 5a. AI PORT RESOLUTION
                self.db.update_job_status(job_id, "VALIDATING", progress=65, log_msg=f"AI resolving {warn_cnt} unmatched port names via GPT-4o...")
                ai_mapper = AIColumnMapper.get_instance()
                sheet.rates = ai_mapper.resolve_ports_with_ai(sheet.rates, sheet.carrier_code)

                # Recount after AI resolution
                valid_cnt = sum(1 for r in sheet.rates if r.validation_status == "VALID")
                warn_cnt = sum(1 for r in sheet.rates if r.validation_status == "WARNING")
                err_cnt = sum(1 for r in sheet.rates if r.validation_status == "ERROR")
                crit_cnt = sum(1 for r in sheet.rates if r.validation_status == "CRITICAL")

                self.db.update_job_status(job_id, "VALIDATING", progress=72, log_msg=f"Post-AI: {valid_cnt} Valid, {warn_cnt} Warnings, {err_cnt} Errors")

                # 5b. AI REASONING
                if warn_cnt > 0 or err_cnt > 0 or crit_cnt > 0:
                    self.db.update_job_status(job_id, "VALIDATING", progress=75, log_msg="Running AI-powered validation reasoning (GPT-4o)...")
                    sheet.rates = ai_mapper.validate_with_reasoning(sheet.rates, sheet.carrier_code)

            proc_time_ms = round((time.time() - start_time) * 1000, 2)
            c_num = sheet.contract_number or (sheet.rates[0].contract_number if sheet.rates else "")
            v_s = sheet.validity_start or (sheet.rates[0].validity_start if sheet.rates else "")
            v_e = sheet.validity_end or (sheet.rates[0].validity_end if sheet.rates else "")

            sheet.contract_number = c_num
            sheet.validity_start = v_s
            sheet.validity_end = v_e

            sheet.summary = JobSummary(
                total_rows=len(sheet.rates),
                valid_rows=valid_cnt,
                warning_rows=warn_cnt,
                error_rows=err_cnt,
                critical_rows=crit_cnt,
                carriers_found=[sheet.carrier_code] if sheet.carrier_code else ["UNKN"],
                contract_number=c_num,
                validity_start=v_s,
                validity_end=v_e,
                processing_time_ms=proc_time_ms
            )

            # 4. SELF-LEARNING
            md = MasterDataEngine.get_instance()
            md.save_if_dirty()

            # Determine next job status
            if len(sheet.rates) == 0:
                next_status = "FAILED"
                self.db.update_job_status(
                    job_id,
                    next_status,
                    progress=100,
                    log_msg=f"No rate rows could be extracted from {original_filename}.",
                    canonical_sheet=sheet
                )
            else:
                next_status = "NEEDS_REVIEW" if (err_cnt > 0 or crit_cnt > 0) else "APPROVED"
                
                self.db.update_job_status(
                    job_id, 
                    next_status, 
                    progress=80, 
                    log_msg=f"Validation completed in {proc_time_ms}ms: {valid_cnt} Valid, {warn_cnt} Warnings, {err_cnt} Errors, {crit_cnt} Critical.",
                    canonical_sheet=sheet
                )

                # Pre-generate export for instant download
                self._generate_export_sync(job_id, export_policy)

                if next_status == "APPROVED":
                    self.db.update_job_status(job_id, "COMPLETED", progress=100,
                        log_msg="Auto-approved — Freightify workbook ready for download.")

        except Exception as e:
            print(f"Error processing job {job_id}: {e}")
            import traceback
            traceback.print_exc()
            self.db.update_job_status(job_id, "FAILED", progress=0, log_msg=f"Pipeline Error: {str(e)}")

    def _generate_export_sync(self, job_id: str, export_policy: str = "PARTIAL") -> str:
        try:
            job = self.db.get_job(job_id)
            if not job or not job.get("canonical"):
                return ""

            canonical_data = job["canonical"]
            sheet = CanonicalRateSheet(**canonical_data)
            output_filename = f"Freightify_Upload_{job_id}.xlsm"

            self.exporter.export(sheet, output_filename, export_policy)
            StorageService.upload_output_to_blob(output_filename)

            current_status = job.get("status", "COMPLETED")
            self.db.update_job_status(
                job_id,
                current_status,
                log_msg=f"Generated Freightify Upload Workbook: {output_filename}",
                output_file=output_filename
            )
            return output_filename
        except Exception as e:
            print(f"[Export Error] {e}")
            return ""

    async def generate_export(self, job_id: str, export_policy: str = "PARTIAL") -> str:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self._executor, self._generate_export_sync, job_id, export_policy)

