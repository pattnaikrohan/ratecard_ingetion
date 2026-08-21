from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime

class ChargeItem(BaseModel):
    charge_code: str
    charge_name: Optional[str] = ""
    amount: float
    currency: str = "USD"
    basis: str = "per equipment"
    category: str = "Freight"  # Freight, Origin, Destination

class ValidationItem(BaseModel):
    field: str
    severity: str  # INFO, WARNING, ERROR, CRITICAL
    reason_code: str
    message: str
    suggested_value: Optional[str] = None
    ai_reasoning: Optional[str] = None

class RateRow(BaseModel):
    row_index: int
    carrier_scac: str = ""
    origin_raw: str = ""
    origin_locode: str = ""
    origin_name: str = ""
    destination_raw: str = ""
    destination_locode: str = ""
    destination_name: str = ""
    service_type: Optional[str] = ""
    cargo_type: str = "FAK"
    load_type: str = "20GP"
    commodity: Optional[str] = ""
    ofr_amount: float = 0.0
    ofr_currency: str = "USD"
    charges: List[ChargeItem] = Field(default_factory=list)
    validity_start: str = ""
    validity_end: str = ""
    contract_number: str = ""
    inclusions: Optional[str] = ""
    subject_to: Optional[str] = ""
    remarks: Optional[str] = ""
    internal_remarks: Optional[str] = ""
    validation_status: str = "VALID"  # VALID, WARNING, ERROR, CRITICAL
    validation_items: List[ValidationItem] = Field(default_factory=list)

    @property
    def validation_messages(self) -> List[str]:
        return [item.message for item in self.validation_items if item.message]

    @property
    def base_rate(self) -> float:
        return self.ofr_amount

class JobSummary(BaseModel):
    total_rows: int = 0
    valid_rows: int = 0
    warning_rows: int = 0
    error_rows: int = 0
    critical_rows: int = 0
    carriers_found: List[str] = Field(default_factory=list)
    trade_lanes_found: List[str] = Field(default_factory=list)
    contract_number: str = ""
    validity_start: str = ""
    validity_end: str = ""
    processing_time_ms: float = 0.0

class CanonicalRateSheet(BaseModel):
    job_id: str
    file_name: str
    carrier_code: str = ""
    contract_number: str = ""
    validity_start: str = ""
    validity_end: str = ""
    ai_mapping_used: bool = False
    ai_mapping_details: Optional[Dict[str, Any]] = None
    rates: List[RateRow] = Field(default_factory=list)
    summary: JobSummary = Field(default_factory=JobSummary)

class JobStatusResponse(BaseModel):
    job_id: str
    file_name: str
    file_size_bytes: int = 0
    status: str  # NEW, QUEUED, PARSING, NORMALIZING, VALIDATING, NEEDS_REVIEW, APPROVED, GENERATING, COMPLETED, FAILED
    progress: int = 0  # 0 to 100
    export_policy: str = "PARTIAL"
    summary: JobSummary = Field(default_factory=JobSummary)
    created_at: str
    updated_at: str
    logs: List[str] = Field(default_factory=list)
    output_file_name: Optional[str] = None
