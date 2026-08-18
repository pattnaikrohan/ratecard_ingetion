from typing import List, Tuple
from datetime import datetime
import re
from app.models.canonical import RateRow, ValidationItem
from app.core.master_data import MasterDataEngine

# Words that indicate a header row was parsed as a data row
HEADER_WORDS = {
    "origin", "destination", "pol", "pod", "por", "del",
    "load port", "discharge port", "load\nport", "discharge\nport",
    "port of loading", "port of discharge", "port of receipt", "port of delivery",
    "location", "over location", "place of receipt", "place of delivery",
    "from", "to", "via",
}

# Words that indicate a currency header, not actual currency
CURRENCY_HEADER_WORDS = {"currency", "curr.", "curr", "ccy", "cur"}

# Patterns that indicate a note/comment row, not a rate row
NOTE_PATTERNS = [
    r"all rates are charged",
    r"any shipment",
    r"surcharge will apply",
    r"important\s*note",
    r"rates are subject",
    r"please note",
    r"coload fee",
    r"overweight surcharge",
    r"high.?density",
    r"high.?volume",
    r"subject to change",
    r"minimum charge",
    r"b/l fee",
    r"effective\s+\d",
    r"validity\s*[:(]",
    r"valid\s+\(",
]
NOTE_RE = re.compile("|".join(NOTE_PATTERNS), re.IGNORECASE)


