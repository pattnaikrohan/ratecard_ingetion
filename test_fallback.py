import requests
import time
import os

BASE_URL = "http://127.0.0.1:8001/api"
FILE = r"D:\Rate File Template\Rate_File_Template_Completion_Freightify\RE_ Tariff Examples\AAW - AUG 2026 - CNSHA, CNTXG to NZAKL - D2, D5.pdf"

print("Uploading fallback test file...")
with open(FILE, "rb") as f:
    resp = requests.post(
        f"{BASE_URL}/upload",
        files={"file": (os.path.basename(FILE), f)},
        data={"export_policy": "PARTIAL"}
    )

job_id = resp.json()["job_id"]
print(f"Job ID: {job_id}. Waiting for completion...")

start = time.time()
while time.time() - start < 120:
    resp = requests.get(f"{BASE_URL}/jobs/{job_id}")
    status = resp.json().get("status")
    print(f"Status: {status}")
    if status not in ("QUEUED", "PARSING", "VALIDATING", "MAPPING"):
        break
    time.sleep(3)

print("Job completed. Summary:")
print(resp.json().get("summary", {}))

# Print logs
print("\n--- Logs ---")
log_resp = requests.get(f"{BASE_URL}/jobs/{job_id}/logs")
for log in log_resp.json().get("logs", []):
    print(log)
