"""
EML / MSG Parser — Extracts attachments and routes them to appropriate parsers.
Also handles HTML rate tables directly embedded in the email body (OOCL, MSC, Maersk, ANL).
Includes pure-Python Outlook .msg parsing for compound binary message files.
"""
import os
import email
import re
import datetime
from email import policy
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any
from urllib.parse import urlparse
from bs4 import BeautifulSoup

from app.core.config import UPLOADS_DIR
from app.services.parsers.base_parser import BaseParser
from app.models.canonical import CanonicalRateSheet, RateRow, ChargeItem, JobSummary
from app.services.parsers.plugins.maersk_plugin import MaerskPlugin
from app.services.parsers.plugins.one_plugin import ONEPlugin
from app.services.parsers.plugins.generic_excel_plugin import GenericExcelPlugin
from app.services.parsers.plugins.msc_plugin import MSCPlugin
from app.services.parsers.azure_doc_intel import AzureDocumentIntelligenceParser


class CompoundFileReader:
    """Pure-Python Compound File Binary Format (CFBF / OLE2) parser."""
    def __init__(self, data: bytes):
        self.data = data
        if len(data) < 512 or data[:8] != b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1':
            raise ValueError("Not a valid OLE2 / Compound Binary File")
        
        self.sector_shift = struct.unpack_from('<H', data, 30)[0]
        self.sector_size = 1 << self.sector_shift
        self.mini_sector_shift = struct.unpack_from('<H', data, 32)[0]
        self.mini_sector_size = 1 << self.mini_sector_shift
        self.dir_first_sector = struct.unpack_from('<I', data, 48)[0]
        self.mini_stream_cutoff = struct.unpack_from('<I', data, 56)[0]
        self.mini_fat_first_sector = struct.unpack_from('<I', data, 60)[0]

        difat = list(struct.unpack_from('<109I', data, 76))
        fat_sectors = [s for s in difat if s < 0xFFFFFFFD]
        self.fat = []
        for s in fat_sectors:
            offset = 512 + s * self.sector_size
            sec_data = data[offset:offset + self.sector_size]
            self.fat.extend(struct.unpack(f'<{self.sector_size // 4}I', sec_data))

        self.mini_fat = []
        mini_sec = self.mini_fat_first_sector
        while mini_sec < 0xFFFFFFFD and mini_sec < len(self.fat):
            offset = 512 + mini_sec * self.sector_size
            sec_data = data[offset:offset + self.sector_size]
            self.mini_fat.extend(struct.unpack(f'<{self.sector_size // 4}I', sec_data))
            mini_sec = self.fat[mini_sec]

        dir_data = self._read_stream(self.dir_first_sector, 0, is_mini=False)
        self.entries = []
        num_entries = len(dir_data) // 128
        for i in range(num_entries):
            e_bytes = dir_data[i * 128:(i + 1) * 128]
            name_len = struct.unpack_from('<H', e_bytes, 64)[0]
            name = e_bytes[:max(0, name_len - 2)].decode('utf-16le', errors='ignore')
            e_type = e_bytes[66]
            start_sec = struct.unpack_from('<I', e_bytes, 116)[0]
            stream_size = struct.unpack_from('<Q', e_bytes, 120)[0]
            self.entries.append({
                "id": i,
                "name": name,
                "type": e_type,
                "start": start_sec,
                "size": stream_size
            })

        self.mini_stream_data = b""
        if self.entries and self.entries[0]["size"] > 0:
            self.mini_stream_data = self._read_stream(self.entries[0]["start"], self.entries[0]["size"], is_mini=False)

    def _read_stream(self, start_sector: int, size: int, is_mini: bool = False) -> bytes:
        chunks = []
        curr = start_sector
        bytes_left = size if size > 0 else 999999999
        
        if is_mini:
            while curr < 0xFFFFFFFD and curr < len(self.mini_fat) and bytes_left > 0:
                offset = curr * self.mini_sector_size
                chunk = self.mini_stream_data[offset:offset + min(self.mini_sector_size, bytes_left)]
                chunks.append(chunk)
                bytes_left -= len(chunk)
                curr = self.mini_fat[curr]
        else:
            while curr < 0xFFFFFFFD and curr < len(self.fat) and bytes_left > 0:
                offset = 512 + curr * self.sector_size
                chunk = self.data[offset:offset + min(self.sector_size, bytes_left)]
                chunks.append(chunk)
                bytes_left -= len(chunk)
                curr = self.fat[curr]
                
        return b"".join(chunks)[:size] if size > 0 else b"".join(chunks)

    def get_stream(self, entry) -> bytes:
        is_mini = entry["size"] < self.mini_stream_cutoff and entry["type"] == 2
        return self._read_stream(entry["start"], entry["size"], is_mini=is_mini)


