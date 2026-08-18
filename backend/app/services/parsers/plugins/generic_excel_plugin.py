"""
Generic Excel Rate Card Parser
Intelligently auto-detects column headers and extracts rate data from any carrier's Excel format.
Supports multi-sheet workbooks, multi-row headers, various container type column layouts,
LCL tariff formats (Rate per cbm/tonne/w/m), and split-header layouts (FRT+BAF subtotals).
"""
import openpyxl
import re
import datetime
from pathlib import Path
from typing import List, Optional, Tuple, Dict
from app.services.parsers.base_parser import BaseParser
from app.models.canonical import CanonicalRateSheet, RateRow, ChargeItem, JobSummary
from app.services.ai_column_mapper import AIColumnMapper


# ── Column Header Synonym Dictionaries ──────────────────────────────────────

ORIGIN_SYNONYMS = {
    "por", "pol", "origin", "from", "port of loading", "load port",
    "loading port", "port of origin", "cntr origin", "origin port",
    "departure", "dep", "dep port", "ex", "source", "receipt", "place of receipt",
    "origin city", "origin inland cfs", "consol cfs",
}

DESTINATION_SYNONYMS = {
    "pod", "destination", "dest", "to", "port of discharge", "discharge port",
    "disch port", "dest port", "delivery", "del", "del port", "arrival",
    "destination port", "arr", "place of delivery", "destination city",
    "destination inland cfs", "deconsol cfs",
}

ORIGIN_CODE_SYNONYMS = {
    "port code", "pol code", "origin code", "origin locode", "origin un code",
}

DEST_CODE_SYNONYMS = {
    "destination code", "dest code", "pod code", "destination locode",
    "destination un code", "port of discharge code",
}

CARRIER_SYNONYMS = {
    "carrier", "scac", "line", "shipping line", "carrier scac",
    "carrier code", "operator",
}

CURRENCY_SYNONYMS = {
    "currency", "curr", "cur", "ccy",
}

SERVICE_SYNONYMS = {
    "service", "svc", "service type", "mode", "routing",
}

VALIDITY_START_SYNONYMS = {
    "effective", "valid from", "validity from", "start", "eff date",
    "effective date", "from date", "valid date",
}

VALIDITY_END_SYNONYMS = {
    "expiry", "valid to", "validity to", "end", "exp date",
    "expiry date", "to date", "until", "validity",
}

CONTRACT_SYNONYMS = {
    "contract", "service contract", "sc no", "contract no",
    "contract number", "sc number", "agreement",
}

COMMODITY_SYNONYMS = {
    "commodity", "comm", "cargo", "goods", "commodity type",
}

CHARGE_CODE_SYNONYMS = {
    "charge code", "charge", "chg code",
}

CHARGE_NAME_SYNONYMS = {
    "charge name", "chg name", "description", "charge description",
}

AMOUNT_SYNONYMS = {
    "amount", "rate", "charge amount", "amt",
}

RATE_BASIS_SYNONYMS = {
    "rate basis", "basis", "per", "uom", "unit",
}

# Container type patterns mapped to standard load types
# IMPORTANT: More specific types (HC, RF, NOR) MUST come before generic (GP) to prevent false matches
CONTAINER_PATTERNS: List[Tuple[str, List[str]]] = [
    ("20DG", ["20'dg", "20dg", "20' hazardous", "20 hazardous"]),
    ("40DG", ["40'dg", "40dg", "40' hazardous", "40 hazardous"]),
    ("45DG", ["45'dg", "45dg", "45' hazardous", "45 hazardous"]),
    ("20OT", ["20'ot", "20ot", "20'ot/fr", "20ot/fr"]),
    ("40OT", ["40'ot", "40ot", "40'ot/fr", "40ot/fr"]),
    ("20FR", ["20'fr", "20fr", "20 flat rack"]),
    ("40FR", ["40'fr", "40fr", "40 flat rack"]),
    ("40HC", ["40'hc", "40hc", "40'hq", "40hq", "40hi", "h40", "40hdry"]),
    ("45HC", ["45'hc", "45hc", "45'hq", "45hq"]),
    ("45GP", ["45'gp", "45gp", "45'st", "45'dv", "45dv", "45ft", "45dr"]),
    ("20RF", ["20'rf", "20rf", "20reefer", "r20"]),
    ("40RF", ["40'rf", "40rf", "40reefer", "r40"]),
    ("20NOR", ["20nor", "20'nor"]),
    ("40NOR", ["40nor", "40'nor"]),
    ("20GP", ["20'st", "20'gp", "20gp", "20'dv", "20dv", "20ft", "20dr", "d20", "20dry", "20'"]),
    ("40GP", ["40'st", "40'gp", "40gp", "40'dv", "40dv", "40ft", "40dr", "d40", "40dry", "40'"]),
    ("LCL",  ["lcl", "cbm", "w/m", "per cbm", "per w/m"]),
]

