import os
import json
import hashlib
from typing import List, Dict, Any, Optional, Set
from app.core.config import AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_KEY, AZURE_OPENAI_DEPLOYMENT
from app.models.canonical import RateRow

CACHE_FILE = "data/ai_mapping_cache.json"
LEARNED_SYNONYMS_FILE = "data/learned_synonyms.json"

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
                temperature=0.0
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
                temperature=0.0
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
