import sqlite3
import json
import time
import os
from pathlib import Path
from typing import Dict, Any, List, Optional
from app.core.config import DB_PATH
from app.models.canonical import JobStatusResponse, CanonicalRateSheet, JobSummary

class DatabaseManager:
    _instance = None

    def __init__(self, db_path: str = str(DB_PATH)):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        self.restore_from_blob()

    @classmethod
    def get_instance(cls) -> "DatabaseManager":
        if cls._instance is None:
            cls._instance = DatabaseManager()
        return cls._instance

    def _get_conn(self):
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                job_id TEXT PRIMARY KEY,
                file_name TEXT NOT NULL,
                file_size_bytes INTEGER DEFAULT 0,
                status TEXT NOT NULL,
                progress INTEGER DEFAULT 0,
                export_policy TEXT DEFAULT 'PARTIAL',
                summary_json TEXT,
                canonical_json TEXT,
                logs_json TEXT,
                output_file_name TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """)
            conn.commit()

    def backup_to_blob(self):
        """Upload current SQLite DB to Azure Blob Storage with robust retry and timeout."""
        from app.services.storage import StorageService
        blob_client = StorageService._get_blob_client("rate_agent.db")
        if blob_client and self.db_path.exists() and self.db_path.stat().st_size > 0:
            try:
                with open(self.db_path, "rb") as data:
                    blob_client.upload_blob(data, overwrite=True, timeout=15)
                print("[Storage] Backed up rate_agent.db to Azure Blob Storage successfully.")
            except Exception as e:
                print(f"[Storage] Warning: Failed to backup DB to Azure Blob: {e}")

    def restore_from_blob(self):
        """Restore SQLite DB from Azure Blob Storage if blob contains more recent/populated records."""
        from app.services.storage import StorageService
        blob_client = StorageService._get_blob_client("rate_agent.db")
        if not blob_client:
            return

        try:
            if not blob_client.exists(timeout=10):
                return

            local_job_count = 0
            if self.db_path.exists():
                try:
                    with self._get_conn() as conn:
                        cursor = conn.cursor()
                        cursor.execute("SELECT COUNT(*) FROM jobs")
                        local_job_count = cursor.fetchone()[0]
                except Exception:
                    local_job_count = 0

            # If local has 0 records, download the cloud version
            if local_job_count == 0:
                print("[Storage] Local DB empty — downloading persisted rate_agent.db from Azure Blob...")
                blob_data = blob_client.download_blob(timeout=15).readall()
                if len(blob_data) > 0:
                    with open(self.db_path, "wb") as f:
                        f.write(blob_data)
                    print(f"[Storage] Successfully restored SQLite DB ({len(blob_data)} bytes) from Azure Blob Storage.")
        except Exception as e:
            print(f"[Storage] Warning: Failed to restore DB from Azure Blob: {e}")

    def create_job(self, job_id: str, file_name: str, file_size: int, export_policy: str = "PARTIAL") -> JobStatusResponse:
        now = datetime_now_iso()
        summary = JobSummary()
        logs = [f"[{now}] Job initialized for file: {file_name}"]
        
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO jobs (job_id, file_name, file_size_bytes, status, progress, export_policy, summary_json, logs_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (job_id, file_name, file_size, "NEW", 0, export_policy, json.dumps(summary.model_dump()), json.dumps(logs), now, now))
            conn.commit()

        # Backup state to Azure
        import threading
        threading.Thread(target=self.backup_to_blob, daemon=True).start()
            
        return JobStatusResponse(
            job_id=job_id,
            file_name=file_name,
            file_size_bytes=file_size,
            status="NEW",
            progress=0,
            export_policy=export_policy,
            summary=summary,
            created_at=now,
            updated_at=now,
            logs=logs
        )

    def update_job_status(self, job_id: str, status: str, progress: int = None, log_msg: str = None, canonical_sheet: CanonicalRateSheet = None, output_file: str = None):
        now = datetime_now_iso()
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT logs_json, progress FROM jobs WHERE job_id = ?", (job_id,))
            row = cursor.fetchone()
            if not row:
                return
            
            logs = json.loads(row["logs_json"]) if row["logs_json"] else []
            if log_msg:
                logs.append(f"[{now}] {log_msg}")
            
            p = progress if progress is not None else row["progress"]
            
            sql = "UPDATE jobs SET status = ?, progress = ?, logs_json = ?, updated_at = ?"
            params = [status, p, json.dumps(logs), now]
            
            if canonical_sheet:
                sql += ", canonical_json = ?, summary_json = ?"
                params.extend([json.dumps(canonical_sheet.model_dump()), json.dumps(canonical_sheet.summary.model_dump())])
            
            if output_file:
                sql += ", output_file_name = ?"
                params.append(output_file)
                
            sql += " WHERE job_id = ?"
            params.append(job_id)
            
            cursor.execute(sql, params)
            conn.commit()

        # Backup on completion or important status transitions
        if status in ["COMPLETED", "FAILED", "APPROVED", "NEEDS_REVIEW", "VALIDATING"] or progress == 100:
             import threading
             threading.Thread(target=self.backup_to_blob, daemon=True).start()

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,))
            row = cursor.fetchone()
            if not row:
                return None
            
            res = dict(row)
            res["summary"] = json.loads(res["summary_json"]) if res["summary_json"] else {}
            res["canonical"] = json.loads(res["canonical_json"]) if res["canonical_json"] else None
            res["logs"] = json.loads(res["logs_json"]) if res["logs_json"] else []
            return res

    def list_jobs(self, limit: int = 40) -> List[Dict[str, Any]]:
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT job_id, file_name, file_size_bytes, status, progress, export_policy, summary_json, created_at, updated_at, output_file_name FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,))
            rows = cursor.fetchall()
            
            # If 0 rows, check if we need to restore from Azure Blob once
            if len(rows) == 0:
                conn.close()
                self.restore_from_blob()
                with self._get_conn() as conn2:
                    cursor2 = conn2.cursor()
                    cursor2.execute("SELECT job_id, file_name, file_size_bytes, status, progress, export_policy, summary_json, created_at, updated_at, output_file_name FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,))
                    rows = cursor2.fetchall()

            result = []
            for r in rows:
                item = dict(r)
                summary = json.loads(item["summary_json"]) if item["summary_json"] else {}
                item["summary"] = summary
                item["total_rows"] = summary.get("total_rows", 0)
                item["valid_rows"] = summary.get("valid_rows", 0)
                item["warning_rows"] = summary.get("warning_rows", 0)
                item["error_rows"] = summary.get("error_rows", 0)
                item["carrier_code"] = summary.get("carriers_found", ["UNKN"])[0] if summary.get("carriers_found") else "UNKN"
                item["contract_number"] = summary.get("contract_number", "")
                item["validity_start"] = summary.get("validity_start", "")
                item["validity_end"] = summary.get("validity_end", "")
                result.append(item)
            return result

    def clear_all_jobs(self):
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM jobs;")
            conn.commit()
        # Immediately backup cleared state to Azure Blob
        self.backup_to_blob()

def datetime_now_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
