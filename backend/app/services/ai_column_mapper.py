import os
import json
import hashlib
from typing import List, Dict, Any, Optional, Set
from app.core.config import AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_KEY, AZURE_OPENAI_DEPLOYMENT, DATA_DIR
from app.models.canonical import RateRow

CACHE_FILE = str(DATA_DIR / "ai_mapping_cache.json")
LEARNED_SYNONYMS_FILE = str(DATA_DIR / "learned_synonyms.json")

class AIColumnMapper:
    _instance = None

    def __init__(self):
        self.endpoint = AZURE_OPENAI_ENDPOINT.rstrip('/')
        self.api_key = AZURE_OPENAI_KEY
        self.deployment = AZURE_OPENAI_DEPLOYMENT
        
        self.client = None
        if self.endpoint and self.api_key:
            try:
                from openai import AzureOpenAI
                self.client = AzureOpenAI(
                    api_key=self.api_key,
                    api_version="2025-01-01-preview",
                    azure_endpoint=self.endpoint,
                    azure_deployment=self.deployment
                )
            except ImportError:
                print("[AI Mapper] openai package not installed.")
            except Exception as e:
                print(f"[AI Mapper] Client init error: {e}")
                
        self.cache = self._load_cache()
        self.learned_synonyms = self._load_learned_synonyms()

    @classmethod
    def get_instance(cls) -> "AIColumnMapper":
        if cls._instance is None:
            cls._instance = AIColumnMapper()
        return cls._instance

    # ── AI Mapping Cache ──────────────────────────────────────────────────

    def _load_cache(self) -> Dict:
        if os.path.exists(CACHE_FILE):
            try:
                with open(CACHE_FILE, "r") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def _save_cache(self):
        os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
        try:
            with open(CACHE_FILE, "w") as f:
                json.dump(self.cache, f, indent=2)
        except Exception as e:
            print(f"[AI Mapper] Failed to save cache: {e}")

    # ── Self-Learning Synonym Dictionary ──────────────────────────────────

    def _load_learned_synonyms(self) -> Dict[str, Dict[str, List[str]]]:
        """Load the learned synonyms dictionary from disk.
        
        Structure:
        {
            "field_synonyms": {
                "origin": ["pol", "port of loading", "from", ...],
                "destination": ["pod", "discharge port", ...],
                "currency": ["cur", "ccy", ...]
            },
            "container_synonyms": {
                "20GP": ["20'dc", "20ft dry", "20", ...],
                "40HC": ["40hq", "40'hc", ...],
                ...
            }
        }
        """
        if os.path.exists(LEARNED_SYNONYMS_FILE):
            try:
                with open(LEARNED_SYNONYMS_FILE, "r") as f:
                    data = json.load(f)
                    # Ensure expected structure
                    if "field_synonyms" not in data:
                        data["field_synonyms"] = {}
                    if "container_synonyms" not in data:
                        data["container_synonyms"] = {}
                    return data
            except Exception:
                pass
        return {"field_synonyms": {}, "container_synonyms": {}}

    def _save_learned_synonyms(self):
        """Persist the learned synonyms dictionary to disk."""
        os.makedirs(os.path.dirname(LEARNED_SYNONYMS_FILE), exist_ok=True)
        try:
            with open(LEARNED_SYNONYMS_FILE, "w") as f:
                json.dump(self.learned_synonyms, f, indent=2)
        except Exception as e:
            print(f"[AI Mapper] Failed to save learned synonyms: {e}")

    def _learn_from_ai_result(self, headers: List[str], ai_result: Dict[str, Any]):
        """Extract individual column name -> field mappings from a successful AI result
        and add them to the learned synonyms dictionary.
        
        Example: If headers=["POL", "POD", "20'DC"] and AI mapped col 0->origin, 
        col 1->destination, col 2->20GP, we learn:
            "pol" -> origin, "pod" -> destination, "20'dc" -> 20GP
        """
        new_learned = 0
        col_map = ai_result.get("col_map", {})
        container_cols = ai_result.get("container_cols", [])

        # Learn field synonyms (origin, destination, currency)
        for field_name, col_idx in col_map.items():
            if col_idx is None:
                continue
            col_idx = int(col_idx)
            if col_idx < 0 or col_idx >= len(headers):
                continue
            header_name = str(headers[col_idx]).strip().lower()
            if not header_name:
                continue

            if field_name not in self.learned_synonyms["field_synonyms"]:
                self.learned_synonyms["field_synonyms"][field_name] = []

            if header_name not in self.learned_synonyms["field_synonyms"][field_name]:
                self.learned_synonyms["field_synonyms"][field_name].append(header_name)
                new_learned += 1

        # Learn container type synonyms (20GP, 40HC, etc.)
        for col_idx, container_type in container_cols:
            if col_idx is None:
                continue
            col_idx = int(col_idx)
            if col_idx < 0 or col_idx >= len(headers):
                continue
            header_name = str(headers[col_idx]).strip().lower()
            if not header_name:
                continue

            if container_type not in self.learned_synonyms["container_synonyms"]:
                self.learned_synonyms["container_synonyms"][container_type] = []

            if header_name not in self.learned_synonyms["container_synonyms"][container_type]:
                self.learned_synonyms["container_synonyms"][container_type].append(header_name)
                new_learned += 1

        if new_learned > 0:
            self._save_learned_synonyms()
            total = sum(len(v) for v in self.learned_synonyms["field_synonyms"].values()) + \
                    sum(len(v) for v in self.learned_synonyms["container_synonyms"].values())
            print(f"[AI Mapper] Learned {new_learned} new synonym(s). Dictionary now has {total} total entries.")

    def get_learned_stats(self) -> Dict[str, Any]:
        """Return stats about the learned synonym dictionary (useful for Settings/UI)."""
        field_count = sum(len(v) for v in self.learned_synonyms["field_synonyms"].values())
        container_count = sum(len(v) for v in self.learned_synonyms["container_synonyms"].values())
        return {
            "total_entries": field_count + container_count,
            "field_synonyms": {k: len(v) for k, v in self.learned_synonyms["field_synonyms"].items()},
            "container_synonyms": {k: len(v) for k, v in self.learned_synonyms["container_synonyms"].items()},
            "dictionary": self.learned_synonyms
        }

    # ── Column Mapping ────────────────────────────────────────────────────
            
    def _get_fingerprint(self, headers: List[str], carrier: str) -> str:
        header_str = "|".join([str(h).strip().lower() for h in headers if h and str(h).strip()])
        raw = f"{carrier}::{header_str}"
        return hashlib.md5(raw.encode()).hexdigest()

    def map_columns(self, headers: List[str], sample_rows: List[List[str]], carrier: str) -> Optional[Dict[str, Any]]:
        if not self.client:
            print("[AI Mapper] Azure OpenAI not configured. Falling back to rule-based.")
            return None
            
        if not headers or len(headers) < 2:
            return None
            
        fingerprint = self._get_fingerprint(headers, carrier)
        if fingerprint in self.cache:
            print(f"[AI Mapper] Cache hit for carrier {carrier}")
            return self.cache[fingerprint]

        system_prompt = """You are a logistics expert mapping rate card columns to a standard Freightify extraction schema.
You will be provided with a list of column headers (0-indexed) and a few sample data rows.

Your task is to identify which column index corresponds to:
- "origin" (Port of Loading / Origin / POR)
- "destination" (Port of Discharge / Destination / POD / DEL)
- "currency"
- "charge_code" (Name of a Surcharge or Local Charge Fee, e.g., "Charge Code", "Surcharge", "Description"). 
  *Note: A table may be an Ocean Freight table OR a Local Charge table. For Local Charge tables, YOU MUST STILL map "origin" and "destination" if columns like "POR", "POL", "POD", "DEL" exist!*
- Container Types (e.g. "20GP", "40GP", "40HC", "45GP", "20RF", "40RF", "20OT", "40OT", "LCL", etc.). E.g., if a column is "20'DC" or "20", map it to "20GP".
- For LCL rates, map columns like "PER CBM", "PER TON", "MIN" etc. to their exact names (e.g., "PER CBM", "MIN") or just "LCL" if there's only one. If there are multiple LCL rate columns, include them all in container_cols (e.g., [ [<index>, "PER CBM"], [<index>, "MIN"] ]).

Return EXACTLY this JSON structure:
{
  "col_map": {
    "origin": <integer_index>,
    "destination": <integer_index>,
    "currency": <integer_index>,
    "charge_code": <integer_index>
  },
  "container_cols": [
    [<integer_index>, "20GP"],
    [<integer_index>, "40HC"]
  ],
  "reasoning": "Explain why you mapped the columns as you did."
}
Omit keys from col_map if they are not present in the headers. Do not include columns that represent dates or validity.
"""
        
        user_prompt = f"Carrier: {carrier}\nHeaders:\n{json.dumps(headers)}\n\nSample Rows:\n{json.dumps(sample_rows[:3])}"
        
        try:
            print(f"[AI Mapper] Calling Azure OpenAI GPT-4o for {carrier} mapping...")
            response = self.client.chat.completions.create(
                model=self.deployment,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.0,
                timeout=5.0
            )
            
            result_text = response.choices[0].message.content
            result_json = json.loads(result_text)
            
            # Basic validation of structure
            if "col_map" in result_json and "container_cols" in result_json:
                self.cache[fingerprint] = result_json
                self._save_cache()
                
                # Learn new synonyms from this successful mapping
                self._learn_from_ai_result(headers, result_json)
                
                return result_json
            else:
                print(f"[AI Mapper] Invalid response structure: {result_text}")
                return None
            
        except Exception as e:
            print(f"[AI Mapper] API Error: {e}")
            return None

    def resolve_ports_with_ai(self, rates: List[RateRow], carrier: str) -> List[RateRow]:
        """Use GPT-4o to resolve unmatched port names to UNLOCODEs.
        
        Collects unique unresolved origin/destination port names, sends them to AI
        in batches, and writes the resolved UNLOCODEs back into each row.
        Successfully resolved mappings are auto-learned for future files.
        """
        if not self.client:
            print("[AI Mapper] No OpenAI client configured — skipping AI port resolution")
            return rates

        from app.core.master_data import MasterDataEngine
        md = MasterDataEngine.get_instance()

        # Collect unique unresolved port names
        unresolved_origins: set = set()
        unresolved_dests: set = set()

        for r in rates:
            if r.validation_status != "WARNING":
                continue
            for item in r.validation_items:
                if item.reason_code == "unresolved_origin_port" and r.origin_raw:
                    unresolved_origins.add(r.origin_raw.strip())
                elif item.reason_code == "unresolved_dest_port" and r.destination_raw:
                    unresolved_dests.add(r.destination_raw.strip())

        all_unresolved = list(unresolved_origins | unresolved_dests)
        if not all_unresolved:
            print("[AI Mapper] No unresolved ports to resolve")
            return rates

        print(f"[AI Mapper] Resolving {len(all_unresolved)} unique unresolved port names via GPT-4o...")

        # Build a quick reference of known LOCODEs for the AI prompt
        sample_ports = list(md.ports.keys())[:200]

        # Process in batches of 50 to avoid token limits
        BATCH_SIZE = 50
        resolved_map: Dict[str, str] = {}

        for batch_start in range(0, len(all_unresolved), BATCH_SIZE):
            batch = all_unresolved[batch_start:batch_start + BATCH_SIZE]

            system_prompt = """You are an expert in ocean freight logistics and UN/LOCODEs.
You will be given a list of port names, city names, or region location codes extracted from carrier rate cards.
For each one, return the correct 5-character UN/LOCODE (e.g., CNSHA for Shanghai, AUMEL for Melbourne, KRPUS for Busan).

Rules:
- Standard UN/LOCODE format: 2-letter country code + 3-letter location code (e.g., CNSHA, SGSIN, USNYC)
- If a string has trailing asterisks or symbols (e.g., "PRDA*", "PRDB*"), strip the symbols and resolve the base code!
- If a code is a carrier region or port group alias (e.g. "PRDA", "PRDB", "THL", "DOC"), map it to the primary representative UN/LOCODE:
  * PRDA / PRDA* -> CNFOS (Pearl River Delta - Foshan)
  * PRDB / PRDB* -> CNZUH (Pearl River Delta - Zhuhai)
  * THL -> THLCH (Thailand - Laem Chabang)
  * DOC -> CNGZG (Guangzhou / China origin)
  * SPRC -> CNSHA (South Pearl River / Shanghai)
  * NPRC -> CNXMN (North Pearl River / Xiamen)
- ALWAYS provide the best representative 5-character UN/LOCODE for shipping locations!

Return a JSON object:
{
  "resolutions": {
    "Original Port Name": "LOCODE",
    "Another Port": "LOCODE"
  }
}"""

            user_prompt = f"Carrier: {carrier or 'Unknown'}\n\nPort names to resolve:\n"
            for name in batch:
                user_prompt += f"- {name}\n"
            user_prompt += f"\nReference LOCODEs from our master data (sample): {', '.join(sample_ports[:100])}"

            try:
                response = self.client.chat.completions.create(
                    model=self.deployment,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.0,
                    timeout=5.0
                )

                result_json = json.loads(response.choices[0].message.content)
                batch_resolutions = result_json.get("resolutions", {})

                for raw_name, locode in batch_resolutions.items():
                    if locode and locode != "UNKNOWN" and len(locode) == 5:
                        resolved_map[raw_name.strip()] = locode.strip().upper()

                print(f"[AI Mapper] Batch {batch_start // BATCH_SIZE + 1}: Resolved {len(batch_resolutions)} ports, {sum(1 for v in batch_resolutions.values() if v != 'UNKNOWN')} valid")

            except Exception as e:
                print(f"[AI Mapper] GPT-4o port resolution batch error: {e}")
                continue

        if not resolved_map:
            print("[AI Mapper] AI could not resolve any ports")
            return rates

        print(f"[AI Mapper] Successfully resolved {len(resolved_map)} port names via AI")

        # Apply resolutions back to rate rows
        ai_fixed_count = 0
        for r in rates:
            changed = False

            # Fix origin
            if r.origin_raw and r.origin_raw.strip() in resolved_map:
                new_locode = resolved_map[r.origin_raw.strip()]
                # Verify the LOCODE exists in master data, or accept it if it looks valid
                port_info = md.ports.get(new_locode, {})
                r.origin_locode = new_locode
                r.origin_name = port_info.get("name", r.origin_raw)
                md.learn_port(r.origin_raw, new_locode)
                changed = True

            # Fix destination
            if r.destination_raw and r.destination_raw.strip() in resolved_map:
                new_locode = resolved_map[r.destination_raw.strip()]
                port_info = md.ports.get(new_locode, {})
                r.destination_locode = new_locode
                r.destination_name = port_info.get("name", r.destination_raw)
                md.learn_port(r.destination_raw, new_locode)
                changed = True

            # If we fixed the port issues, clear old validation items and re-evaluate severity
            if changed:
                # Remove the unresolved port warnings
                r.validation_items = [
                    item for item in r.validation_items
                    if item.reason_code not in ("unresolved_origin_port", "unresolved_dest_port")
                ]
                # Add an INFO item noting the AI resolution
                from app.models.canonical import ValidationItem
                r.validation_items.append(ValidationItem(
                    field="ai_resolution",
                    severity="INFO",
                    reason_code="ai_resolved_port",
                    message=f"AI resolved ports: origin={r.origin_locode}, dest={r.destination_locode}"
                ))
                # Re-evaluate max severity
                max_sev = "VALID"
                severity_levels = {"VALID": 0, "INFO": 0, "WARNING": 1, "ERROR": 2, "CRITICAL": 3}
                for item in r.validation_items:
                    if severity_levels.get(item.severity, 0) > severity_levels.get(max_sev, 0):
                        max_sev = item.severity
                r.validation_status = max_sev
                ai_fixed_count += 1

        # Persist learned synonyms
        md.save_if_dirty()

        print(f"[AI Mapper] AI port resolution complete: {ai_fixed_count} rows upgraded from WARNING to VALID/INFO")
        return rates

    def validate_with_reasoning(self, rates: List[RateRow], carrier: str) -> List[RateRow]:
        if not self.client:
            return rates
            
        rows_to_validate = [r for r in rates if r.validation_status in ["WARNING", "ERROR", "CRITICAL"]]
        if not rows_to_validate:
            return rates
            
        # Collect unique issues
        issues_map = {}
        for r in rows_to_validate:
            for item in r.validation_items:
                key = item.message
                if key not in issues_map:
                    issues_map[key] = item
                if len(issues_map) > 20: # Cap to avoid huge prompts
                    break
            if len(issues_map) > 20:
                break
                
        if not issues_map:
            return rates

        print(f"[AI Mapper] Generating reasoning for {len(issues_map)} unique validation issues...")

        system_prompt = """You are a logistics data validation assistant.
You will be provided with a list of validation errors from a rate card ingestion process.
For each error, provide a clear, human-readable reasoning explaining what the issue is and how it might be resolved.
Use your domain knowledge of shipping (UNLOCODEs, SCACs, container types, etc.).

Return a JSON object:
{
  "reasoning": {
    "Exact Error Message String": "Your detailed explanation..."
  }
}
"""
        
        user_prompt = "Validation Issues:\n" + "\n".join([f"- {msg}" for msg in issues_map.keys()])
        
        try:
            response = self.client.chat.completions.create(
                model=self.deployment,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.0,
                timeout=5.0
            )
            
            result_json = json.loads(response.choices[0].message.content)
            reasoning_map = result_json.get("reasoning", {})
            
            for r in rates:
                if r.validation_status in ["WARNING", "ERROR", "CRITICAL"]:
                    for item in r.validation_items:
                        if item.message in reasoning_map:
                            item.ai_reasoning = reasoning_map[item.message]
                            
        except Exception as e:
            print(f"[AI Mapper] Validation Reasoning API Error: {e}")
            
        return rates

    def extract_rates_from_raw_text(self, text: str, filename: str, job_id: str, notes: Optional[str] = None) -> Optional[Any]:
        """
        Autonomous AI Extraction: When deterministic parsing cannot find standard tables,
        GPT-4o parses unstructured text, conversational emails, or non-standard documents
        directly into Canonical Rate format.
        """
        if not self.client or not text or len(text.strip()) < 10:
            return None

        print(f"[AI Extractor] Activating Autonomous AI Extraction for {filename}...")
        
        system_prompt = """You are an expert ocean freight rate extraction AI for Freightify.
Analyze the provided unstructured rate document / email / text and extract all carrier freight rates into standard JSON.

Extract the following:
1. "carrier_code": Standard 4-letter SCAC (e.g. MAEU for Maersk, OOLU for OOCL, ANNU for ANL, MSCU for MSC, CMDU for CMA CGM, ONEY for ONE, COSU for COSCO, HLCU for Hapag-Lloyd).
2. "contract_number": Service contract / agreement number if present (otherwise null).
3. "validity_start": ISO YYYY-MM-DD start date (e.g. 2026-08-01) if present (otherwise null).
4. "validity_end": ISO YYYY-MM-DD expiry date (e.g. 2026-09-30) if present (otherwise null).
5. "rates": Array of rate objects with:
   - "origin": City or port name of loading (e.g. "Fremantle", "Melbourne", "Shanghai")
   - "origin_locode": 5-character UN/LOCODE (e.g. "AUFRE", "AUMEL", "CNSHA")
   - "destination": City or port name of discharge (e.g. "Rijeka", "Auckland", "Los Angeles")
   - "destination_locode": 5-character UN/LOCODE (e.g. "HRRJK", "NZAKL", "USLAX")
   - "load_type": Standard container type ("20GP", "40GP", "40HC", "45HC", "20RF", "40RF", "20OT", "40OT", "20FR", "40FR", "20NOR", "40NOR", "LCL")
   - "ofr_amount": Base ocean freight numeric amount (e.g. 2850.0)
   - "ofr_currency": 3-letter currency code (e.g. "USD", "AUD", "NZD", "EUR")
   - "charges": Array of attached surcharge objects: [{"charge_code": "BAF", "charge_name": "Bunker", "amount": 200.0, "currency": "USD", "basis": "per equipment"}]
   - "transit_time": Transit time string (e.g. "14 Days", "7 Days") if mentioned
   - "remarks": Routing notes or routing details (e.g. "Via Singapore")
   - "inclusions": Included charges (e.g. "FCR; EBS")

Return STRICTLY this JSON structure:
{
  "carrier_code": "OOLU",
  "contract_number": "...",
  "validity_start": "YYYY-MM-DD",
  "validity_end": "YYYY-MM-DD",
  "rates": [ ... ]
}
"""

        combined_text = f"Source Document ({filename}):\n{text[:12000]}"
        if notes and notes.strip():
            combined_text += f"\n\nSupplementary Notes / Context:\n{notes.strip()}"

        try:
            response = self.client.chat.completions.create(
                model=self.deployment,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": combined_text}
                ],
                response_format={"type": "json_object"},
                temperature=0.0,
                timeout=12.0
            )

            result_json = json.loads(response.choices[0].message.content)
            raw_rates = result_json.get("rates", [])
            if not raw_rates:
                print("[AI Extractor] No rates found by AI in text.")
                return None

            from app.models.canonical import CanonicalRateSheet, RateRow, ChargeItem, JobSummary
            from app.core.master_data import MasterDataEngine
            md = MasterDataEngine.get_instance()

            carrier = result_json.get("carrier_code") or "UNKN"
            contract = result_json.get("contract_number") or ""
            val_start = result_json.get("validity_start") or ""
            val_end = result_json.get("validity_end") or ""

            parsed_rows: List[RateRow] = []
            for idx, r in enumerate(raw_rates, start=1):
                o_raw = r.get("origin") or ""
                d_raw = r.get("destination") or ""
                
                # Resolve LOCODEs through master data
                o_locode, o_name, _ = md.resolve_port(r.get("origin_locode") or o_raw)
                d_locode, d_name, _ = md.resolve_port(r.get("destination_locode") or d_raw)
                
                # Load type resolution
                lt, _ = md.resolve_load_type(r.get("load_type") or "20GP")

                # Surcharges
                charges: List[ChargeItem] = []
                for c in r.get("charges", []):
                    charges.append(ChargeItem(
                        charge_code=c.get("charge_code") or "SUR",
                        charge_name=c.get("charge_name") or c.get("charge_code") or "Surcharge",
                        amount=float(c.get("amount") or 0),
                        currency=c.get("currency") or r.get("ofr_currency") or "USD",
                        basis=c.get("basis") or "per equipment"
                    ))

                parsed_rows.append(RateRow(
                    row_index=idx,
                    carrier_scac=carrier,
                    origin_raw=o_raw,
                    origin_locode=o_locode or o_raw,
                    origin_name=o_name or o_raw,
                    destination_raw=d_raw,
                    destination_locode=d_locode or d_raw,
                    destination_name=d_name or d_raw,
                    load_type=lt,
                    ofr_amount=float(r.get("ofr_amount") or 0),
                    ofr_currency=r.get("ofr_currency") or "USD",
                    charges=charges,
                    validity_start=val_start,
                    validity_end=val_end,
                    contract_number=contract,
                    remarks=r.get("transit_time") or r.get("remarks") or "",
                    inclusions=r.get("inclusions") or ""
                ))

            print(f"[AI Extractor] Successfully extracted {len(parsed_rows)} rates via GPT-4o!")
            return CanonicalRateSheet(
                job_id=job_id,
                file_name=filename,
                carrier_code=carrier,
                contract_number=contract,
                validity_start=val_start,
                validity_end=val_end,
                rates=parsed_rows,
                summary=JobSummary(
                    total_rows=len(parsed_rows),
                    valid_rows=len(parsed_rows),
                    carriers_found=[carrier]
                )
            )

        except Exception as e:
            print(f"[AI Extractor] Error during AI extraction: {e}")
            return None
