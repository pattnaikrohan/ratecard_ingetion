import uuid
import time
import asyncio
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

    def submit_job(self, file_bytes: bytes, filename: str, export_policy: str = "PARTIAL") -> str:
        job_id = f"job_{int(time.time())}_{uuid.uuid4().hex[:4]}"
        file_path = StorageService.save_upload(file_bytes, f"{job_id}_{filename}")
        
        self.db.create_job(job_id, filename, len(file_bytes), export_policy)
        
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._process_pipeline(job_id, file_path, filename, export_policy))
        except RuntimeError:
            asyncio.run(self._process_pipeline(job_id, file_path, filename, export_policy))

        return job_id

    async def _process_pipeline(self, job_id: str, file_path: Path, original_filename: str, export_policy: str):
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

            sheet: CanonicalRateSheet = None
            fn = original_filename.lower()

            # ── Route to appropriate parser ──
            if fn.endswith(".eml") or fn.endswith(".msg"):
                self.db.update_job_status(job_id, "PARSING", progress=20, log_msg="Parsing email: extracting all attachments...")
                sheet = await asyncio.to_thread(eml_parser.parse, file_path, job_id)

            elif azure_parser.can_parse(file_path, original_filename):
                self.db.update_job_status(job_id, "PARSING", progress=25, log_msg="Invoking Microsoft Azure Document Intelligence layout OCR model...")
                sheet = await asyncio.to_thread(azure_parser.parse, file_path, job_id)

            elif fn.endswith(".xlsx") or fn.endswith(".xls") or fn.endswith(".xlsm"):
                if fn.endswith(".xls"):
                    self.db.update_job_status(job_id, "PARSING", progress=22, log_msg="Converting legacy .xls format to .xlsx...")
                    try:
                        def convert_xls():
                            dfs = pd.read_excel(file_path, sheet_name=None, engine='xlrd')
                            new_path = file_path.with_suffix(".xlsx")
                            with pd.ExcelWriter(new_path, engine='openpyxl') as writer:
                                for sheet_name, df in dfs.items():
                                    df.to_excel(writer, sheet_name=sheet_name, index=False)
                            return new_path
                        file_path = await asyncio.to_thread(convert_xls)
                        original_filename = original_filename + "x"
                    except Exception as e:
                        self.db.update_job_status(job_id, "PARSING", progress=22, log_msg=f"Warning: Failed to convert .xls: {e}")

                if maersk_plugin.can_parse(file_path, original_filename):
                    self.db.update_job_status(job_id, "PARSING", progress=25, log_msg="Detected Maersk rate card format, using BAS+Surcharges parser...")
                    sheet = await asyncio.to_thread(maersk_plugin.parse, file_path, job_id)
                elif one_plugin.can_parse(file_path, original_filename):
                    self.db.update_job_status(job_id, "PARSING", progress=25, log_msg="Detected ONE rate card format...")
                    sheet = await asyncio.to_thread(one_plugin.parse, file_path, job_id)
                else:
                    self.db.update_job_status(job_id, "PARSING", progress=25, log_msg="Using intelligent generic Excel parser with auto-header detection...")
                    sheet = await asyncio.to_thread(generic_excel_plugin.parse, file_path, job_id)

            else:
                # Unknown format — try generic Excel as last resort
                self.db.update_job_status(job_id, "PARSING", progress=25, log_msg="Unknown file format, attempting generic parse...")
                try:
                    sheet = await asyncio.to_thread(self.generic_excel_plugin.parse, file_path, job_id)
                except Exception:
                    sheet = CanonicalRateSheet(
                        job_id=job_id,
                        file_name=original_filename,
                        rates=[],
                        summary=JobSummary(total_rows=0)
                    )

            self.db.update_job_status(job_id, "NORMALIZING", progress=40, log_msg=f"Extracted {len(sheet.rates)} rate rows into Canonical JSON format.")

            # 2. DESTINATION GROUP EXPANSION
            # Expand "AUS MAIN PORTS", "AUBP" etc. into individual port rows BEFORE validation
            pre_expansion_count = len(sheet.rates)
            sheet.rates = self.validator.expand_destination_groups(sheet.rates)
            if len(sheet.rates) != pre_expansion_count:
                self.db.update_job_status(
                    job_id, "NORMALIZING", progress=50,
                    log_msg=f"Expanded {pre_expansion_count} rows to {len(sheet.rates)} rows (destination group expansion)"
                )

            # 3. FILTER JUNK ROWS (headers, notes, comments parsed as data)
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
                self.db.update_job_status(job_id, "VALIDATING", progress=70, log_msg="Running AI-powered validation reasoning (GPT-4o)...")
                ai_mapper = AIColumnMapper.get_instance()
                sheet.rates = await asyncio.to_thread(ai_mapper.validate_with_reasoning, sheet.rates, sheet.carrier_code)

            proc_time_ms = round((time.time() - start_time) * 1000, 2)
            sheet.summary = JobSummary(
                total_rows=len(sheet.rates),
                valid_rows=valid_cnt,
                warning_rows=warn_cnt,
                error_rows=err_cnt,
                critical_rows=crit_cnt,
                carriers_found=[sheet.carrier_code] if sheet.carrier_code else ["UNKN"],
                processing_time_ms=proc_time_ms
            )

            # 4. SELF-LEARNING: Persist any new port/carrier synonyms learned during this job
            md = MasterDataEngine.get_instance()
            md.save_if_dirty()

            # Determine next job status
            # WARNING-only rows are now considered "good enough" — only ERROR/CRITICAL block approval
            if len(sheet.rates) == 0:
                next_status = "FAILED"
                self.db.update_job_status(
                    job_id,
                    next_status,
                    progress=100,
                    log_msg=f"No rate rows could be extracted from {original_filename}. The file format may not be supported or the document contains no recognizable rate tables.",
                    canonical_sheet=sheet
                )
            else:
                # APPROVED if no errors/critical, NEEDS_REVIEW if there are errors
                next_status = "NEEDS_REVIEW" if (err_cnt > 0 or crit_cnt > 0) else "APPROVED"
                
                self.db.update_job_status(
                    job_id, 
                    next_status, 
                    progress=80, 
                    log_msg=f"Validation completed in {proc_time_ms}ms: {valid_cnt} Valid, {warn_cnt} Warnings, {err_cnt} Errors, {crit_cnt} Critical.",
                    canonical_sheet=sheet
                )

                # If approved, trigger export
                if next_status == "APPROVED":
                    await self.generate_export(job_id, export_policy)

        except Exception as e:
            print(f"Error processing job {job_id}: {e}")
            import traceback
            traceback.print_exc()
            self.db.update_job_status(job_id, "FAILED", progress=0, log_msg=f"Pipeline Error: {str(e)}")

    async def generate_export(self, job_id: str, export_policy: str = "PARTIAL") -> str:
        job = self.db.get_job(job_id)
        if not job or not job.get("canonical"):
            raise ValueError("Job not found or canonical data missing")

        self.db.update_job_status(job_id, "GENERATING", progress=90, log_msg="Generating Freightify Upload Workbook (.xlsm)...")
        
        canonical_data = job["canonical"]
        sheet = CanonicalRateSheet(**canonical_data)
        output_filename = f"Freightify_Upload_{job_id}.xlsm"

        await asyncio.to_thread(self.exporter.export, sheet, output_filename, export_policy)

        self.db.update_job_status(
            job_id, 
            "COMPLETED", 
            progress=100, 
            log_msg=f"Successfully generated Freightify Upload Workbook: {output_filename}",
            output_file=output_filename
        )
        return output_filename