# LCL-specific rate column headers
LCL_RATE_SYNONYMS = {
    "rate per cbm", "rate per tonne", "rate per w/m", "ocean freight rate",
    "ocean freight", "ofr", "minimum charge", "rate", 
    "per cbm", "per ton", "min", "w/m", "rt",
}

# Rate-like column patterns (when container type is in a separate column or combined rate column)
RATE_SYNONYMS = {
    "rate", "ofr", "amount", "freight", "price", "frt",
    "ocean freight", "base rate", "bas",
}


def _normalize(s: str) -> str:
    """Lowercase, strip, collapse whitespace, normalize separators."""
    return re.sub(r'\s+', ' ', s.strip()).lower()


def _match_synonym(header: str, synonyms: set) -> bool:
    """Match header against synonym set with word-boundary awareness for short synonyms."""
    h = _normalize(header)
    if h in synonyms:
        return True
    # For substring matching, require longer synonyms (>4 chars) to avoid
    # false matches like "por" inside "poa-pod-via port"
    for syn in synonyms:
        if len(syn) > 4 and syn in h:
            return True
        # For short synonyms (3-4 chars), require word boundary match
        elif 3 <= len(syn) <= 4:
            # Check if synonym appears as a standalone word
            if re.search(r'(?:^|[\s\-/,])' + re.escape(syn) + r'(?:$|[\s\-/,])', h):
                return True
    return False


def _match_container_type(header: str) -> Optional[str]:
    """Returns the standard load type if header matches a container pattern."""
    h = _normalize(header)
    for std_type, patterns in CONTAINER_PATTERNS:
        for pat in patterns:
            if pat in h:
                return std_type
    return None


def _match_lcl_rate(header: str) -> bool:
    """Check if header is an LCL rate column."""
    h = _normalize(header)
    if h in LCL_RATE_SYNONYMS:
        return True
    # Require longer synonym matches (>4 chars) for substring matching
    for syn in LCL_RATE_SYNONYMS:
        if len(syn) > 4 and syn in h:
            return True
    return False


def _extract_amount(val) -> Optional[float]:
    """Extracts a numeric amount from a cell value, handling OCR artifacts."""
    if val is None:
        return None
    s = str(val).strip()
    if not s or s.upper() in ('N/A', 'NA', '-', 'TBA', 'TBC', 'POA', 'INCL', 'INCLUSIVE', 'INCLUDED'):
        return None
    # Remove currency symbols and common OCR artifacts
    s = s.replace('$', '').replace('€', '').replace('£', '').replace('¥', '')
    s = s.replace(',', '').replace(' ', '')
    # Handle negative/parenthetical amounts
    if s.startswith('(') and s.endswith(')'):
        s = '-' + s[1:-1]
    try:
        amt = float(s)
        return amt if amt > 0 else None
    except ValueError:
        # Try extracting just digits
        digits = re.findall(r'\d+\.?\d*', s)
        if digits:
            try:
                amt = float(digits[0])
                return amt if amt > 0 else None
            except ValueError:
                return None
    return None


