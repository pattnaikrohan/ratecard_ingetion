"""
Test runner for files from 12th file (index 11) to end (19).
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import os
import time
import requests

API_BASE = "http://localhost:8000"
TARIFF_DIR = r"D:\Rate File Template\Rate_File_Template_Completion_Freightify\RE_ Tariff Examples"

def get_all_files():
    files = []
    for fn in sorted(os.listdir(TARIFF_DIR)):
        fp = os.path.join(TARIFF_DIR, fn)
        if os.path.isfile(fp):
            files.append((fn, fp))
    return files

def upload_file(filepath, filename):
    with open(filepath, "rb") as f:
        resp = requests.post(
            f"{API_BASE}/api/upload",
            files={"file": (filename, f)},
            data={"export_policy": "PARTIAL"},
            timeout=30
        )
    if resp.status_code != 200:
        return None
    return resp.json().get("job_id")

def wait_for_job(job_id, max_wait=120):
    for _ in range(max_wait):
        resp = requests.get(f"{API_BASE}/api/jobs/{job_id}")
        if resp.status_code != 200:
            time.sleep(1)
            continue
        data = resp.json()
        status = data.get("status", "")
        if status in ("COMPLETED", "APPROVED", "NEEDS_REVIEW", "FAILED"):
            return data
        time.sleep(1)
    return None

def main():
    all_files = get_all_files()
    files = all_files[11:]  # Start from 12th file (index 11)

    print(f"\n{'='*90}")
    print(f" TESTING TARIFF FILES FROM 12th FILE TO 19th FILE ({len(files)} files)")
    print(f"{'='*90}\n")

    results = []
    for i, (fn, fp) in enumerate(files, start=12):
        print(f"[{i:2d}/{len(all_files)}] {fn[:70]}...", end=" ", flush=True)

        job_id = upload_file(fp, fn)
        if not job_id:
            print("UPLOAD FAILED")
            results.append((fn, "UPLOAD_FAILED", 0, 0, 0, 0, ""))
            continue

        data = wait_for_job(job_id)
        if not data:
            print("TIMEOUT")
            results.append((fn, "TIMEOUT", 0, 0, 0, 0, ""))
            continue

        status = data.get("status", "UNKNOWN")
        summary = data.get("summary", {})
        total = summary.get("total_rows", 0)
        valid = summary.get("valid_rows", 0)
        warns = summary.get("warning_rows", 0)
        errors = summary.get("error_rows", 0)
        crits = summary.get("critical_rows", 0)
        output = data.get("output_file_name", "")

        icon = "[OK]" if status in ("COMPLETED", "APPROVED") else ("[!!" if status == "NEEDS_REVIEW" else "[XX]")

        print(f"{icon} {status:15s} | {total:5d} rows | V:{valid} W:{warns} E:{errors} C:{crits}")
        results.append((fn, status, total, valid, warns, errors, output))

    print(f"\n{'='*90}")
    print(f" SUMMARY (Files 12-19)")
    print(f"{'='*90}")

    statuses = {}
    for fn, status, total, valid, warns, errors, output in results:
        statuses[status] = statuses.get(status, 0) + 1

    for status, count in sorted(statuses.items()):
        print(f"  {status:20s}: {count}")

    total_rows = sum(r[2] for r in results)
    total_valid = sum(r[3] for r in results)
    print(f"\n  Total rows extracted: {total_rows}")
    print(f"  Total valid rows:    {total_valid}")
    print(f"\n{'='*90}")

if __name__ == "__main__":
    main()
