import sys
sys.stdout.reconfigure(encoding='utf-8')
import re
from pathlib import Path

# Simulate the parser logic
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
LCL_RATE_SYNONYMS = {
    "rate per cbm", "rate per tonne", "rate per w/m", "ocean freight rate",
    "ocean freight", "ofr", "minimum charge", "rate",
}

def _normalize(s):
    return re.sub(r'\s+', ' ', s.strip()).lower()

def _match_synonym(header, synonyms):
    h = _normalize(header)
    return h in synonyms or any(syn in h for syn in synonyms if len(syn) > 2)

def _match_lcl_rate(header):
    h = _normalize(header)
    return h in LCL_RATE_SYNONYMS or any(syn in h for syn in LCL_RATE_SYNONYMS if len(syn) > 3)

# Row 7 headers from Tariff sheet
row7 = ['', 'POA-POD-VIA Port', 'POA-POD', 'POD-VIA Port', 'Region', 'Country', 'Origin Port', 'Destination Port', 'concatenate', 'Port Code', 'VIA Port', 'VIA Country', 'Service Type', 'CFS / Gateway', 'Currency', 'Rate per cbm', 'Rate per tonne', 'Minimum Charge', 'GRI per w/m']

print("Testing header matching for LCL tariff Row 7:")
origin_found = False
dest_found = False
lcl_found = False
for idx, h in enumerate(row7):
    if not h:
        continue
    if _match_synonym(h, ORIGIN_SYNONYMS):
        print(f"  Col {idx+1}: '{h}' -> ORIGIN match")
        origin_found = True
    if _match_synonym(h, DESTINATION_SYNONYMS):
        print(f"  Col {idx+1}: '{h}' -> DESTINATION match")
        dest_found = True
    if _match_lcl_rate(h):
        print(f"  Col {idx+1}: '{h}' -> LCL_RATE match")
        lcl_found = True

print(f"\nResult: origin_found={origin_found}, dest_found={dest_found}, lcl_found={lcl_found}")
print(f"Would match: {(origin_found or dest_found) and lcl_found}")
