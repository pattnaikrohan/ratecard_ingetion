import openpyxl
import re
from pathlib import Path
from typing import List
from app.services.parsers.base_parser import BaseParser
from app.models.canonical import CanonicalRateSheet, RateRow, ChargeItem, JobSummary

class ONEPlugin(BaseParser):
    def can_parse(self, file_path: Path, filename: str) -> bool:
        fn = filename.lower()
        # Check filename first
        if "oney" in fn or "ocean network" in fn or "one-line" in fn:
            return True
        # Avoid false positive: "one" appears in many words (done, phone, zone...)
        # Use word boundary check for standalone "one"
        import re
        if re.search(r'\bone\b', fn):
            return True
        # Check file content for "OCEAN NETWORK EXPRESS" in top rows
        if file_path.suffix.lower() in ('.xlsx', '.xlsm', '.xls'):
            try:
                wb = openpyxl.load_workbook(file_path, data_only=True, read_only=True)
                ws = wb.active
                for r in range(1, min((ws.max_row or 1) + 1, 10)):
                    row_text = " ".join(str(ws.cell(r, c).value or "") for c in range(1, min((ws.max_column or 1) + 1, 15)))
                    if "OCEAN NETWORK EXPRESS" in row_text.upper():
                        wb.close()
                        return True
                wb.close()
            except Exception:
                pass
        return False

    def parse(self, file_path: Path, job_id: str) -> CanonicalRateSheet:
        wb = openpyxl.load_workbook(file_path, data_only=True)
        rates: List[RateRow] = []
        row_counter = 1
        validity_start = ""
        validity_end = ""
        contract_number = ""

        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            if ws.max_row is None or ws.max_row < 3:
                continue

            max_col = min(ws.max_column or 1, 20)

            # Read top rows for metadata (validity, contract)
            for top_r in range(1, min((ws.max_row or 1) + 1, 15)):
                row_str = " ".join(str(ws.cell(top_r, c).value or "") for c in range(1, max_col + 1))
                if ("MRG" in row_str or "Contract" in row_str) and not contract_number:
                    m = re.search(r'([A-Za-z0-9\-_]{4,})', row_str)
                    if m:
                        contract_number = m.group(1)
                
                # Check for Validity or Effective/Expiry — handle ordinal suffixes
                if re.search(r'(valid|effect|expir)', row_str, re.IGNORECASE) and not validity_start:
                    # Strip ordinal suffixes (1st, 2nd, 3rd, 4th, 01st, 31st)
                    clean_str = re.sub(r'(\d+)(?:st|nd|rd|th)\b', r'\1', row_str)
                    # Try "DD Month YYYY - DD Month YYYY" pattern
                    m = re.search(
                        r'(\d{1,2}\s+[a-zA-Z]{3,9}\s+\d{4})\s*(?:to|\-|~)\s*(\d{1,2}\s+[a-zA-Z]{3,9}\s+\d{4})',
                        clean_str, re.IGNORECASE
                    )
                    if m:
                        validity_start = self._parse_date(m.group(1).strip())
                        validity_end = self._parse_date(m.group(2).strip())
                    else:
                        # Fallback: date formats like DD-MMM-YYYY or YYYY-MM-DD
                        dates = re.findall(r'(\d{2,4}[-/]\d{1,2}[-/]\d{1,4}|\d{1,2}-[a-zA-Z]{3}-\d{2,4})', row_str)
                        if len(dates) >= 1 and not validity_start:
                            validity_start = dates[0]
                        if len(dates) >= 2 and not validity_end:
                            validity_end = dates[1]

            # Dynamically find header row (look for ORIGIN/POR + DESTINATION/POD)
            header_row_idx = None
            por_idx = None
            pod_idx = None
            country_idx = None
            svc_idx = None
            equipment_cols = []  # list of (col_num, equipment_type)

            for r in range(1, min((ws.max_row or 1) + 1, 20)):
                row_vals = [str(ws.cell(r, c).value or "").strip().upper() for c in range(1, max_col + 1)]
                
                found_origin = False
                found_dest = False
                
                for c_idx, h in enumerate(row_vals):
                    if h in ("POR", "ORIGIN", "POL", "LOADING PORT"):
                        por_idx = c_idx + 1
                        found_origin = True
                    elif h in ("POD", "DESTINATION", "DISCHARGE PORT"):
                        pod_idx = c_idx + 1
                        found_dest = True
                    elif h in ("COUNTRY",):
                        country_idx = c_idx + 1
                    elif h in ("SERVICE", "SVC"):
                        svc_idx = c_idx + 1
                
                if found_origin or found_dest:
                    header_row_idx = r
                    # Detect equipment columns — support both standard and paired layout
                    # Standard: 20' | 40' | 40'HC | 20'RF | ...
                    # Paired: EQ TYPE | OCEAN FREIGHT | EQ TYPE | OCEAN FREIGHT
                    eq_type_cols = []
                    rate_cols = []
                    for c_idx, h in enumerate(row_vals):
                        if h in ("20'", "40'", "40'HC", "20'RF", "40'RF", "20'RAD", "40'RAD",
                                 "20GP", "40GP", "40HC", "20RF", "40RF", "45HC"):
                            equipment_cols.append((c_idx + 1, h))
                        elif h == "EQ TYPE":
                            eq_type_cols.append(c_idx + 1)
                        elif h in ("OCEAN FREIGHT", "RATE", "FREIGHT"):
                            rate_cols.append(c_idx + 1)
                    
                    # If we found paired EQ TYPE + OCEAN FREIGHT columns, resolve them from the data rows
                    if eq_type_cols and rate_cols and not equipment_cols:
                        # Pair each EQ TYPE col with the next RATE col
                        for eq_col in eq_type_cols:
                            matching_rate = None
                            for rc in rate_cols:
                                if rc > eq_col:
                                    matching_rate = rc
                                    break
                            if matching_rate:
                                # Read the first data row to get the actual equipment type
                                eq_val = str(ws.cell(r + 1, eq_col).value or "").strip().upper()
                                if eq_val:
                                    equipment_cols.append((matching_rate, eq_val))
                    break

            if header_row_idx is None or (por_idx is None and pod_idx is None):
                # Fallback to old behavior (headers at row 3)
                headers = [str(ws.cell(3, c).value or "").strip() for c in range(1, max_col + 1)]
                por_idx = self._find_col(headers, "POR")
                pod_idx = self._find_col(headers, "POD")
                svc_idx = self._find_col(headers, "Service")
                header_row_idx = 3
                for c_idx, h in enumerate(headers):
                    if h in ["20'", "40'", "40'HC", "20'RF", "40'RF", "20'RAD", "40'RAD"]:
                        equipment_cols.append((c_idx + 1, h))

            data_start = header_row_idx + 1

            for r in range(data_start, (ws.max_row or data_start) + 1):
                por_val = str(ws.cell(r, por_idx).value or "").strip() if por_idx else ""
                pod_val = str(ws.cell(r, pod_idx).value or "").strip() if pod_idx else ""
                svc_val = str(ws.cell(r, svc_idx).value or "").strip() if svc_idx else ""

                if not por_val or not pod_val:
                    continue

                # Skip surcharge header rows or empty sections
                if por_val.upper() in ("ORIGIN", "POR", "POL") or pod_val.upper() in ("DESTINATION", "POD"):
                    continue

                # Expand combined PODs (e.g. "Brisbane / Melbourne / Adelaide" -> ["Brisbane", "Melbourne", "Adelaide"])
                pods = [p.strip() for p in pod_val.split("/") if p.strip()]

                for pod_item in pods:
                    for col_num, eq_header in equipment_cols:
                        # For paired layout, read EQ TYPE from the same row (col_num - 1 is the EQ TYPE)
                        # Determine actual load type
                        load_type = self._map_equipment(eq_header)
                        
                        amt_val = ws.cell(r, col_num).value
                        if amt_val is not None and str(amt_val).strip() != "":
                            try:
                                amt = float(amt_val)
                            except ValueError:
                                continue

                            r_row = RateRow(
                                row_index=row_counter,
                                carrier_scac="ONEY",
                                origin_raw=por_val,
                                origin_locode=por_val,
                                destination_raw=pod_item,
                                destination_locode=pod_item,
                                service_type=svc_val,
                                cargo_type="FAK",
                                load_type=load_type,
                                commodity="FAK",
                                ofr_amount=amt,
                                ofr_currency="USD",
                                charges=[ChargeItem(charge_code="OFR", charge_name="Base Ocean Freight", amount=amt, currency="USD", basis="per equipment")],
                                validity_start=validity_start,
                                validity_end=validity_end,
                                contract_number=contract_number,
                                inclusions="",
                                subject_to="",
                                remarks=""
                            )
                            rates.append(r_row)
                            row_counter += 1

        summary = JobSummary(total_rows=len(rates), carriers_found=["ONEY"])
        return CanonicalRateSheet(
            job_id=job_id,
            file_name=file_path.name,
            carrier_code="ONEY",
            contract_number=contract_number,
            validity_start=validity_start,
            validity_end=validity_end,
            rates=rates,
            summary=summary
        )

    def _find_col(self, headers: List[str], target: str) -> int:
        for idx, h in enumerate(headers):
            if target.lower() == h.lower():
                return idx + 1
        return 1

    def _map_equipment(self, header: str) -> str:
        mapping = {
            "20'": "20GP",
            "40'": "40GP",
            "40'HC": "40HC",
            "20'RF": "20RF",
            "40'RF": "40RF",
            "20'RAD": "20GP",
            "40'RAD": "40HC",
            "20GP": "20GP",
            "40GP": "40GP",
            "40HC": "40HC",
            "20RF": "20RF",
            "40RF": "40RF",
            "45HC": "45HC",
        }
        return mapping.get(header.strip().upper(), mapping.get(header, "20GP"))

    def _parse_date(self, date_str: str) -> str:
        """Parse a date string like '01 October 2026' or '31 December 2026' into YYYY-MM-DD."""
        import datetime
        for fmt in ["%d %B %Y", "%d %b %Y", "%d-%b-%Y", "%Y-%m-%d", "%d/%m/%Y"]:
            try:
                dt = datetime.datetime.strptime(date_str.strip(), fmt)
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                continue
        return date_str

