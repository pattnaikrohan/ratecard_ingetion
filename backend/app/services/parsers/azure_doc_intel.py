"""
Azure Document Intelligence Parser
Extracts structured rate tables from PDF and image files using the Azure prebuilt-layout model.
Supports multi-table documents with intelligent column header detection.
"""
import os
import re
import json
import time
import requests
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from app.services.parsers.base_parser import BaseParser
from app.core.config import AZURE_DOC_INTEL_ENDPOINT, AZURE_DOC_INTEL_KEY
from app.models.canonical import CanonicalRateSheet, RateRow, ChargeItem, JobSummary
from app.services.ai_column_mapper import AIColumnMapper


# ── Expanded Column Header Synonyms ──────────────────────────────────────

ORIGIN_HEADERS = {
    "origin", "pol", "por", "from", "load port", "loading port",
    "port of loading", "port of origin", "departure", "ex", "cntr origin",
    "origin port", "dep", "source", "pol - dry", "pol-dry",
}

DESTINATION_HEADERS = {
    "destination", "dest", "pod", "to", "discharge port", "disch port",
    "port of discharge", "delivery", "arrival", "dest port",
    "destination port", "discharging port",
}

CONTAINER_PATTERNS: List[Tuple[str, List[str]]] = [
    ("20DG", ["20dg", "20'dg", "20 hazardous"]),
    ("40DG", ["40dg", "40'dg", "40 hazardous"]),
    ("45DG", ["45dg", "45'dg", "45 hazardous"]),
    ("20OT", ["20ot", "20'ot", "20'ot/fr", "20ot/fr"]),
    ("40OT", ["40ot", "40'ot", "40'ot/fr", "40ot/fr"]),
    ("20FR", ["20fr", "20'fr"]),
    ("40FR", ["40fr", "40'fr"]),
    ("40HC", ["40hc", "40'hc", "40hq", "40'hq", "40hi", "h40", "hc"]),
    ("45HC", ["45hc", "45'hc", "45hq", "45'hq"]),
    ("45GP", ["45gp", "45'gp"]),
    ("20RF", ["20rf", "20'rf", "20reefer", "r20"]),
    ("40RF", ["40rf", "40'rf", "40reefer", "r40"]),
    ("20NOR", ["20nor", "20'nor"]),
    ("40NOR", ["40nor", "40'nor"]),
    ("20GP", ["20'", "20gp", "20'gp", "20'st", "20dv", "20'dv", "20ft", "20dr", "d20", "teu", "20"]),
    ("40GP", ["40'", "40gp", "40'gp", "40'st", "40dv", "40'dv", "40ft", "40dr", "d40", "40"]),
    ("LCL",  ["lcl", "cbm", "w/m", "per cbm"]),
]

RATE_HEADERS = {
    "rate", "ofr", "amount", "freight", "price", "frt",
    "ocean freight", "base rate", "bas", "total",
}

CURRENCY_HEADERS = {"currency", "curr", "cur", "ccy"}

# ── Local Charges Table Detection ──
LOCAL_CHARGE_HEADERS = {
    "charge", "charge code", "charge name", "description", "surcharge",
    "local charge", "type", "charge type",
}

LOCAL_AMOUNT_HEADERS = {
    "amount", "rate", "charge amount", "usd", "aud", "20gp", "40gp", "40hc",
}

LOCAL_BASIS_HEADERS = {
    "basis", "per", "uom", "unit", "rate basis",
}


def _normalize(s: str) -> str:
    return re.sub(r'\s+', ' ', s.strip()).lower()


def _match_header(header: str, synonyms: set) -> bool:
    h = _normalize(header)
    if not h or h.startswith('$') or re.match(r'^\$?\d+', h):
        return False
    return h in synonyms or any(syn == h or (len(syn) > 3 and syn in h.split()) for syn in synonyms)


def _match_container(header: str) -> Optional[str]:
    h = _normalize(header)
    words = h.split()
    for std_type, patterns in CONTAINER_PATTERNS:
        for pat in patterns:
            if pat in h:
                if pat == "hc" and "thc" in h and "hc" not in words and "40hc" not in h and "40'hc" not in h:
                    continue
                if len(pat) <= 2 and pat not in words:
                    continue
                return std_type
    return None


