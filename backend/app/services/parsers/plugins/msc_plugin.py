"""
MSC Plugin — Parses MSC rate announcements from HTML email bodies.
Extracts rate tables from HTML <table> elements in the email body.
Also handles MSC PDF attachments via Azure DocIntel when applicable.
"""
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import List, Optional, Tuple
from app.services.parsers.base_parser import BaseParser
from app.models.canonical import CanonicalRateSheet, RateRow, ChargeItem, JobSummary


class _HTMLTableExtractor(HTMLParser):
    """Extracts all HTML tables as list of list of list of strings."""

    def __init__(self):
        super().__init__()
        self.tables: List[List[List[str]]] = []
        self.current_table: List[List[str]] = []
        self.current_row: List[str] = []
        self.current_cell: str = ""
        self.depth = 0
        self.in_row = False
        self.in_cell = False

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self.depth += 1
            if self.depth == 1:
                self.current_table = []
        elif tag == "tr" and self.depth:
            self.in_row = True
            self.current_row = []
        elif tag in ("td", "th") and self.in_row:
            self.in_cell = True
            self.current_cell = ""
        elif tag == "br" and self.in_cell:
            self.current_cell += " "

    def handle_endtag(self, tag):
        if tag == "table":
            if self.depth == 1 and self.current_table:
                self.tables.append(self.current_table)
            self.depth = max(0, self.depth - 1)
        elif tag == "tr" and self.in_row:
            if self.current_row:
                self.current_table.append(self.current_row)
            self.in_row = False
        elif tag in ("td", "th") and self.in_cell:
            self.current_row.append(self.current_cell.strip())
            self.in_cell = False

    def handle_data(self, data):
        if self.in_cell:
            self.current_cell += data

    def handle_entityref(self, name):
        if self.in_cell:
            self.current_cell += " "

    def handle_charref(self, name):
        if self.in_cell:
            try:
                self.current_cell += chr(int(name))
            except (ValueError, OverflowError):
                self.current_cell += " "


# Region/country/port synonym maps for abbreviations used in MSC emails
REGION_PORTS = {
    "nea": ["North East Asia Ports"],
    "sea": ["South East Asia Ports"],
    "sg": ["SGSIN"],
    "id": ["IDJKT"],
    "th": ["THLCH"],
    "my": ["MYPKG"],
    "vn": ["VNSGN"],
    "ph": ["PHMNL"],
    "kh": ["KHKOS"],
    "tw": ["TWKHH"],
    "hk": ["HKHKG"],
    "cn": ["CNSHA"],
    "kr": ["KRPUS"],
    "jp": ["JPTYO"],
    "in": ["INNSA"],
    "bd": ["BDCGP"],
    "lk": ["LKCMB"],
    "pk": ["PKKAR"],
}

DEST_PORTS = {
    "auec": ["AUSYD", "AUMEL", "AUBNE"],  # Australia East Coast
    "auwc": ["AUFRE", "AUADL"],  # Australia West Coast
    "aubp": ["AUSYD", "AUMEL", "AUBNE", "AUFRE", "AUADL"],  # Australia Base Ports
    "aus": ["AUSYD", "AUMEL", "AUBNE", "AUFRE", "AUADL"],
    "nz": ["NZAKL", "NZWLG", "NZLYT"],
}


def _extract_amount(val: str) -> Optional[float]:
    """Extracts numeric amount from a cell string."""
    if not val:
        return None
    s = val.strip().replace('$', '').replace(',', '').replace(' ', '')
    s = re.sub(r'/teu|/cbm|/w/m|/box|/ctr|per.*', '', s, flags=re.IGNORECASE)
    try:
        amt = float(s)
        return amt if amt > 0 else None
    except ValueError:
        digits = re.findall(r'\d+\.?\d*', s)
        if digits:
            try:
                return float(digits[0])
            except ValueError:
                return None
    return None