class EMLParser(BaseParser):
    def __init__(self):
        self.maersk_plugin = MaerskPlugin()
        self.one_plugin = ONEPlugin()
        self.generic_plugin = GenericExcelPlugin()
        self.msc_plugin = MSCPlugin()
        self.azure_parser = AzureDocumentIntelligenceParser()

    def can_parse(self, file_path: Path, filename: str) -> bool:
        fn = filename.lower()
        return fn.endswith('.eml') or fn.endswith('.msg')

    def parse(self, file_path: Path, job_id: str) -> CanonicalRateSheet:
        print(f"[EML Parser] Processing: {file_path.name} (Job: {job_id})")
        
        subject = ""
        sender = ""
        body_text = ""
        html_body = ""
        attachments_to_process: List[Tuple[str, Path]] = []

        is_msg_file = file_path.name.lower().endswith('.msg')

        if is_msg_file:
            try:
                data = file_path.read_bytes()
                cfb = CompoundFileReader(data)
                for e in cfb.entries:
                    name = e["name"]
                    if "__substg1.0_0037" in name:
                        subject = cfb.get_stream(e).decode('utf-16le' if name.endswith('001F') else 'utf-8', errors='ignore')
                    elif "__substg1.0_0C1F" in name or "__substg1.0_0042" in name:
                        sender = cfb.get_stream(e).decode('utf-16le' if name.endswith('001F') else 'utf-8', errors='ignore')
                    elif "__substg1.0_1000" in name:
                        body_text = cfb.get_stream(e).decode('utf-16le' if name.endswith('001F') else 'utf-8', errors='ignore')
                    elif "__substg1.0_1013" in name:
                        html_body = cfb.get_stream(e).decode('utf-8', errors='ignore')
            except Exception as e:
                print(f"[EML Parser] Error reading .msg file: {e}")
        else:
            with open(file_path, "rb") as f:
                msg = email.message_from_bytes(f.read(), policy=policy.default)
            subject = str(msg.get("Subject", "") or "")
            sender = str(msg.get("From", "") or "")
            
            # Extract body & attachments from MIME
            for part in msg.walk():
                content_type = part.get_content_type()
                filename = part.get_filename()
                if filename:
                    payload = part.get_payload(decode=True)
                    if payload:
                        att_path = UPLOADS_DIR / f"{job_id}_{filename}"
                        with open(att_path, "wb") as af:
                            af.write(payload)
                        attachments_to_process.append((filename, att_path))
                elif content_type == "text/html" and not html_body:
                    p = part.get_payload(decode=True)
                    if p: html_body = p.decode("utf-8", errors="ignore")
                elif content_type == "text/plain" and not body_text:
                    p = part.get_payload(decode=True)
                    if p: body_text = p.decode("utf-8", errors="ignore")

        print(f"[EML Parser] Subject: {subject}")
        print(f"[EML Parser] From: {sender}")
        for fn, ap in attachments_to_process:
            print(f"[EML Parser] Extracted attachment: {fn} ({os.path.getsize(ap)} bytes)")

        # Detect carrier from metadata
        carrier_scac = self._detect_carrier(subject, sender, file_path.name)
        contract_number = self._extract_contract_number(subject, body_text or html_body)
        validity_start, validity_end = self._extract_validity(subject, body_text or html_body)

        all_rates: List[RateRow] = []
        all_carriers: List[str] = []
        if carrier_scac:
            all_carriers.append(carrier_scac)

        # ── Phase 1: Process Excel attachments ──
        excel_attachments = [
            (fn, ap) for fn, ap in attachments_to_process
            if fn.lower().endswith(('.xlsx', '.xls', '.xlsm'))
        ]

        for att_name, att_path in excel_attachments:
            try:
                sheet = self._parse_excel_attachment(att_path, att_name, job_id, carrier_scac)
                if sheet and sheet.rates:
                    all_rates.extend(sheet.rates)
                    if sheet.carrier_code and sheet.carrier_code not in all_carriers:
                        all_carriers.append(sheet.carrier_code)
                    if sheet.contract_number and not contract_number:
                        contract_number = sheet.contract_number
                    if sheet.validity_start and not validity_start:
                        validity_start = sheet.validity_start
                        validity_end = sheet.validity_end
                    print(f"[EML Parser] Excel '{att_name}': {len(sheet.rates)} rate rows")
            except Exception as e:
                print(f"[EML Parser] Error parsing Excel attachment '{att_name}': {e}")

        # ── Phase 2: If no Excel rates, parse HTML / Text Body (e.g. OOCL, MSC, direct email quotes) ──
        if not all_rates:
            content_to_parse = html_body or body_text
            if content_to_parse:
                generic_rates = self._parse_generic_html_tables(content_to_parse, carrier_scac or "UNKN", contract_number, validity_start, validity_end)
                if generic_rates:
                    all_rates.extend(generic_rates)
                    print(f"[EML Parser] Generic HTML Table: {len(generic_rates)} rate rows")
                else:
                    sheet = self.msc_plugin.parse_text(content_to_parse, file_path.name, job_id)
                    if sheet and sheet.rates:
                        if carrier_scac:
                            sheet.carrier_code = carrier_scac
                            for r in sheet.rates: r.carrier_scac = carrier_scac
                        all_rates.extend(sheet.rates)
                        if sheet.carrier_code and sheet.carrier_code not in all_carriers:
                            all_carriers.append(sheet.carrier_code)
                        print(f"[EML Parser] MSC Plugin: {len(sheet.rates)} rate rows")

        # ── Phase 3: Process PDF & Large Image rate attachments (if no Excel or HTML rates) ──
        if not all_rates:
            doc_attachments = [
                (fn, ap) for fn, ap in attachments_to_process
                if fn.lower().endswith('.pdf') or (fn.lower().endswith(('.png', '.jpg', '.jpeg')) and os.path.getsize(ap) > 40000)
            ]
            for att_name, att_path in doc_attachments:
                try:
                    sheet = self.azure_parser.parse(att_path, job_id)
                    if sheet and sheet.rates:
                        all_rates.extend(sheet.rates)
                        if sheet.carrier_code and sheet.carrier_code not in all_carriers:
                            all_carriers.append(sheet.carrier_code)
                        print(f"[EML Parser] Visual Doc '{att_name}': {len(sheet.rates)} rate rows")
                except Exception as e:
                    print(f"[EML Parser] Error parsing visual attachment '{att_name}': {e}")

        # ── Phase 4: Check for Download Links if still no rates ──
        if not all_rates and (body_text or html_body):
            link_rates = self._try_download_link(body_text or html_body, job_id, carrier_scac, file_path.name)
            if link_rates:
                all_rates.extend(link_rates)
                print(f"[EML Parser] Downloaded link file: {len(link_rates)} rate rows")

        # ── Phase 5: Autonomous AI Extractor (GPT-4o) Fallback ──
        if not all_rates and (body_text or html_body):
            print(f"[EML Parser] Activating Autonomous AI Extraction for email body...")
            try:
                from app.services.ai_column_mapper import AIColumnMapper
                ai_mapper = AIColumnMapper.get_instance()
                full_email_text = f"Subject: {subject}\nFrom: {sender}\n\n{body_text or html_body}"
                ai_sheet = ai_mapper.extract_rates_from_raw_text(full_email_text, file_path.name, job_id)
                if ai_sheet and ai_sheet.rates:
                    all_rates.extend(ai_sheet.rates)
                    if ai_sheet.carrier_code and ai_sheet.carrier_code not in all_carriers:
                        all_carriers.append(ai_sheet.carrier_code)
                    if ai_sheet.contract_number and not contract_number:
                        contract_number = ai_sheet.contract_number
                    if ai_sheet.validity_start and not validity_start:
                        validity_start = ai_sheet.validity_start
                        validity_end = ai_sheet.validity_end
                    print(f"[EML Parser] Autonomous AI Extractor: {len(ai_sheet.rates)} rate rows")
            except Exception as e:
                print(f"[EML Parser] AI Fallback error: {e}")

        final_carrier = carrier_scac or (all_carriers[0] if all_carriers else "UNKN")
        summary = JobSummary(
            total_rows=len(all_rates),
            carriers_found=all_carriers if all_carriers else [final_carrier],
        )

        return CanonicalRateSheet(
            job_id=job_id,
            file_name=file_path.name,
            carrier_code=final_carrier,
            contract_number=contract_number,
            validity_start=validity_start,
            validity_end=validity_end,
            rates=all_rates,
            summary=summary,
        )

    def _parse_generic_html_tables(self, html_content: str, default_carrier: str, contract_no: str, v_start: str, v_end: str) -> List[RateRow]:
        """Extract rate rows from any carrier's HTML email table (e.g. OOCL Fremantle to Rijeka)."""
        soup = BeautifulSoup(html_content, "html.parser")
        tables = soup.find_all("table")
        extracted_rates: List[RateRow] = []
        row_counter = 1

        for tbl in tables:
            rows = tbl.find_all("tr")
            if len(rows) < 2:
                continue
            
            hdr_idx = None
            col_map: Dict[str, int] = {}
            containers: List[Tuple[int, str]] = []
            
            for r_idx, r in enumerate(rows[:4]):
                cells = [c.get_text(" ", strip=True) for c in r.find_all(["td", "th"])]
                if not cells:
                    continue
                
                c_map = {}
                c_containers = []
                for c_i, text in enumerate(cells):
                    t_low = text.lower().strip()
                    if any(w in t_low for w in ["origin", "pol", "from", "port of loading", "receipt"]):
                        c_map["origin"] = c_i
                    elif any(w in t_low for w in ["destination", "pod", "to", "port of discharge", "delivery"]):
                        c_map["destination"] = c_i
                    elif any(w in t_low for w in ["transshipment", "ts port", "via", "routing"]):
                        c_map["transshipment"] = c_i
                    elif any(w in t_low for w in ["currency", "curr", "ccy"]):
                        c_map["currency"] = c_i
                    elif any(w in t_low for w in ["inclusive", "inclusions", "subject to", "surcharges"]):
                        c_map["inclusions"] = c_i
                    elif any(w in t_low for w in ["transit", "tt", "days"]):
                        c_map["transit_time"] = c_i
                    
                    if "40'ot" in t_low or "40ot" in t_low or "40'oq" in t_low or "40oq" in t_low:
                        c_containers.append((c_i, "40OT"))
                    elif "20'ot" in t_low or "20ot" in t_low:
                        c_containers.append((c_i, "20OT"))
                    elif "20'fr" in t_low or "20fr" in t_low:
                        c_containers.append((c_i, "20FR"))
                    elif "40'fr" in t_low or "40fr" in t_low:
                        c_containers.append((c_i, "40FR"))
                    elif "40hc" in t_low or "40'hc" in t_low or "40hq" in t_low or "40'hq" in t_low:
                        c_containers.append((c_i, "40HC"))
                    elif "40gp" in t_low or "40'gp" in t_low or "40ft" in t_low or "40'" in t_low:
                        c_containers.append((c_i, "40GP"))
                    elif "20gp" in t_low or "20'gp" in t_low or "20ft" in t_low or "20'" in t_low:
                        c_containers.append((c_i, "20GP"))
                    elif "rate" in t_low or "ofr" in t_low or "amount" in t_low:
                        c_containers.append((c_i, "20GP"))

                if "origin" in c_map and "destination" in c_map and c_containers:
                    hdr_idx = r_idx
                    col_map = c_map
                    containers = c_containers
                    break

            if hdr_idx is None:
                continue

            for r in rows[hdr_idx + 1:]:
                cells = [c.get_text(" ", strip=True) for c in r.find_all(["td", "th"])]
                if len(cells) <= max(col_map.get("origin", 0), col_map.get("destination", 0)):
                    continue

                orig = cells[col_map["origin"]] if "origin" in col_map and col_map["origin"] < len(cells) else ""
                dest = cells[col_map["destination"]] if "destination" in col_map and col_map["destination"] < len(cells) else ""
                curr = cells[col_map["currency"]] if "currency" in col_map and col_map["currency"] < len(cells) else "USD"
                incl = cells[col_map["inclusions"]] if "inclusions" in col_map and col_map["inclusions"] < len(cells) else ""
                ts = cells[col_map["transshipment"]] if "transshipment" in col_map and col_map["transshipment"] < len(cells) else ""
                tt = cells[col_map["transit_time"]] if "transit_time" in col_map and col_map["transit_time"] < len(cells) else ""

                if not orig or not dest:
                    continue

                for col_i, eq_type in containers:
                    if col_i < len(cells):
                        raw_amt = cells[col_i]
                        digits = re.findall(r'\d+\.?\d*', raw_amt.replace(',', ''))
                        if digits:
                            amt = float(digits[0])
                            if amt > 0:
                                rate_row = RateRow(
                                    row_index=row_counter,
                                    carrier_scac=default_carrier.upper(),
                                    origin_raw=orig,
                                    origin_locode=orig,
                                    destination_raw=dest,
                                    destination_locode=dest,
                                    service_type="CY/CY",
                                    cargo_type="FAK",
                                    load_type=eq_type,
                                    commodity="FAK",
                                    ofr_amount=amt,
                                    ofr_currency=curr if len(curr) == 3 else "USD",
                                    charges=[ChargeItem(charge_code="BAS", charge_name="Base Ocean Freight", amount=amt, currency=curr if len(curr) == 3 else "USD", basis="per equipment")],
                                    validity_start=v_start,
                                    validity_end=v_end,
                                    contract_number=contract_no,
                                    inclusions=incl,
                                    remarks=f"Via {ts}" if ts else tt,
                                    internal_remarks=f"Transshipment: {ts}" if ts else ""
                                )
                                extracted_rates.append(rate_row)
                                row_counter += 1

        return extracted_rates

    def _parse_excel_attachment(self, att_path: Path, att_name: str, job_id: str, email_carrier: str) -> Optional[CanonicalRateSheet]:
        sheet = None
        if self.maersk_plugin.can_parse(att_path, att_name):
            sheet = self.maersk_plugin.parse(att_path, job_id)
        elif self.one_plugin.can_parse(att_path, att_name):
            sheet = self.one_plugin.parse(att_path, job_id)

        if not sheet or not sheet.rates:
            sheet = self.generic_plugin.parse(att_path, job_id)

        if sheet and email_carrier and sheet.carrier_code in ("UNKN", ""):
            sheet.carrier_code = email_carrier
            for r in sheet.rates:
                if r.carrier_scac in ("UNKN", ""):
                    r.carrier_scac = email_carrier
        return sheet

    def _detect_carrier(self, subject: str, sender: str, filename: str) -> str:
        combined = f"{subject} {sender} {filename}".lower()
        if "oocl" in combined: return "OOLU"
        if "maeu" in combined or "maersk" in combined or "o3e" in combined or "o3w" in combined: return "MAEU"
        if "anl" in combined or "autnb" in combined: return "ANNU"
        if "msc" in combined: return "MSCU"
        if "one" in combined or "ocean network" in combined: return "ONEY"
        if "cosco" in combined: return "COSU"
        if "hapag" in combined or "hlcu" in combined: return "HLCU"
        if "cma" in combined: return "CMDU"
        return ""

    def _extract_contract_number(self, subject: str, body: str) -> str:
        combined = f"{subject}\n{body}"
        m = re.search(r'\b(?:contract|agreement|service\s*contract|sc)\s*(?:no|number|#)?[:\s]+([A-Za-z0-9\-_/]{4,})', combined, re.IGNORECASE)
        if m:
            c = m.group(1).strip()
            if c.lower() not in ("harge", "rate", "ofr", "summary", "standard", "number", "notes", "hedules", "schedules", "details"):
                return c
        return ""

    def _extract_validity(self, subject: str, body: str) -> Tuple[str, str]:
        combined = f"{subject}\n{body}"
        m = re.search(r'(?:validity|effective)?[:\s]*(\d{1,2}\s+[a-zA-Z]{3,9}(?:\s+\d{4})?|\d{1,2}[\-/][a-zA-Z]{3,9}[\-/]\d{2,4}|\d{4}[\-/]\d{1,2}[\-/]\d{1,2})\s*(?:to|\-|\~)\s*(\d{1,2}\s+[a-zA-Z]{3,9}(?:\s+\d{4})?|\d{1,2}[\-/][a-zA-Z]{3,9}[\-/]\d{2,4}|\d{4}[\-/]\d{1,2}[\-/]\d{1,2})', combined, re.IGNORECASE)
        if m:
            s_raw = m.group(1).strip()
            e_raw = m.group(2).strip()
            return s_raw, e_raw
        return "", ""

    def _try_download_link(self, body_text: str, job_id: str, carrier_scac: str, original_filename: str) -> List[RateRow]:
        return []
