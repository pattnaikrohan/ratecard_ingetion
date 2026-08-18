import os
import openpyxl
from pathlib import Path
from typing import List
from app.core.config import TEMPLATE_XLSM, PROCESSED_DIR
from app.models.canonical import CanonicalRateSheet, RateRow

class FreightifyExporter:
    def __init__(self, template_path: Path = TEMPLATE_XLSM):
        self.template_path = template_path
        self.clean_template_path = PROCESSED_DIR / "clean_template.xlsm"

    def _ensure_clean_template(self) -> Path:
        """Create a lightweight macro-enabled template containing ONLY the 'Template' sheet."""
        if self.clean_template_path.exists():
            return self.clean_template_path

        PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
        print(f"[Exporter] Generating clean export template at {self.clean_template_path}...")
        try:
            wb = openpyxl.load_workbook(self.template_path, keep_vba=True)
            for s in list(wb.sheetnames):
                if s != "Template":
                    del wb[s]
            wb.save(self.clean_template_path)
            print(f"[Exporter] Clean template created successfully ({self.clean_template_path.stat().st_size / 1024:.1f} KB)")
            return self.clean_template_path
        except Exception as e:
            print(f"[Exporter] Failed to create clean template: {e}, falling back to original")
            return self.template_path

    def export(self, sheet: CanonicalRateSheet, output_filename: str, export_policy: str = "PARTIAL") -> Path:
        print(f"Exporting Canonical Rate Sheet ({len(sheet.rates)} rows) to Freightify Workbook {output_filename}...")
        
        # Load lightweight clean template (0.6s load time vs 16.5s original)
        template_file = self._ensure_clean_template()
        wb = openpyxl.load_workbook(template_file, keep_vba=True)
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

        output_path = PROCESSED_DIR / output_filename
        wb.save(output_path)
        print(f"Exported {len(rows_to_export)} rows to {output_path}")
        return output_path