def _clean_date(date_val) -> str:
    """Parses various date formats into YYYY-MM-DD."""
    if not date_val:
        return ""
    if isinstance(date_val, datetime.datetime):
        return date_val.strftime("%Y-%m-%d")
    if isinstance(date_val, datetime.date):
        return date_val.strftime("%Y-%m-%d")
    s = str(date_val).strip()
    # Remove time component if present
    s = re.sub(r'\s+\d{2}:\d{2}:\d{2}.*$', '', s)
    for fmt in ["%Y-%m-%d", "%d-%b-%Y", "%d/%m/%Y", "%d-%m-%Y", "%m/%d/%Y",
                "%d %b %Y", "%d %B %Y", "%Y/%m/%d", "%b %d, %Y", "%B %d, %Y",
                "%Y-%m-%d %H:%M:%S"]:
        try:
            dt = datetime.datetime.strptime(s, fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            pass
    return s


class GenericExcelPlugin(BaseParser):
    """
    Intelligent generic Excel rate card parser.
    Auto-detects header rows and columns from any carrier's spreadsheet format.
    Supports FCL container-type columns AND LCL rate columns.
    """

    def can_parse(self, file_path: Path, filename: str) -> bool:
        fn = filename.lower()
        return fn.endswith('.xlsx') or fn.endswith('.xls') or fn.endswith('.xlsm')

    def parse(self, file_path: Path, job_id: str) -> CanonicalRateSheet:
        print(f"[GenericExcel] Parsing: {file_path.name} (Job: {job_id})")
        wb = openpyxl.load_workbook(file_path, data_only=True)
        all_rates: List[RateRow] = []
        row_counter = 1
        detected_carrier = ""
        detected_validity_start = ""
        detected_validity_end = ""
        detected_contract = ""
        detected_currency = "USD"

        # Try to extract metadata from filename
        fn = file_path.name
        carrier_from_filename = self._detect_carrier_from_filename(fn)
        validity_from_filename = self._detect_validity_from_filename(fn)
        if validity_from_filename:
            detected_validity_start, detected_validity_end = validity_from_filename

        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            if ws.max_row is None or ws.max_row < 2:
                continue

            max_col = min(ws.max_column or 1, 50)
            max_row = min(ws.max_row or 1, 5000)

            # ── Phase 1: Scan metadata from top rows ──
            for r in range(1, min(max_row + 1, 15)):
                row_text = " ".join(str(ws.cell(r, c).value or "") for c in range(1, max_col + 1))
                if not detected_validity_start and re.search(r'validity|effective', row_text, re.IGNORECASE):
                    text_clean = re.sub(r'\s+', ' ', row_text).strip()
                    m = re.search(r'(?:validity|effective)?[:\s]*(\d{1,2}\s+[a-zA-Z]{3,9}(?:\s+\d{4})?|\d{1,2}[\-/][a-zA-Z]{3,9}[\-/]\d{2,4}|\d{4}[\-/]\d{1,2}[\-/]\d{1,2})\s*(?:to|\-|\~)\s*(\d{1,2}\s+[a-zA-Z]{3,9}(?:\s+\d{4})?|\d{1,2}[\-/][a-zA-Z]{3,9}[\-/]\d{2,4}|\d{4}[\-/]\d{1,2}[\-/]\d{1,2})', text_clean, re.IGNORECASE)
                    if m:
                        s_raw = m.group(1).strip()
                        e_raw = m.group(2).strip()
                        year_match = re.search(r'\b(20\d{2})\b', text_clean)
                        year = year_match.group(1) if year_match else str(datetime.datetime.now().year)
                        if not re.search(r'\b20\d{2}\b', s_raw):
                            s_raw = f"{s_raw} {year}"
                        if not re.search(r'\b20\d{2}\b', e_raw):
                            e_raw = f"{e_raw} {year}"
                        detected_validity_start = _clean_date(s_raw)
                        detected_validity_end = _clean_date(e_raw)

                # Contract number
                contract_match = re.search(r'(?:contract|sc)\s*(?:no|number|#)?[:\s]*(\S+)', row_text, re.IGNORECASE)
                if contract_match and not detected_contract:
                    detected_contract = contract_match.group(1).strip()

            # ── Phase 2: Find header row ──
            header_row_idx = None
            col_map: Dict[str, int] = {}
            container_cols: List[Tuple[int, str]] = []
            is_lcl_format = False
            lcl_rate_col: Optional[int] = None
            
            ai_mapper = AIColumnMapper.get_instance()

            for r in range(1, min(max_row + 1, 25)):
                row_headers = [str(ws.cell(r, c).value or "").strip() for c in range(1, max_col + 1)]
                
                # Try AI mapping first
                sample_rows = []
                for sample_r in range(r + 1, min(r + 4, max_row + 1)):
                    sample_rows.append([str(ws.cell(sample_r, c).value or "").strip() for c in range(1, max_col + 1)])
                
                ai_result = ai_mapper.map_columns(row_headers, sample_rows, carrier_from_filename or "GenericExcel")
                if ai_result and (ai_result.get("col_map") or ai_result.get("container_cols")):
                    ai_col_map = ai_result.get("col_map", {})
                    # AI returns 0-indexed, convert to 1-indexed for this plugin
                    col_map = {k: int(v) + 1 for k, v in ai_col_map.items()}
                    
                    raw_containers = ai_result.get("container_cols", [])
                    container_cols = [(int(c[0]) + 1, c[1]) for c in raw_containers]
                    
                    if "origin" in col_map or "destination" in col_map:
                        header_row_idx = r
                        is_lcl_format = "LCL" in [c[1] for c in container_cols]
                        break

                candidate_map: Dict[str, int] = {}
                candidate_containers: List[Tuple[int, str]] = []
                candidate_lcl_col: Optional[int] = None
                origin_found = False
                dest_found = False
                container_found = False
                lcl_found = False

                for c_idx, h in enumerate(row_headers):
                    if not h:
                        continue
                    c_1based = c_idx + 1

                    if _match_synonym(h, ORIGIN_SYNONYMS) and "origin" not in candidate_map:
                        candidate_map["origin"] = c_1based
                        origin_found = True
                    elif _match_synonym(h, ORIGIN_CODE_SYNONYMS) and "origin_code" not in candidate_map:
                        candidate_map["origin_code"] = c_1based
                    elif _match_synonym(h, DESTINATION_SYNONYMS) and "destination" not in candidate_map:
                        candidate_map["destination"] = c_1based
                        dest_found = True
                    elif _match_synonym(h, DEST_CODE_SYNONYMS) and "dest_code" not in candidate_map:
                        candidate_map["dest_code"] = c_1based
                    elif _match_synonym(h, CARRIER_SYNONYMS) and "carrier" not in candidate_map:
                        candidate_map["carrier"] = c_1based
                    elif _match_synonym(h, CURRENCY_SYNONYMS) and "currency" not in candidate_map:
                        candidate_map["currency"] = c_1based
                    elif _match_synonym(h, SERVICE_SYNONYMS) and "service" not in candidate_map:
                        candidate_map["service"] = c_1based
                    elif _match_synonym(h, VALIDITY_START_SYNONYMS) and "validity_start" not in candidate_map:
                        candidate_map["validity_start"] = c_1based
                    elif _match_synonym(h, VALIDITY_END_SYNONYMS) and "validity_end" not in candidate_map:
                        candidate_map["validity_end"] = c_1based
                    elif _match_synonym(h, CONTRACT_SYNONYMS) and "contract" not in candidate_map:
                        candidate_map["contract"] = c_1based
                    elif _match_synonym(h, COMMODITY_SYNONYMS) and "commodity" not in candidate_map:
                        candidate_map["commodity"] = c_1based
                    elif _match_synonym(h, CHARGE_CODE_SYNONYMS) and "charge_code" not in candidate_map:
                        candidate_map["charge_code"] = c_1based
                    elif _match_synonym(h, CHARGE_NAME_SYNONYMS) and "charge_name" not in candidate_map:
                        candidate_map["charge_name"] = c_1based
                    elif _match_synonym(h, AMOUNT_SYNONYMS) and "amount" not in candidate_map:
                        candidate_map["amount"] = c_1based

                    ct = _match_container_type(h)
                    if ct:
                        candidate_containers.append((c_1based, ct))
                        container_found = True

                    # Check for LCL rate columns
                    if _match_lcl_rate(h) and not candidate_lcl_col:
                        candidate_lcl_col = c_1based
                        lcl_found = True

                # Also check next row for split headers
                if (origin_found or dest_found) and not container_found and r + 1 <= max_row:
                    next_row_headers = [str(ws.cell(r + 1, c).value or "").strip() for c in range(1, max_col + 1)]
                    for c_idx, h in enumerate(next_row_headers):
                        ct = _match_container_type(h)
                        if ct:
                            candidate_containers.append((c_idx + 1, ct))
                            container_found = True

                # Accept if we have origin OR destination, plus container columns OR LCL rate column
                if (origin_found or dest_found) and (container_found or lcl_found):
                    header_row_idx = r
                    col_map = candidate_map
                    container_cols = candidate_containers
                    is_lcl_format = lcl_found and not container_found
                    lcl_rate_col = candidate_lcl_col
                    # If split headers, data starts after the second header row
                    if container_found and any(_match_container_type(str(ws.cell(r + 1, c).value or "")) for c in range(1, max_col + 1)):
                        header_row_idx = r + 1
                    break

                # Also accept charge-sheet format: origin_code + dest_code + charge_code + amount
                if "origin_code" in candidate_map and "charge_code" in candidate_map and "amount" in candidate_map:
                    header_row_idx = r
                    col_map = candidate_map
                    is_lcl_format = True  # Use LCL-like single-rate parsing
                    break

            if header_row_idx is None:
                print(f"[GenericExcel] No header row found in sheet '{sheet_name}', skipping.")
                continue

            print(f"[GenericExcel] Sheet '{sheet_name}': header at row {header_row_idx}, "
                  f"col_map={col_map}, containers={[(c, t) for c, t in container_cols]}, "
                  f"lcl_format={is_lcl_format}")

            # ── Phase 3: Handle split-header — pick the TOTAL columns ──
            if container_cols and header_row_idx > 1:
                container_cols = self._resolve_split_header_totals(ws, header_row_idx, container_cols, max_row)

            # ── Phase 4: Extract rate rows ──
            data_start = header_row_idx + 1
            last_origin_val = ""
            last_origin_code = ""
            last_dest_val = ""
            last_dest_code = ""

            for r in range(data_start, max_row + 1):
                # Get origin
                origin_val = ""
                origin_code = ""
                if "origin" in col_map:
                    origin_val = str(ws.cell(r, col_map["origin"]).value or "").strip()
                if "origin_code" in col_map:
                    origin_code = str(ws.cell(r, col_map["origin_code"]).value or "").strip()

                # Get destination
                dest_val = ""
                dest_code = ""
                if "destination" in col_map:
                    dest_val = str(ws.cell(r, col_map["destination"]).value or "").strip()
                if "dest_code" in col_map:
                    dest_code = str(ws.cell(r, col_map["dest_code"]).value or "").strip()

                # Carry-forward: inherit from previous row if empty (merged cells)
                if origin_val:
                    last_origin_val = origin_val
                elif not origin_code:
                    origin_val = last_origin_val

                if origin_code:
                    last_origin_code = origin_code
                elif not origin_val:
                    origin_code = last_origin_code

                if dest_val:
                    last_dest_val = dest_val
                elif not dest_code:
                    dest_val = last_dest_val

                if dest_code:
                    last_dest_code = dest_code
                elif not dest_val:
                    dest_code = last_dest_code

                # Skip empty rows
                if not origin_val and not origin_code and not dest_val and not dest_code:
                    continue

                # Get optional fields
                carrier = carrier_from_filename or detected_carrier
                if "carrier" in col_map:
                    c_val = str(ws.cell(r, col_map["carrier"]).value or "").strip()
                    if c_val:
                        carrier = c_val

                currency = detected_currency
                if "currency" in col_map:
                    c_val = str(ws.cell(r, col_map["currency"]).value or "").strip().upper()
                    if c_val:
                        currency = c_val

                service = ""
                if "service" in col_map:
                    service = str(ws.cell(r, col_map["service"]).value or "").strip()

                v_start = detected_validity_start
                v_end = detected_validity_end
                if "validity_start" in col_map:
                    vs = ws.cell(r, col_map["validity_start"]).value
                    if vs:
                        v_start = _clean_date(vs)
                if "validity_end" in col_map:
                    ve = ws.cell(r, col_map["validity_end"]).value
                    if ve:
                        v_end = _clean_date(ve)

                contract = detected_contract
                if "contract" in col_map:
                    c_val = str(ws.cell(r, col_map["contract"]).value or "").strip()
                    if c_val:
                        contract = c_val

                commodity = "FAK"
                if "commodity" in col_map:
                    c_val = str(ws.cell(r, col_map["commodity"]).value or "").strip()
                    if c_val:
                        commodity = c_val

                # Handle charge-code format (e.g., "OFR" for Ocean Freight)
                charge_code = ""
                if "charge_code" in col_map:
                    charge_code = str(ws.cell(r, col_map["charge_code"]).value or "").strip().upper()

                # ── LCL Format: single rate column ──
                if is_lcl_format and not container_cols:
                    amt = None
                    if lcl_rate_col:
                        amt = _extract_amount(ws.cell(r, lcl_rate_col).value)
                    elif "amount" in col_map:
                        amt = _extract_amount(ws.cell(r, col_map["amount"]).value)

                    if amt is not None and amt > 0:
                        # Only include OFR (Ocean Freight) charge rows, skip local charges
                        if charge_code and charge_code not in ("OFR", "OCEAN FREIGHT", ""):
                            continue

                        o_raw = origin_val or origin_code
                        d_raw = dest_val or dest_code

                        rate_row = RateRow(
                            row_index=row_counter,
                            carrier_scac=carrier.upper() if carrier else "UNKN",
                            origin_raw=o_raw,
                            origin_locode=origin_code or o_raw,
                            destination_raw=d_raw,
                            destination_locode=dest_code or d_raw,
                            service_type=service,
                            cargo_type=commodity,
                            load_type="LCL",
                            commodity=commodity,
                            ofr_amount=amt,
                            ofr_currency=currency,
                            validity_start=v_start,
                            validity_end=v_end,
                            contract_number=contract,
                        )
                        all_rates.append(rate_row)
                        row_counter += 1
                    continue

                # ── FCL Format: multiple container columns ──
                # Filter out obvious add-on tables before splitting by "/"
                _o_chk = origin_val.strip().lower()
                if re.match(r'^(class\s*[\d\.]|psa\s*group|dg\s*class|haz\s*surcharge|haz\s*add|psa\s*add|via\s+sin\s+shipment)', _o_chk):
                    continue
                if any(kw in _o_chk for kw in ["bunker surcharge", "cargo value", "add-on", "addon", "tariff", "value range", "terms & conditions"]):
                    continue
                if re.match(r'^\d+$', _o_chk):
                    continue

                _d_chk = dest_val.strip().lower()
                if _d_chk.startswith("usd ") or "do not accept" in _d_chk or _d_chk in {"20'", "40'", "40hc", "45hc", "20gp", "40gp", "20", "40", "45", "20'rad", "40'rad"}:
                    continue
                if re.match(r'^\d+$', _d_chk):
                    continue
                if any(kw in _d_chk for kw in ["bunker surcharge", "cargo value", "add-on", "addon", "tariff", "value range", "usd301"]):
                    continue

                # Handle destinations with "/" separator
                dest_list = [d.strip() for d in dest_val.split("/") if d.strip()] if dest_val else [""]
                if not dest_list:
                    dest_list = [""]

                # Handle origins with "/" separator
                origin_list = [o.strip() for o in origin_val.split("/") if o.strip()] if origin_val else [""]
                origin_code_list = [oc.strip() for oc in origin_code.split("/") if oc.strip()] if origin_code else [""]

                for orig_i, orig in enumerate(origin_list):
                    oc = origin_code_list[orig_i] if orig_i < len(origin_code_list) else (origin_code_list[0] if origin_code_list else "")
                    for dest in dest_list:
                        for col_idx, container_type in container_cols:
                            amt = _extract_amount(ws.cell(r, col_idx).value)
                            if amt is not None and amt > 0:
                                rate_row = RateRow(
                                    row_index=row_counter,
                                    carrier_scac=carrier.upper() if carrier else "UNKN",
                                    origin_raw=orig or origin_code,
                                    origin_locode=oc or orig,
                                    destination_raw=dest or dest_code,
                                    destination_locode=dest_code or dest,
                                    service_type=service,
                                    cargo_type=commodity,
                                    load_type=container_type,
                                    commodity=commodity,
                                    ofr_amount=amt,
                                    ofr_currency=currency,
                                    validity_start=v_start,
                                    validity_end=v_end,
                                    contract_number=contract,
                                )
                                all_rates.append(rate_row)
                                row_counter += 1

        carrier_code = carrier_from_filename or detected_carrier or "UNKN"
        summary = JobSummary(
            total_rows=len(all_rates),
            carriers_found=[carrier_code] if carrier_code else ["UNKN"]
        )

        print(f"[GenericExcel] Extracted {len(all_rates)} rate rows from {file_path.name}")

        return CanonicalRateSheet(
            job_id=job_id,
            file_name=file_path.name,
            carrier_code=carrier_code,
            contract_number=detected_contract,
            validity_start=detected_validity_start,
            validity_end=detected_validity_end,
            rates=all_rates,
            summary=summary,
        )

    def _resolve_split_header_totals(self, ws, header_row_idx, container_cols: List[Tuple[int, str]], max_row: int) -> List[Tuple[int, str]]:
        """
        For split-header formats like AAX (FRT | BAF | 20'ST | FRT | BAF | 40'ST),
        detect which columns are totals vs breakdowns and pick the totals.
        A total column's values typically equal the sum of the preceding FRT+BAF columns.
        """
        if len(container_cols) <= 3:
            return container_cols  # Not a split-header situation

        # Group by container type — if we have duplicates like multiple "20GP" matches, pick totals
        type_groups: Dict[str, List[int]] = {}
        for col_idx, ct in container_cols:
            type_groups.setdefault(ct, []).append(col_idx)

        # If no duplicates per type, return as-is
        if all(len(cols) == 1 for cols in type_groups.values()):
            return container_cols

        # For each type with duplicates, check first 3 data rows to find the "total" column
        result: List[Tuple[int, str]] = []
        seen_types: set = set()
        for ct, cols in type_groups.items():
            if ct in seen_types:
                continue
            seen_types.add(ct)
            if len(cols) == 1:
                result.append((cols[0], ct))
            else:
                # Pick the column that has the highest values (totals are FRT+BAF)
                best_col = cols[0]
                best_sum = 0
                for col_idx in cols:
                    col_sum = 0
                    for r in range(header_row_idx + 1, min(header_row_idx + 5, max_row + 1)):
                        amt = _extract_amount(ws.cell(r, col_idx).value)
                        if amt:
                            col_sum += amt
                    if col_sum > best_sum:
                        best_sum = col_sum
                        best_col = col_idx
                result.append((best_col, ct))

        print(f"[GenericExcel] Split-header resolved: {result}")
        return result

    def _detect_carrier_from_filename(self, filename: str) -> str:
        """Attempt to identify carrier SCAC from the filename."""
        fn = filename.lower()
        carriers = [
            ("MAEU", ["maersk", "maeu", "sealand"]),
            ("ONEY", ["one ", "oney", "ocean network"]),
            ("MSCU", ["msc ", "mscu"]),
            ("HMMU", ["hmm", "hyundai"]),
            ("ZIMU", ["zim "]),
            ("OOLU", ["oocl", "orient overseas"]),
            ("CMDU", ["cma", "cma-cgm", "cma cgm", "anl"]),
            ("COSU", ["cosco"]),
            ("EGLV", ["evergreen"]),
            ("HLCU", ["hapag", "hapag-lloyd"]),
            ("YMLU", ["yang ming", "yml"]),
            ("WHLC", ["wan hai"]),
            ("SUDU", ["hamburg sud", "hamburg"]),
            ("AAXU", ["aax "]),
            ("CTLU", ["carotrans", "caro trans"]),
            ("AAWU", ["aaw "]),
            ("VGLU", ["vanguard", "shipco"]),
        ]
        for scac, patterns in carriers:
            for pat in patterns:
                if pat in fn:
                    return scac
        return ""

    def _detect_validity_from_filename(self, filename: str) -> Optional[Tuple[str, str]]:
        """Attempt to extract validity dates from filename."""
        fn = filename
        # Pattern: "01Aug26-31Aug26"
        m = re.search(r'(\d{1,2})([A-Za-z]{3})(\d{2,4})\s*[-–]\s*(\d{1,2})([A-Za-z]{3})(\d{2,4})', fn)
        if m:
            try:
                d1, m1, y1 = m.group(1), m.group(2), m.group(3)
                d2, m2, y2 = m.group(4), m.group(5), m.group(6)
                if len(y1) == 2: y1 = "20" + y1
                if len(y2) == 2: y2 = "20" + y2
                start = datetime.datetime.strptime(f"{d1} {m1} {y1}", "%d %b %Y")
                end = datetime.datetime.strptime(f"{d2} {m2} {y2}", "%d %b %Y")
                return (start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))
            except ValueError:
                pass
        # Pattern: "15-Jul 2026 to 31-Jul 2026"
        m = re.search(r'(\d{1,2})[- ]([A-Za-z]+)\s*(\d{4})\s*to\s*(\d{1,2})[- ]([A-Za-z]+)\s*(\d{4})', fn)
        if m:
            try:
                start = datetime.datetime.strptime(f"{m.group(1)} {m.group(2)} {m.group(3)}", "%d %b %Y")
                end = datetime.datetime.strptime(f"{m.group(4)} {m.group(5)} {m.group(6)}", "%d %b %Y")
                return (start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))
            except ValueError:
                pass
        return None
