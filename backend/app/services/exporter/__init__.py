import openpyxl
from pathlib import Path
from typing import List
from app.core.config import TEMPLATE_XLSM, PROCESSED_DIR
from app.models.canonical import CanonicalRateSheet, RateRow

class FreightifyExporter:
    def __init__(self, template_path: Path = TEMPLATE_XLSM):
        self.template_path = template_path

    def export(self, sheet: CanonicalRateSheet, output_filename: str, export_policy: str = "PARTIAL") -> Path:
        print(f"Exporting Canonical Rate Sheet ({len(sheet.rates)} rows) to Freightify Workbook {output_filename}...")
        
        # Load Freightify template preserving VBA macros
        wb = openpyxl.load_workbook(self.template_path, keep_vba=True)
        ws = wb["Template"]

        # Filter rows based on export policy
        rows_to_export: List[RateRow] = []
        for r in sheet.rates:
            if export_policy == "STRICT":
                if r.validation_status in ["VALID", "INFO", "WARNING"]:
                    rows_to_export.append(r)
            elif export_policy == "PARTIAL":
                if r.validation_status != "CRITICAL":
                    rows_to_export.append(r)
            else:  # WARNING_PERMISSIVE
                rows_to_export.append(r)

        orig_max_row = ws.max_row

        for idx, rate in enumerate(rows_to_export, start=2):
            ws.cell(row=idx, column=1, value=rate.carrier_scac)
            ws.cell(row=idx, column=2, value=rate.origin_locode)
            ws.cell(row=idx, column=3, value=rate.origin_locode)
            ws.cell(row=idx, column=5, value=rate.destination_locode)
            ws.cell(row=idx, column=7, value=rate.service_type or "")
            ws.cell(row=idx, column=8, value=rate.cargo_type or "FAK")
            ws.cell(row=idx, column=10, value=rate.commodity or "")
            ws.cell(row=idx, column=12, value=rate.inclusions or "")
            ws.cell(row=idx, column=13, value=rate.subject_to or "")
            ws.cell(row=idx, column=14, value=rate.remarks or "")
            ws.cell(row=idx, column=16, value=rate.load_type)
            ws.cell(row=idx, column=17, value=rate.validity_start)
            ws.cell(row=idx, column=18, value=rate.validity_end)
            ws.cell(row=idx, column=21, value=rate.contract_number or sheet.contract_number)
            
            # Base Ocean Freight (OFR)
            ws.cell(row=idx, column=22, value=rate.ofr_amount)
            ws.cell(row=idx, column=23, value="per equipment")
            ws.cell(row=idx, column=24, value=rate.ofr_currency or "USD")

            # Additional surcharges mapping
            for chg in rate.charges:
                if chg.charge_code in ["DOC", "DOC (Destination)"]:
                    ws.cell(row=idx, column=37, value=chg.amount)
                    ws.cell(row=idx, column=38, value=chg.basis)
                    ws.cell(row=idx, column=39, value=chg.currency)
                elif chg.charge_code in ["THC", "THC (Destination)", "DTHC"]:
                    ws.cell(row=idx, column=42, value=chg.amount)
                    ws.cell(row=idx, column=43, value=chg.basis)
                    ws.cell(row=idx, column=44, value=chg.currency)

        # Clear leftover rows from template if template originally had more rows
        last_written_row = 1 + len(rows_to_export)
        if orig_max_row > last_written_row:
            for r in range(last_written_row + 1, orig_max_row + 1):
                for c in range(1, 50):
                    ws.cell(row=r, column=c).value = None

        output_path = PROCESSED_DIR / output_filename
        wb.save(output_path)
        print(f"Exported {len(rows_to_export)} rows to {output_path}")
        return output_path