class MSCPlugin(BaseParser):
    def can_parse(self, file_path: Path, filename: str) -> bool:
        fn = filename.lower()
        return "msc" in fn or "mscu" in fn

    def parse_text(self, text_content: str, filename: str, job_id: str) -> CanonicalRateSheet:
        """Parse rate tables from HTML email body text."""
        print(f"[MSC Plugin] Parsing HTML email body for rate tables: {filename}")

        # Extract validity from text
        validity_start = ""
        validity_end = ""
        val_match = re.search(
            r'(?:valid|validity|effective)[:\s(]*(\d{1,2}\s*(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*[\s,]*\d{2,4})'
            r'[^)]*?(?:to|–|-|—|~)\s*(\d{1,2}\s*(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*[\s,]*\d{2,4})',
            text_content, re.IGNORECASE
        )
        if val_match:
            validity_start = self._parse_date(val_match.group(1))
            validity_end = self._parse_date(val_match.group(2))

        # Also try simpler pattern: "1 August – 14 August" or "(1 August – 14 August)"
        if not validity_start:
            val_match2 = re.search(
                r'(\d{1,2}\s+(?:january|february|march|april|may|june|july|august|september|october|november|december))'
                r'\s*(?:–|-|—|to)\s*(\d{1,2}\s+(?:january|february|march|april|may|june|july|august|september|october|november|december))',
                text_content, re.IGNORECASE
            )
            if val_match2:
                # Try to find year nearby
                year_match = re.search(r'20\d{2}', text_content)
                year = year_match.group() if year_match else "2026"
                validity_start = self._parse_date(val_match2.group(1) + " " + year)
                validity_end = self._parse_date(val_match2.group(2) + " " + year)

        # Extract HTML tables
        extractor = _HTMLTableExtractor()
        extractor.feed(text_content)

        rates: List[RateRow] = []
        row_counter = 1

        for table in extractor.tables:
            if len(table) < 2:
                continue

            # Check if this table is a vessel schedule or rating date table (and skip if so)
            table_title = " ".join([" ".join(r) for r in table[:2]]).lower()
            if any(kw in table_title for kw in ["vessel", "voyage", "fixed rating date", "external sender", "vvd", "partner"]):
                continue

            # Check if header row contains port codes as column headers (e.g. ['PUS', 'SHA', 'NGB', 'TAO', 'YTN', 'Validity'])
            headers = [c.strip().upper() for c in table[0]]
            data_rows = table[1:]

            # Try parsing column-header origin matrix first (e.g. HMM rate matrix)
            column_header_found = False
            for d_row in data_rows:
                for c_idx, cell_val in enumerate(d_row):
                    if c_idx >= len(headers):
                        continue
                    col_hdr = headers[c_idx]
                    if not col_hdr or col_hdr in ("VALIDITY", "EFFECTIVE", "REMARKS", ""):
                        continue
                    
                    amt_match = re.search(r'\$?(\d{3,5}(?:\.\d{2})?)', cell_val)
                    if amt_match:
                        amt = float(amt_match.group(1))
                        if amt > 100:
                            column_header_found = True
                            orig_key = col_hdr.lower()
                            origin_ports = REGION_PORTS.get(orig_key, [col_hdr])
                            dest_ports = DEST_PORTS.get("aubp", ["AUSYD", "AUMEL", "AUBNE", "AUFRE", "AUADL"])
                            
                            for orig in origin_ports:
                                for dest in dest_ports:
                                    for ct in ["20GP", "40GP", "40HC"]:
                                        ct_amount = amt if ct == "20GP" else amt * 2
                                        rates.append(RateRow(
                                            row_index=row_counter,
                                            carrier_scac="HMMU" if "hmm" in filename.lower() else "MSCU",
                                            origin_raw=orig,
                                            origin_locode=orig if len(orig) == 5 else "",
                                            destination_raw=dest,
                                            destination_locode=dest if len(dest) == 5 else "",
                                            cargo_type="FAK",
                                            load_type=ct,
                                            commodity="FAK",
                                            ofr_amount=ct_amount,
                                            ofr_currency="USD",
                                            validity_start=validity_start,
                                            validity_end=validity_end,
                                            remarks=f"Southbound Rate Table",
                                        ))
                                        row_counter += 1

            if column_header_found:
                continue

            # Check if this looks like a standard rate table (has numeric amounts)
            has_amounts = False
            for row in table[1:]:
                for cell in row:
                    if _extract_amount(cell) is not None:
                        has_amounts = True
                        break
                if has_amounts:
                    break

            if not has_amounts:
                continue

            # Try to identify origin/destination/rate columns
            for row in table:
                # Skip header-like rows
                if len(row) < 3:
                    continue

                origin_raw = ""
                dest_raw = ""
                amount = None
                currency = "USD"
                unit = "/teu"

                for i, cell in enumerate(row):
                    cell_clean = cell.strip().upper()

                    # Currency detection
                    if cell_clean in ("USD", "EUR", "AUD", "CNY", "GBP", "NZD"):
                        currency = cell_clean
                        continue

                    # Unit detection
                    if cell_clean.startswith("/") or cell_clean.startswith("PER"):
                        unit = cell_clean.lower()
                        continue

                    # Amount detection
                    amt = _extract_amount(cell)
                    if amt is not None and amt > 10:
                        amount = amt
                        continue

                    # Region/port detection
                    cl = cell_clean.lower().strip()
                    if cl in REGION_PORTS or cl in DEST_PORTS:
                        if not origin_raw:
                            origin_raw = cl
                        elif not dest_raw:
                            dest_raw = cl
                    elif " to " in cl:
                        parts = cl.split(" to ")
                        if len(parts) == 2:
                            origin_raw = parts[0].strip()
                            dest_raw = parts[1].strip()
                    elif cl and not origin_raw and len(cl) <= 10:
                        origin_raw = cl
                    elif cl and origin_raw and not dest_raw and len(cl) <= 10:
                        dest_raw = cl

                if not origin_raw or amount is None:
                    continue

                # Expand origins
                origin_ports = REGION_PORTS.get(origin_raw, [origin_raw.upper()])
                # Expand destinations
                dest_ports = DEST_PORTS.get(dest_raw, [dest_raw.upper()] if dest_raw else ["AUBP"])

                # Determine load type from unit
                load_type = "20GP"  # /teu = 20GP equivalent
                container_types = ["20GP", "40GP", "40HC"]
                if "/cbm" in unit or "/w/m" in unit:
                    container_types = ["LCL"]

                for orig in origin_ports:
                    for dest in dest_ports:
                        for ct in container_types:
                            # For /teu pricing, 40' is typically 2x 20'
                            ct_amount = amount
                            if ct in ("40GP", "40HC") and "/teu" in unit:
                                ct_amount = amount * 2

                            rates.append(RateRow(
                                row_index=row_counter,
                                carrier_scac="MSCU",
                                origin_raw=orig,
                                origin_locode=orig if len(orig) == 5 else "",
                                destination_raw=dest,
                                destination_locode=dest if len(dest) == 5 else "",
                                cargo_type="FAK",
                                load_type=ct,
                                commodity="FAK",
                                ofr_amount=ct_amount,
                                ofr_currency=currency,
                                validity_start=validity_start,
                                validity_end=validity_end,
                                contract_number="",
                                remarks=f"MSC Special FAK Rate ({unit})",
                            ))
                            row_counter += 1

        print(f"[MSC Plugin] Extracted {len(rates)} rate rows from HTML body")

        summary = JobSummary(total_rows=len(rates), carriers_found=["MSCU"])
        return CanonicalRateSheet(
            job_id=job_id,
            file_name=filename,
            carrier_code="MSCU",
            contract_number="",
            validity_start=validity_start,
            validity_end=validity_end,
            rates=rates,
            summary=summary,
        )

    def parse(self, file_path: Path, job_id: str) -> CanonicalRateSheet:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        return self.parse_text(content, file_path.name, job_id)

    def _parse_date(self, date_str: str) -> str:
        """Parse a date string into YYYY-MM-DD."""
        import datetime
        s = date_str.strip()
        for fmt in ["%d %B %Y", "%d %b %Y", "%d-%b-%Y", "%d/%m/%Y",
                     "%B %d, %Y", "%b %d, %Y", "%Y-%m-%d"]:
            try:
                dt = datetime.datetime.strptime(s, fmt)
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                continue
        return s