def _extract_amount(val: str) -> Optional[float]:
    """Clean OCR artifacts and extract numeric freight rate amount."""
    if not val:
        return None
    s = val.strip()
    # Remove currency symbols
    s = s.replace('$', '').replace('€', '').replace('£', '').replace('¥', '')
    # Handle OCR misreads: ",250" -> "1250", "$,250" -> "1250"
    if s.startswith(','):
        s = '1' + s.lstrip(',')
    elif s.startswith('$,'):
        s = '1' + s.replace('$,', '')
    s = s.replace(',', '').replace(' ', '')
    try:
        amt = float(s)
        return amt if amt > 0 else None
    except ValueError:
        digits = re.findall(r'\d+\.?\d*', s)
        if digits:
            try:
                return float(digits[0])
            except ValueError:
                pass
    return None


class AzureDocumentIntelligenceParser(BaseParser):
    """
    Microsoft Azure Document Intelligence (Form Recognizer) Integration
    Extracts structured rate tables from PDF documents & image rate cards (.pdf, .png, .jpg, .tiff)
    using the 'prebuilt-layout' model.
    """

    def __init__(self, endpoint: str = AZURE_DOC_INTEL_ENDPOINT, api_key: str = AZURE_DOC_INTEL_KEY):
        self.endpoint = endpoint.rstrip('/')
        self.api_key = api_key

    def can_parse(self, file_path: Path, filename: str) -> bool:
        fn = filename.lower()
        return fn.endswith('.pdf') or fn.endswith('.png') or fn.endswith('.jpg') or fn.endswith('.jpeg') or fn.endswith('.tiff')

    def parse(self, file_path: Path, job_id: str) -> CanonicalRateSheet:
        print(f"[Azure DocIntel] Processing: {file_path.name} (Job: {job_id})")

        carrier = self._detect_carrier(file_path.name)

        # If Azure credentials are configured, use Azure API
        if self.endpoint and self.api_key:
            try:
                result = self._analyze_with_azure(file_path)
                tables = result.get("tables", [])
                content_text = result.get("content", "")

                carrier = self._detect_carrier(file_path.name, content_text)

                if tables:
                    try:
                        # Try standard rate table extraction first across all tables/pages
                        sheet = self._convert_tables_to_canonical(tables, job_id, file_path.name, carrier, content_text)

                        if sheet.rates:
                            return sheet
                    except Exception as table_err:
                        print(f"[Azure DocIntel] Error during table extraction: {table_err}")

                # Try extracting from content text
                if content_text:
                    print(f"[Azure DocIntel] Attempting text extraction...")
                    sheet = self._extract_from_text(content_text, job_id, file_path.name, carrier)
                    if sheet.rates:
                        return sheet

                    # Try GRI notice extraction
                    sheet = self._extract_gri_notice(content_text, job_id, file_path.name, carrier)
                    if sheet.rates:
                        return sheet

                    # GPT-4o Unstructured Fallback
                    print(f"[Azure DocIntel] Fallback: Using GPT-4o to extract from unstructured text for {file_path.name}...")
                    sheet = self._extract_with_gpt_fallback(content_text, job_id, file_path.name, carrier)
                    if sheet.rates:
                        return sheet

                print(f"[Azure DocIntel] Warning: No rate data could be extracted from {file_path.name} (even with GPT fallback)")

            except Exception as e:
                print(f"[Azure DocIntel API Error] {e}")
                import traceback
                traceback.print_exc()

        # Return empty sheet (no hardcoded fallback data)
        return CanonicalRateSheet(
            job_id=job_id,
            file_name=file_path.name,
            carrier_code=carrier or "UNKN",
            rates=[],
            summary=JobSummary(total_rows=0, carriers_found=[carrier] if carrier else [])
        )

    def _analyze_with_azure(self, file_path: Path) -> Dict[str, Any]:
        """
        Submits PDF/Image file to Azure Document Intelligence 'prebuilt-layout' REST API
        Returns the full analyzeResult including tables AND content text.
        """
        api_url = f"{self.endpoint}/formrecognizer/documentModels/prebuilt-layout:analyze?api-version=2023-07-31"

        headers = {
            "Ocp-Apim-Subscription-Key": self.api_key,
            "Content-Type": "application/octet-stream"
        }

        with open(file_path, "rb") as f:
            data = f.read()

        response = requests.post(api_url, headers=headers, data=data)
        if response.status_code != 202:
            raise Exception(f"Azure submit failed ({response.status_code}): {response.text}")

        operation_location = response.headers.get("Operation-Location")
        if not operation_location:
            raise Exception("No Operation-Location header received from Azure")

        # Poll operation status
        poll_headers = {"Ocp-Apim-Subscription-Key": self.api_key}
        for _ in range(45):
            time.sleep(1.5)
            poll_resp = requests.get(operation_location, headers=poll_headers)
            if poll_resp.status_code == 200:
                result = poll_resp.json()
                status = result.get("status")
                if status == "succeeded":
                    return result.get("analyzeResult", {})
                elif status == "failed":
                    raise Exception(f"Azure analysis failed: {result.get('error')}")

        raise Exception("Azure Document Intelligence analysis timed out after 67s")

    def _convert_tables_to_canonical(self, tables: List[Dict[str, Any]], job_id: str, filename: str,
                                      carrier: str, content_text: str = "") -> CanonicalRateSheet:
        """
        Converts ALL Azure Document Intelligence extracted tables into rate rows.
        Uses intelligent column header detection with expanded synonyms.
        """
        rates: List[RateRow] = []
        global_row_idx = 1

        carrier = carrier or self._detect_carrier(filename, content_text)

        # Try to extract validity from document text
        validity_start, validity_end = self._extract_validity(content_text)

        print(f"[Azure DocIntel] Processing {len(tables)} tables from document (Carrier: {carrier})")

        for table_idx, table in enumerate(tables):
            row_count = table.get("rowCount", 0)
            col_count = table.get("columnCount", 0)
            cells = table.get("cells", [])

            if row_count < 2 or col_count < 2:
                continue

            # Reconstruct 2D matrix
            matrix = [["" for _ in range(col_count)] for _ in range(row_count)]
            for cell in cells:
                r = cell.get("rowIndex", 0)
                c = cell.get("columnIndex", 0)
                matrix[r][c] = cell.get("content", "").strip()

            # Title & context inspection
            title_text = " ".join([" ".join(row) for row in matrix[:2]]).upper()
            table_currency = "AUD" if "AUD" in title_text else "EUR" if "EUR" in title_text else "USD"
            is_import_thc = "IMPORT" in title_text or "DISCHARGE PORT" in title_text or "THD" in title_text
            is_export_thc = "EXPORT" in title_text or "LOADING PORT" in title_text or "THC" in title_text

            # ── Find header row (may be row 0 or 1 or split across rows 0..1) ──
            header_row = 0
            col_map: Dict[str, int] = {}
            container_cols: List[Tuple[int, str]] = []
            
            ai_mapper = AIColumnMapper.get_instance()

            for try_row in range(min(3, row_count)):
                headers = [_normalize(c) for c in matrix[try_row]]
                
                # Try AI mapping first
                sample_rows = matrix[try_row+1:min(try_row+4, row_count)]
                ai_result = ai_mapper.map_columns(headers, sample_rows, carrier)
                
                if ai_result and ai_result.get("container_cols"):
                    col_map = {k: int(v) for k, v in ai_result.get("col_map", {}).items() if v is not None}
                    container_cols = [(int(c[0]), c[1]) for c in ai_result.get("container_cols", []) if c[0] is not None]
                    header_row = try_row
                    break

                for c_idx, h in enumerate(headers):
                    if not h:
                        continue
                    if _match_header(h, ORIGIN_HEADERS) and "origin" not in col_map:
                        col_map["origin"] = c_idx
                    elif _match_header(h, DESTINATION_HEADERS) and "destination" not in col_map:
                        col_map["destination"] = c_idx
                    elif _match_header(h, CURRENCY_HEADERS) and "currency" not in col_map:
                        col_map["currency"] = c_idx

                    ct = _match_container(h)
                    if ct and not any(c[0] == c_idx for c in container_cols):
                        container_cols.append((c_idx, ct))

                if ("origin" in col_map or "destination" in col_map or "charge_code" in col_map) and container_cols:
                    header_row = try_row
                    break

            if not container_cols:
                # Try to use rate-like columns for single-rate tables
                for c_idx, h in enumerate([_normalize(c) for c in matrix[0]]):
                    if _match_header(h, RATE_HEADERS):
                        container_cols.append((c_idx, "20GP"))

            if not container_cols:
                print(f"[Azure DocIntel] Table {table_idx}: no container/rate columns found, skipping")
                continue

            print(f"[Azure DocIntel] Table {table_idx}: header_row={header_row}, "
                  f"col_map={col_map}, containers={container_cols}")

            # ── Extract data rows ──
            for r_idx in range(header_row + 1, row_count):
                row_vals = matrix[r_idx]

                orig_val = row_vals[col_map["origin"]] if "origin" in col_map and col_map["origin"] < len(row_vals) else ""
                dest_val = row_vals[col_map["destination"]] if "destination" in col_map and col_map["destination"] < len(row_vals) else ""
                
                charge_name = ""
                if "charge_code" in col_map and col_map["charge_code"] < len(row_vals):
                    charge_name = row_vals[col_map["charge_code"]].strip()

                currency = table_currency
                if "currency" in col_map and col_map["currency"] < len(row_vals):
                    c = row_vals[col_map["currency"]].strip().upper()
                    if c:
                        currency = c

                # Clean up price values ($645, 645, etc.) wrongly assigned to port names
                if dest_val and (dest_val.startswith('$') or dest_val.replace('.', '').replace(',', '').isdigit()):
                    dest_val = ""
                if orig_val and (orig_val.startswith('$') or orig_val.replace('.', '').replace(',', '').isdigit()):
                    orig_val = ""

                # Handle local charges THC/THD tables (where port column 0 is discharge or loading port)
                if is_import_thc and not orig_val and not dest_val and row_vals[0]:
                    port_cand = row_vals[0].strip()
                    if not port_cand.startswith('$') and not port_cand.replace('.', '').replace(',', '').isdigit():
                        dest_val = port_cand

                elif is_export_thc and not orig_val and not dest_val and row_vals[0]:
                    port_cand = row_vals[0].strip()
                    if not port_cand.startswith('$') and not port_cand.replace('.', '').replace(',', '').isdigit():
                        orig_val = port_cand

                if not orig_val and not dest_val and not charge_name:
                    continue

                for col_i, container_type in container_cols:
                    if col_i >= len(row_vals):
                        continue
                    val_raw = row_vals[col_i].strip()
                    amt = _extract_amount(val_raw)
                    if amt is not None and amt > 0:
                        rates.append(RateRow(
                            row_index=global_row_idx,
                            carrier_scac=carrier or "UNKN",
                            origin_raw=orig_val,
                            destination_raw=dest_val,
                            load_type=container_type,
                            ofr_amount=amt,
                            ofr_currency=currency,
                            validity_start=validity_start,
                            validity_end=validity_end,
                            contract_number="",
                            remarks=f"Local Charge: {charge_name}" if charge_name else "",
                            commodity=charge_name if charge_name else ""
                        ))
                        global_row_idx += 1

        print(f"[Azure DocIntel] Extracted {len(rates)} rate rows from {len(tables)} tables")

        return CanonicalRateSheet(
            job_id=job_id,
            file_name=filename,
            carrier_code=carrier or "UNKN",
            carrier_name=f"Azure Doc Intel Extracted ({carrier})",
            contract_number="",
            validity_start=validity_start,
            validity_end=validity_end,
            rates=rates,
            summary=JobSummary(total_rows=len(rates), carriers_found=[carrier] if carrier else [])
        )

    def _extract_from_text(self, content: str, job_id: str, filename: str, carrier: str) -> CanonicalRateSheet:
        """Fallback: extract rate-like patterns from plain text content."""
        # This handles unstructured PDFs where Azure finds text but no tables
        rates: List[RateRow] = []
        # Simple pattern: ORIGIN TO DESTINATION USD AMOUNT
        pattern = re.compile(
            r'([A-Z]{2,}(?:\s+[A-Z]+)*)\s+(?:to|→|->)\s+([A-Z]{2,}(?:\s+[A-Z]+)*)\s+'
            r'(?:USD|EUR|AUD)?\s*\$?\s*(\d[\d,.]+)',
            re.IGNORECASE
        )
        for i, match in enumerate(pattern.finditer(content)):
            amt = _extract_amount(match.group(3))
            if amt and amt > 0:
                rates.append(RateRow(
                    row_index=len(rates) + 1,
                    carrier_scac=carrier or "UNKN",
                    origin_raw=match.group(1).strip(),
                    destination_raw=match.group(2).strip(),
                    load_type="20GP",
                    ofr_amount=amt,
                    ofr_currency="USD",
                ))

        # Text-fallback for local charges (e.g. HMM Local Charges layout)
        if content:
            lines = content.split('\n')
            current_port = ""
            current_currency = "AUD"
            for line in lines:
                l_strip = line.strip()
                if not l_strip:
                    continue
                # Port detection: SYD, MEL, BNE, ADL, FRE
                for p in ["SYD", "MEL", "BNE", "ADL", "FRE", "SYDNEY", "MELBOURNE", "BRISBANE", "ADELAIDE", "FREMANTLE"]:
                    if p in l_strip.upper().split():
                        current_port = p
                        break
                # Look for amounts line: e.g. "DC 676 937 937 1,044" or "RF 846 1,101 1,101"
                m_amt = re.search(r'\b(DC|RF|GP|HD|FR|OT|DG|AUD|USD)\b\s+([\d,.]+)\s+([\d,.]+)\s+([\d,.]+)', l_strip, re.IGNORECASE)
                if m_amt:
                    c_type = m_amt.group(1).upper()
                    amt20 = _extract_amount(m_amt.group(2))
                    amt40 = _extract_amount(m_amt.group(3))
                    amt40h = _extract_amount(m_amt.group(4))

                    for ct, amt_v in [("20GP", amt20), ("40GP", amt40), ("40HC", amt40h)]:
                        if amt_v and amt_v > 0:
                            rates.append(RateRow(
                                row_index=len(rates) + 1,
                                carrier_scac=carrier or "HMMU",
                                origin_raw=current_port,
                                destination_raw=current_port,
                                load_type=ct,
                                ofr_amount=amt_v,
                                ofr_currency=current_currency,
                                remarks=f"HMM Local Charge ({c_type})",
                                commodity=f"Local Charge {c_type}",
                            ))

        return CanonicalRateSheet(
            job_id=job_id,
            file_name=filename,
            carrier_code=carrier or "UNKN",
            rates=rates,
            summary=JobSummary(total_rows=len(rates))
        )

    def _extract_validity(self, text: str) -> Tuple[str, str]:
        """Extract validity date range from document text."""
        if not text:
            return ("", "")

        import datetime

        # Strip ordinal suffixes: 15th -> 15, 1st -> 1, 2nd -> 2, 3rd -> 3
        clean_text = re.sub(r'(\d+)(st|nd|rd|th)', r'\1', text, flags=re.IGNORECASE)

        # Single date start pattern (e.g. "Effective for all shipments with Bill of Lading dated 15 August 2025 onwards")
        m_onwards = re.search(r'(?:effective|dated|validity|from)[:\s]+(?:for\s+all\s+shipments\s+with\s+bill\s+of\s+lading\s+dated\s+)?(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})', clean_text, re.IGNORECASE)
        if m_onwards:
            day, month, year = m_onwards.groups()
            for fmt in ["%d %B %Y", "%d %b %Y"]:
                try:
                    d1 = datetime.datetime.strptime(f"{day} {month} {year}", fmt)
                    return (d1.strftime("%Y-%m-%d"), "")
                except ValueError:
                    pass

        patterns = [
            r'(?:effective|valid|validity)[:\s]*(?:from\s+)?(\d{1,2})\s*(?:-|to|–|—)\s*(\d{1,2})\s+(\w+)[,\s]*(\d{4})',
            r'(\d{1,2}\s+\w+\s+\d{4})\s*(?:-|to|–|—)\s*(\d{1,2}\s+\w+\s+\d{4})',
        ]
        for pat in patterns:
            m = re.search(pat, clean_text, re.IGNORECASE)
            if m:
                groups = m.groups()
                if len(groups) == 4:
                    day1, day2, month, year = groups
                    for fmt in ["%d %B %Y", "%d %b %Y"]:
                        try:
                            d1 = datetime.datetime.strptime(f"{day1} {month} {year}", fmt)
                            d2 = datetime.datetime.strptime(f"{day2} {month} {year}", fmt)
                            return (d1.strftime("%Y-%m-%d"), d2.strftime("%Y-%m-%d"))
                        except ValueError:
                            pass
                elif len(groups) == 2:
                    for fmt in ["%d %B %Y", "%d %b %Y"]:
                        try:
                            d1 = datetime.datetime.strptime(groups[0].strip(), fmt)
                            d2 = datetime.datetime.strptime(groups[1].strip(), fmt)
                            return (d1.strftime("%Y-%m-%d"), d2.strftime("%Y-%m-%d"))
                        except ValueError:
                            pass
        return ("", "")

    def _detect_carrier(self, filename: str, content_text: str = "") -> str:
        """Detect carrier SCAC from PDF/image filename and content text."""
        fn = filename.lower()
        full_text = (filename + " " + content_text).lower()
        carriers = [
            ("COSU", ["cosco", "cosu"]),
            ("MAEU", ["maersk", "maeu", "sealand"]),
            ("ONEY", ["one ", "oney", "ocean network express"]),
            ("MSCU", ["msc", "mscu", "mediterranean shipping"]),
            ("HMMU", ["hmm", "hyundai"]),
            ("ZIMU", ["zim"]),
            ("OOLU", ["oocl"]),
            ("CMDU", ["cma", "anl"]),
            ("AAXU", ["aax"]),
            ("AAWU", ["aaw"]),
            ("CTLU", ["carotrans", "caro trans"]),
            ("VGLU", ["vanguard", "shipco"]),
            ("EGLV", ["evergreen"]),
            ("HLCU", ["hapag"]),
            ("YMLU", ["yang ming"]),
        ]
        for scac, patterns in carriers:
            for pat in patterns:
                if pat in fn:
                    return scac
        for scac, patterns in carriers:
            for pat in patterns:
                if pat in full_text:
                    return scac
        return ""


    def _extract_gri_notice(self, content: str, job_id: str, filename: str, carrier: str) -> CanonicalRateSheet:
        """Extract GRI (General Rate Increase / Rate Restoration) information from text content."""
        rates: List[RateRow] = []

        # Look for GRI amount patterns
        gri_patterns = [
            # "USD $500/teu" or "$500/teu" or "USD 500 per teu"
            re.compile(r'(?:USD|EUR|AUD)?\s*\$?\s*(\d[\d,.]+)\s*(?:/|per\s+)(?:teu|cbm|container|box)', re.IGNORECASE),
            # "GRI of USD 200" or "Rate Restoration USD $500"
            re.compile(r'(?:GRI|Rate Restoration|Rate Increase|Restoration)[\s:]*(?:of|by|with|quantum of)?\s*(?:USD|EUR|AUD)?\s*\$?\s*(\d[\d,.]+)', re.IGNORECASE),
            re.compile(r'(?:increase|adjustment)[\s:]*(?:of|by)\s*(?:USD|EUR|AUD)?\s*\$?\s*(\d[\d,.]+)', re.IGNORECASE),
        ]

        gri_amount = None
        for pat in gri_patterns:
            m = pat.search(content)
            if m:
                gri_amount = _extract_amount(m.group(1))
                if gri_amount and gri_amount > 10:
                    break

        if not gri_amount:
            return CanonicalRateSheet(job_id=job_id, file_name=filename, carrier_code=carrier or "UNKN", rates=[], summary=JobSummary(total_rows=0))

        validity_start, validity_end = self._extract_validity(content)

        # Try to determine affected routes from text
        origins = []
        destinations = []

        if re.search(r'Northeast|North East|NEA', content, re.IGNORECASE):
            origins.append("NEA")
        if re.search(r'Southeast|South East|SEA', content, re.IGNORECASE):
            origins.append("SEA")
        if not origins:
            origins = ["NEA", "SEA"]

        if re.search(r'Australia|AUS', content, re.IGNORECASE):
            destinations.append("AUS MAIN PORTS")
        if not destinations:
            destinations = ["AUS MAIN PORTS"]

        row_idx = 1
        for orig in origins:
            for dest in destinations:
                for ct in ["20GP", "40GP", "40HC"]:
                    rates.append(RateRow(
                        row_index=row_idx,
                        carrier_scac=carrier or "ZIMU",
                        origin_raw=orig,
                        destination_raw=dest,
                        load_type=ct,
                        ofr_amount=gri_amount,
                        ofr_currency="USD",
                        validity_start=validity_start,
                        validity_end=validity_end,
                        remarks=f"Rate Restoration GRI: +${gri_amount}",
                    ))
                    row_idx += 1

        print(f"[Azure DocIntel] Extracted {len(rates)} GRI notice rows")
        return CanonicalRateSheet(
            job_id=job_id,
            file_name=filename,
            carrier_code=carrier or "ZIMU",
            rates=rates,
            summary=JobSummary(total_rows=len(rates), carriers_found=[carrier] if carrier else [])
        )

    def _extract_with_gpt_fallback(self, content_text: str, job_id: str, filename: str, carrier: str) -> CanonicalRateSheet:
        """
        Fallback extraction using GPT-4o. Sends the raw OCR text and expects a structured JSON array.
        """
        rates = []
        mapper = AIColumnMapper.get_instance()
        
        # If no openai credentials, abort fallback
        if not mapper.client:
            print("[GPT Fallback] No OpenAI credentials available, skipping fallback.")
            return CanonicalRateSheet(job_id=job_id, file_name=filename, carrier_code=carrier or "UNKN", rates=[], summary=JobSummary(total_rows=0))

        system_prompt = '''You are a highly capable logistics data extractor.
I will provide you with the raw text extracted from a rate card document (PDF).
Your job is to find all the ocean freight rates and return them in a valid JSON array of objects.

JSON schema for each object:
{
  "origin": "string (port or city name)",
  "destination": "string (port or city name)",
  "container_type": "string (e.g., '20GP', '40GP', '40HC')",
  "amount": "number (float, no currency symbol)",
  "currency": "string (e.g., 'USD', 'AUD')"
}

Rules:
1. ONLY return the JSON array. Do not wrap in ```json or explain anything.
2. If the text does not contain any rates, return an empty array [].
3. For 'container_type', try to normalize to '20GP', '40GP', '40HC', '20RF', '40RF', '20OT', '40OT'.
4. If a rate is given for a range of weights instead of a container (e.g. LCL per CBM/W/M), you can skip it or try to map it as 'LCL'.
'''
        # Truncate content text if it's too massive (e.g., > 30000 chars)
        prompt_text = content_text[:30000]

        try:
            response = mapper.client.chat.completions.create(
                model=mapper.deployment_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt_text}
                ],
                temperature=0.0
            )
            
            result_str = response.choices[0].message.content.strip()
            
            # Clean up markdown if the model mistakenly included it
            if result_str.startswith("```json"):
                result_str = result_str[7:]
            if result_str.startswith("```"):
                result_str = result_str[3:]
            if result_str.endswith("```"):
                result_str = result_str[:-3]
            result_str = result_str.strip()
            
            data = json.loads(result_str)
            if not isinstance(data, list):
                print("[GPT Fallback] Model returned invalid structure (not a list).")
                data = []

            # Determine validity from text
            validity_start, validity_end = self._extract_validity(content_text)
            
            row_idx = 1
            for item in data:
                if not isinstance(item, dict):
                    continue
                
                amount = item.get("amount")
                if amount is None:
                    continue
                try:
                    amount = float(amount)
                except (ValueError, TypeError):
                    continue

                rates.append(RateRow(
                    row_index=row_idx,
                    carrier_scac=carrier or "UNKN",
                    origin_raw=item.get("origin", "Unknown"),
                    destination_raw=item.get("destination", "Unknown"),
                    load_type=item.get("container_type", "20GP"),
                    ofr_amount=amount,
                    ofr_currency=item.get("currency", "USD"),
                    validity_start=validity_start,
                    validity_end=validity_end,
                    remarks="Extracted via GPT-4o Fallback"
                ))
                row_idx += 1
                
            print(f"[Azure DocIntel] GPT Fallback extracted {len(rates)} rows successfully.")
            
        except Exception as e:
            print(f"[GPT Fallback Error] {e}")

        return CanonicalRateSheet(
            job_id=job_id,
            file_name=filename,
            carrier_code=carrier or "UNKN",
            rates=rates,
            summary=JobSummary(total_rows=len(rates), carriers_found=[carrier] if carrier else [])
        )

