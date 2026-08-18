import openpyxl
import datetime
import re
from pathlib import Path
from typing import List, Optional, Tuple
from app.services.parsers.base_parser import BaseParser
from app.models.canonical import CanonicalRateSheet, RateRow, ChargeItem, JobSummary

class MaerskPlugin(BaseParser):
    def can_parse(self, file_path: Path, filename: str) -> bool:
        fn = filename.lower()
        if "maeu" in fn or "maersk" in fn or "299163347" in fn:
            return True
        # Content-based detection: look for Maersk AFLS Quote format
        try:
            wb = openpyxl.load_workbook(file_path, data_only=True, read_only=True)
            for sn in wb.sheetnames[:3]:
                ws = wb[sn]
                for r in range(1, 6):
                    cell_a = str(ws.cell(r, 1).value or "").lower()
                    cell_b = str(ws.cell(r, 2).value or "").lower()
                    if "quote number" in cell_a and "maeu" in cell_b:
                        wb.close()
                        return True
                    if "carrier" in cell_a and "maersk" in cell_b:
                        wb.close()
                        return True
            wb.close()
        except Exception:
            pass
        return False

    def parse(self, file_path: Path, job_id: str) -> CanonicalRateSheet:
        wb = openpyxl.load_workbook(file_path, data_only=True)
        
        # Detect which sheet to use
        sheet_name = None
        for preferred in ["BAS+Surcharges", "AFLS Quote"]:
            if preferred in wb.sheetnames:
                sheet_name = preferred
                break
        if not sheet_name:
            # Find first sheet with data (skip disclaimer sheets)
            for sn in wb.sheetnames:
                ws_check = wb[sn]
                if ws_check.max_row and ws_check.max_row > 20:
                    sheet_name = sn
                    break
        if not sheet_name:
            sheet_name = wb.sheetnames[0]
            
        ws = wb[sheet_name]
        print(f"[Maersk] Parsing sheet: {sheet_name} (rows={ws.max_row})")

        contract_no = ""
        valid_start = ""
        valid_end = ""

        for r in range(1, 6):
            cell_a = str(ws.cell(r, 1).value or "")
            cell_b = str(ws.cell(r, 2).value or "")
            if "Contract Number" in cell_a:
                contract_no = cell_b.strip()
            elif "Last Acceptance Date" in cell_a or "Effective" in cell_a:
                valid_start = self._clean_date(cell_b)
            elif "Expiry Date" in cell_a or "Valid To" in cell_a:
                valid_end = self._clean_date(cell_b)

        # Detect column layout by scanning the header row
        header_row_idx = 7
        col_layout = self._detect_columns(ws, header_row_idx)
        
        rates: List[RateRow] = []
        row_counter = 1

        for r in range(header_row_idx + 1, min(ws.max_row + 1, 10000)):
            chg_type = str(ws.cell(r, col_layout["charge"]).value or "").strip().upper()
            if chg_type != "BAS":
                continue

            from_loc = str(ws.cell(r, col_layout["origin"]).value or "").strip()
            to_loc = str(ws.cell(r, col_layout["destination"]).value or "").strip()
            
            eff_dt = valid_start
            exp_dt = valid_end
            if col_layout.get("effective"):
                eff_dt = self._clean_date(ws.cell(r, col_layout["effective"]).value) or valid_start
            if col_layout.get("expiry"):
                exp_dt = self._clean_date(ws.cell(r, col_layout["expiry"]).value) or valid_end

            svc_mode = "CY/CY"
            if col_layout.get("service_mode"):
                svc_mode = str(ws.cell(r, col_layout["service_mode"]).value or "CY/CY").strip()
            
            comm = "FAK"
            if col_layout.get("commodity"):
                comm = str(ws.cell(r, col_layout["commodity"]).value or "FAK").strip()

            # Default currency from a currency column or extract from rate values
            default_curr = "USD"
            if col_layout.get("currency"):
                default_curr = str(ws.cell(r, col_layout["currency"]).value or "USD").strip().upper()

            for eq_type, col_idx in col_layout.get("containers", []):
                cell_val = ws.cell(r, col_idx).value
                if cell_val is None:
                    continue
                
                amt, curr = self._extract_amount_currency(cell_val, default_curr)
                if amt is None or amt <= 0:
                    continue

                r_row = RateRow(
                    row_index=row_counter,
                    carrier_scac="MAEU",
                    origin_raw=from_loc,
                    origin_locode=from_loc,
                    destination_raw=to_loc,
                    destination_locode=to_loc,
                    service_type=svc_mode,
                    cargo_type="FAK",
                    load_type=eq_type,
                    commodity=comm,
                    ofr_amount=amt,
                    ofr_currency=curr,
                    charges=[ChargeItem(charge_code="BAS", charge_name="Base Ocean Freight", amount=amt, currency=curr, basis="per equipment")],
                    validity_start=eff_dt,
                    validity_end=exp_dt,
                    contract_number=contract_no,
                    inclusions="",
                    remarks=""
                )
                rates.append(r_row)
                row_counter += 1

        print(f"[Maersk] Extracted {len(rates)} BAS rate rows from {sheet_name}")
        summary = JobSummary(total_rows=len(rates), carriers_found=["MAEU"])
        return CanonicalRateSheet(
            job_id=job_id,
            file_name=file_path.name,
            carrier_code="MAEU",
            contract_number=contract_no,
            validity_start=valid_start,
            validity_end=valid_end,
            rates=rates,
            summary=summary
        )

    def _detect_columns(self, ws, header_row: int) -> dict:
        """Auto-detect column layout from the header row."""
        layout = {
            "origin": 1,
            "destination": 4,
            "charge": 10,
            "containers": [],
        }
        
        headers = {}
        for c in range(1, min((ws.max_column or 1) + 1, 30)):
            val = str(ws.cell(header_row, c).value or "").strip().lower()
            if val:
                headers[c] = val

        for col_idx, h in headers.items():
            h_clean = re.sub(r'\s+', ' ', h).strip()
            
            if h_clean in ("receipt", "por", "place of receipt", "origin") or h_clean.startswith("receipt"):
                layout["origin"] = col_idx
            elif h_clean in ("delivery", "del", "place of delivery", "destination", "pod") or h_clean.startswith("delivery"):
                layout["destination"] = col_idx
            elif h_clean in ("pol",):
                layout.setdefault("pol", col_idx)
            elif h_clean in ("pod",):
                layout.setdefault("pod_col", col_idx)
            elif "effective" in h_clean:
                layout["effective"] = col_idx
            elif "expiry" in h_clean or "expire" in h_clean:
                layout["expiry"] = col_idx
            elif "service mode" in h_clean or "mode" in h_clean:
                layout["service_mode"] = col_idx
            elif "commodity" in h_clean:
                layout["commodity"] = col_idx
            elif h_clean in ("charge", "chg", "charge code"):
                layout["charge"] = col_idx
            elif h_clean in ("currency", "curr"):
                layout["currency"] = col_idx
            elif "20" in h_clean and ("dry" in h_clean or "gp" in h_clean or "dc" in h_clean or "st" in h_clean):
                layout["containers"].append(("20GP", col_idx))
            elif "40h" in h_clean or "40hd" in h_clean:
                layout["containers"].append(("40HC", col_idx))
            elif "40" in h_clean and ("dry" in h_clean or "gp" in h_clean or "dc" in h_clean or "st" in h_clean):
                layout["containers"].append(("40GP", col_idx))
            elif "45" in h_clean:
                layout["containers"].append(("45HC", col_idx))

        # Fallback: if no containers detected, use standard positions
        if not layout["containers"]:
            layout["containers"] = [("20GP", 13), ("40GP", 14), ("40HC", 15)]

        return layout

    def _extract_amount_currency(self, val, default_curr: str = "USD") -> Tuple[Optional[float], str]:
        """Extract amount and currency from values like '3800 USD' or just 3800."""
        if val is None:
            return None, default_curr
        
        s = str(val).strip()
        if not s:
            return None, default_curr
        
        # Try pure numeric first
        try:
            return float(s), default_curr
        except ValueError:
            pass
        
        # Try "amount currency" format (e.g., "3800 USD")
        match = re.match(r'^([\d.,]+)\s*([A-Z]{3})$', s.strip())
        if match:
            try:
                amt = float(match.group(1).replace(',', ''))
                return amt, match.group(2)
            except ValueError:
                pass
        
        # Try "currency amount" format
        match = re.match(r'^([A-Z]{3})\s*([\d.,]+)$', s.strip())
        if match:
            try:
                amt = float(match.group(2).replace(',', ''))
                return amt, match.group(1)
            except ValueError:
                pass
        
        return None, default_curr

    def _clean_date(self, date_val) -> str:
        if not date_val:
            return ""
        if isinstance(date_val, (datetime.datetime, datetime.date)):
            return date_val.strftime("%Y-%m-%d")
        s = str(date_val).strip()
        # Remove time component
        s = re.sub(r'\s+\d{2}:\d{2}:\d{2}.*$', '', s)
        for fmt in ["%d-%b-%Y", "%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%Y-%m-%d %H:%M:%S"]:
            try:
                dt = datetime.datetime.strptime(s, fmt)
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                pass
        return s