class RateValidationEngine:
    def __init__(self):
        self.md = MasterDataEngine.get_instance()

    def is_junk_row(self, row: RateRow) -> bool:
        """Detect rows that are actually headers, notes, or comments — not real rate data."""
        origin = (row.origin_raw or "").strip()
        dest = (row.destination_raw or "").strip()
        currency = (row.ofr_currency or "").strip()

        # Clean multi-line values
        origin_clean = origin.replace("\r\n", " ").replace("\n", " ").strip().lower()
        dest_clean = dest.replace("\r\n", " ").replace("\n", " ").strip().lower()

        # 1. Header row detection — origin or destination IS a header word
        if origin_clean in HEADER_WORDS or dest_clean in HEADER_WORDS:
            return True

        # 2. Currency is a header word
        if currency.strip().upper() in {w.upper() for w in CURRENCY_HEADER_WORDS}:
            return True

        # 3. Note/comment row — long text in origin that matches note patterns
        if len(origin) > 50 and NOTE_RE.search(origin):
            return True
        if len(dest) > 50 and NOTE_RE.search(dest):
            return True

        # 4. Origin or destination is extremely long text (>100 chars) with no port-like content
        if len(origin) > 100 and not self._looks_like_port(origin):
            return True
        if len(dest) > 100 and not self._looks_like_port(dest):
            return True

        # 5. Surcharge / Add-on table rows (e.g. "CLASS 1", "PSA Group 1", "DG Class", "ONE Bunker Surcharge")
        if re.match(r'^(class\s*[\d\.]|psa\s*group|dg\s*class)', origin_clean):
            return True

        # 6. Pure numeric origin or destination (e.g. "2400", "2600", "3100") is a price/value range from secondary tables, not a port!
        if re.match(r'^\d+$', origin_clean) or re.match(r'^\d+$', dest_clean):
            return True

        # 7. Container type/size in destination (e.g. "20'", "40'", "40hc", "20") is a column header, not a port!
        if dest_clean in {"20'", "40'", "40hc", "45hc", "20gp", "40gp", "20", "40", "45", "20'rad", "40'rad"}:
            return True

        # 8. Surcharge table names or price values misaligned into origin/destination
        if any(kw in origin_clean for kw in ["bunker surcharge", "cargo value", "add-on", "addon", "tariff", "value range", "terms & conditions"]):
            return True
        if any(kw in dest_clean for kw in ["bunker surcharge", "cargo value", "add-on", "addon", "tariff", "value range", "usd301"]):
            return True
            
        # 9. Misaligned columns from secondary tables (e.g. price in destination column)
        if dest_clean.startswith("usd ") or "do not accept" in dest_clean:
            return True

        return False

    def _looks_like_port(self, text: str) -> bool:
        """Quick heuristic: does this text look like it could be a port name?"""
        clean = text.strip().upper()
        # Short text is likely a port
        if len(clean) <= 30:
            return True
        # Contains a known LOCODE pattern (2 letter country + 3 letter code)
        if re.search(r'\b[A-Z]{2}[A-Z]{3}\b', clean):
            return True
        # Check against master data
        _, _, valid = self.md.resolve_port(clean[:50])
        return valid

    def validate_row(self, row: RateRow) -> RateRow:
        items: List[ValidationItem] = []
        max_severity = "VALID"

        # 1. Validate Carrier SCAC
        scac, valid_carrier = self.md.resolve_carrier(row.carrier_scac)
        if not valid_carrier:
            items.append(ValidationItem(field="carrier_scac", severity="WARNING", reason_code="unknown_scac", message=f"SCAC '{row.carrier_scac}' not in Master Data — may be a valid new carrier"))
            max_severity = self._escalate(max_severity, "WARNING")
        else:
            row.carrier_scac = scac

        # 2. Validate & Resolve Origin Port
        orig_input = row.origin_locode or row.origin_raw
        if orig_input:
            # Check if it's a destination group
            if self.md.is_destination_group(orig_input):
                # Origin groups are unusual but valid — use first port as representative
                locodes = self.md.expand_destination_group(orig_input)
                if locodes:
                    row.origin_locode = locodes[0]
                    row.origin_name = orig_input
                    items.append(ValidationItem(field="origin_locode", severity="INFO", reason_code="group_origin", message=f"Origin group '{orig_input}' resolved to '{locodes[0]}'"))
            else:
                orig_locode, orig_name, valid_orig = self.md.resolve_port(orig_input)
                if not valid_orig:
                    items.append(ValidationItem(field="origin_locode", severity="WARNING", reason_code="unresolved_origin_port", message=f"Origin Port '{row.origin_raw}' not auto-resolved — may need manual mapping"))
                    max_severity = self._escalate(max_severity, "WARNING")
                else:
                    if orig_locode != row.origin_locode:
                        items.append(ValidationItem(field="origin_locode", severity="INFO", reason_code="resolved_origin", message=f"Resolved origin '{row.origin_raw}' to UNLOCODE '{orig_locode}'"))
                    row.origin_locode = orig_locode
                    row.origin_name = orig_name
                    # Auto-learn this resolution
                    if row.origin_raw and orig_locode:
                        self.md.learn_port(row.origin_raw, orig_locode)
        else:
            items.append(ValidationItem(field="origin_locode", severity="WARNING", reason_code="missing_origin", message="Origin port is empty"))
            max_severity = self._escalate(max_severity, "WARNING")

        # 3. Validate & Resolve Destination Port
        dest_input = row.destination_locode or row.destination_raw
        if dest_input:
            # Check if it's a destination group — this is common (e.g., "AUS MAIN PORTS")
            if self.md.is_destination_group(dest_input):
                # Mark as valid — the job_manager will expand this into multiple rows
                row.destination_name = dest_input
                first_locode = self.md.expand_destination_group(dest_input)[0]
                row.destination_locode = first_locode
                items.append(ValidationItem(field="destination_locode", severity="INFO", reason_code="destination_group", message=f"Destination group '{dest_input}' will be expanded to multiple ports"))
            else:
                dest_locode, dest_name, valid_dest = self.md.resolve_port(dest_input)
                if not valid_dest:
                    items.append(ValidationItem(field="destination_locode", severity="WARNING", reason_code="unresolved_dest_port", message=f"Destination Port '{row.destination_raw}' not auto-resolved — may need manual mapping"))
                    max_severity = self._escalate(max_severity, "WARNING")
                else:
                    if dest_locode != row.destination_locode:
                        items.append(ValidationItem(field="destination_locode", severity="INFO", reason_code="resolved_dest", message=f"Resolved destination '{row.destination_raw}' to UNLOCODE '{dest_locode}'"))
                    row.destination_locode = dest_locode
                    row.destination_name = dest_name
                    # Auto-learn this resolution
                    if row.destination_raw and dest_locode:
                        self.md.learn_port(row.destination_raw, dest_locode)
        else:
            items.append(ValidationItem(field="destination_locode", severity="WARNING", reason_code="missing_destination", message="Destination port is empty"))
            max_severity = self._escalate(max_severity, "WARNING")

        # 4. Validate Load Type
        load_type, valid_load = self.md.resolve_load_type(row.load_type)
        if not valid_load:
            items.append(ValidationItem(field="load_type", severity="WARNING", reason_code="unknown_load_type", message=f"Load type '{row.load_type}' mapped to standard '{load_type}'"))
            max_severity = self._escalate(max_severity, "WARNING")
        row.load_type = load_type

        # 5. Validate Currency
        if not self.md.is_valid_currency(row.ofr_currency):
            items.append(ValidationItem(field="ofr_currency", severity="WARNING", reason_code="unknown_currency", message=f"Currency '{row.ofr_currency}' not in Freightify standard list"))
            max_severity = self._escalate(max_severity, "WARNING")

        # 6. Validate OFR Amount
        if row.ofr_amount <= 0:
            items.append(ValidationItem(field="ofr_amount", severity="CRITICAL", reason_code="zero_or_negative_rate", message=f"OFR amount ${row.ofr_amount} is zero or negative"))
            max_severity = self._escalate(max_severity, "CRITICAL")

        # 7. Validate Date Range (downgraded to INFO — missing dates are common and not critical)
        if not self._is_valid_date(row.validity_start) or not self._is_valid_date(row.validity_end):
            if row.validity_start or row.validity_end:
                items.append(ValidationItem(field="validity_start", severity="INFO", reason_code="date_format_note", message="Dates should be formatted as YYYY-MM-DD"))

        row.validation_status = max_severity
        row.validation_items = items
        return row

    def expand_destination_groups(self, rates: List[RateRow]) -> List[RateRow]:
        """
        Expand rate rows that have destination group aliases (e.g., 'AUS MAIN PORTS')
        into multiple rows, one per actual port in the group.
        """
        expanded: List[RateRow] = []
        next_idx = max((r.row_index for r in rates), default=0) + 1

        for row in rates:
            dest_input = row.destination_raw or row.destination_locode
            if dest_input and self.md.is_destination_group(dest_input):
                locodes = self.md.expand_destination_group(dest_input)
                for locode in locodes:
                    port_info = self.md.ports.get(locode, {})
                    new_row = row.model_copy()
                    new_row.row_index = next_idx
                    new_row.destination_locode = locode
                    new_row.destination_name = port_info.get("name", locode)
                    new_row.destination_raw = row.destination_raw  # Keep original for reference
                    next_idx += 1
                    expanded.append(new_row)
            else:
                expanded.append(row)

        # Also expand origin groups (less common but possible)
        final: List[RateRow] = []
        for row in expanded:
            orig_input = row.origin_raw or row.origin_locode
            if orig_input and self.md.is_destination_group(orig_input):
                locodes = self.md.expand_destination_group(orig_input)
                for locode in locodes:
                    port_info = self.md.ports.get(locode, {})
                    new_row = row.model_copy()
                    new_row.row_index = next_idx
                    new_row.origin_locode = locode
                    new_row.origin_name = port_info.get("name", locode)
                    new_row.origin_raw = row.origin_raw
                    next_idx += 1
                    final.append(new_row)
            else:
                final.append(row)

        return final

    def _is_valid_date(self, date_str: str) -> bool:
        if not date_str:
            return True
        try:
            datetime.strptime(date_str, "%Y-%m-%d")
            return True
        except ValueError:
            return False

    def _escalate(self, current: str, new_sev: str) -> str:
        levels = {"VALID": 0, "INFO": 0, "WARNING": 1, "ERROR": 2, "CRITICAL": 3}
        if levels.get(new_sev, 0) > levels.get(current, 0):
            return new_sev
        return current
