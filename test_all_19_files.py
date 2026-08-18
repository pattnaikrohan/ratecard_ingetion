"""Upload all 19 test rate files and monitor processing results."""
import requests
import time
import os

BASE_URL = "http://127.0.0.1:8001/api"
TARIFF_DIR = r"D:\Rate File Template\Rate_File_Template_Completion_Freightify\RE_ Tariff Examples"

FILES = [
    "AAW - AUG 2026 - CNSHA, CNTXG to NZAKL - D2, D5.pdf",
    "AAW GLOBAL LOGISTICS_Far East (North & South & China) - Oceania (Australia & Pacific)_FAK_27 JUL-08 NOV_299424850.eml",
    "AAW Global National Import Sea LCL Tariff 1st July 2026 – 14th July 2026.xlsm",
    "AAW Import LCL Tariff 01Aug26-31Aug26.xlsx",
    "AAX SB FAK rate 15-Jul 2026 to 31-Jul 2026vt.xlsx",
    "CaroTrans LCL Export Tariff - 1st-14th August 2026.eml",
    "Fwd_ +Important+ _AUS_ Oceania MRG ex SEA to AUBP - Validity_ 01 Aug to 14 Aug 2026.eml",
    "GRI Notice - Ex NEA SEA to Australia 15 Aug 2026 - ZIM.pdf",
    "HMM - Southbound rates effective date from 1 - 14 AUGUST, 2026.eml",
    "HMM LOCAL CHARGES_ IMPORT_as of from 04-JUL-2026 Except from CHINA.pdf",
    "HMM LOCAL CHARGES_EXPORT_ as of from 04-JUL-2026.pdf",
    "LocalChargeNotice 20250815.pdf",
    "NEA – AUBP FAK Rates for 1H August Revised.eml",
    "O1N (OCE to AMR) ORA Q3.eml",
    "RE_ Adelaide to Vietnam - 40'HC ex Adelaide to Ho Chi Minh - contract no.eml",
    "RE_ Adelaide to Vietnam - 40'HC ex Adelaide to Ho Chi Minh - contract no[1].eml",
    "RE_ OOCL_AAW - 1H AUGUST 2026.eml",
    "RE_ Penske ex Savannah, GA to Brisbane AAW Global.eml",
    "SPECIAL FAK 1H August 2026 01_08 to 14_08 Revised_.eml",
]

print(f"=== Uploading {len(FILES)} rate files ===\n")

job_ids = []
for fname in FILES:
    fpath = os.path.join(TARIFF_DIR, fname)
    if not os.path.exists(fpath):
        print(f"SKIP (not found): {fname}")
        continue
    
    with open(fpath, "rb") as f:
        resp = requests.post(
            f"{BASE_URL}/upload",
            files={"file": (fname, f)},
            data={"export_policy": "PARTIAL"}
        )
    
    if resp.status_code == 200:
        data = resp.json()
        job_ids.append(data["job_id"])
        print(f"QUEUED: {fname} -> {data['job_id'][:8]}...")
    else:
        print(f"FAILED to upload: {fname} -> {resp.status_code}: {resp.text}")

print(f"\n=== {len(job_ids)} jobs submitted. Waiting for processing... ===\n")

# Poll until all jobs are done (max 5 minutes)
start = time.time()
max_wait = 300
while time.time() - start < max_wait:
    all_done = True
    for jid in job_ids:
        resp = requests.get(f"{BASE_URL}/jobs/{jid}")
        if resp.status_code == 200:
            status = resp.json().get("status", "UNKNOWN")
            if status in ("QUEUED", "PARSING", "VALIDATING", "MAPPING"):
                all_done = False
                break
    
    if all_done:
        break
    time.sleep(3)

elapsed = round(time.time() - start, 1)
print(f"Processing completed in {elapsed}s\n")

# Print results
print("=" * 100)
print(f"{'File':<65} {'Status':<15} {'Rows':<8} {'Valid':<8} {'Warn':<8} {'Err':<8}")
print("=" * 100)

total_rows = 0
total_valid = 0
total_warn = 0
total_err = 0

for jid in job_ids:
    resp = requests.get(f"{BASE_URL}/jobs/{jid}")
    if resp.status_code == 200:
        job = resp.json()
        fname = job.get("original_filename", "?")[:62]
        status = job.get("status", "?")
        summary = job.get("summary", {})
        rows = summary.get("total_rows", 0)
        valid = summary.get("valid_rows", 0)
        warn = summary.get("warning_rows", 0)
        err = summary.get("error_rows", 0) + summary.get("critical_rows", 0)
        
        total_rows += rows
        total_valid += valid
        total_warn += warn
        total_err += err
        
        print(f"{fname:<65} {status:<15} {rows:<8} {valid:<8} {warn:<8} {err:<8}")

print("=" * 100)
print(f"{'TOTALS':<65} {'':<15} {total_rows:<8} {total_valid:<8} {total_warn:<8} {total_err:<8}")

# Check learned synonyms
print("\n=== Learned Synonym Dictionary ===\n")
resp = requests.get(f"{BASE_URL}/ai/learned-synonyms")
if resp.status_code == 200:
    stats = resp.json()
    print(f"Total learned entries: {stats['total_entries']}")
    
    print("\nField Synonyms:")
    for field, count in stats.get("field_synonyms", {}).items():
        synonyms = stats["dictionary"]["field_synonyms"].get(field, [])
        print(f"  {field}: {count} entries -> {synonyms}")
    
    print("\nContainer Synonyms:")
    for ctype, count in stats.get("container_synonyms", {}).items():
        synonyms = stats["dictionary"]["container_synonyms"].get(ctype, [])
        print(f"  {ctype}: {count} entries -> {synonyms}")
else:
    print(f"Failed to get learned synonyms: {resp.status_code}")
