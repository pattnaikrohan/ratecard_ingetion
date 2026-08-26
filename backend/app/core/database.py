import sqlite3
import json
import time
import os
import threading
from pathlib import Path
from typing import Dict, Any, List, Optional
from app.core.config import DB_PATH
from app.models.canonical import JobStatusResponse, CanonicalRateSheet, JobSummary

# Max retries for transient SQLite errors (disk I/O, database locked)
_MAX_RETRIES = 3
_RETRY_DELAY = 0.5  # seconds

class DatabaseManager:
    _instance = None
    _lock = threading.Lock()  # Serialize write operations

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
        conn = sqlite3.connect(str(self.db_path), timeout=60.0)
        conn.row_factory = sqlite3.Row
        # Enable WAL mode for concurrent read/write support
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout=30000;")  # 30s busy wait
        conn.execute("PRAGMA synchronous=NORMAL;")   # Faster writes, still safe with WAL
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

    _backup_lock = threading.Lock()
    _backup_timer: Optional[threading.Timer] = None

    def trigger_debounced_backup(self, delay: float = 3.0):
        """Debounces Azure Blob backup so multiple concurrent job status updates only perform a single upload."""
        with self._backup_lock:
            if self._backup_timer is not None and self._backup_timer.is_alive():
                self._backup_timer.cancel()
            self._backup_timer = threading.Timer(delay, self._safe_backup_worker)
            self._backup_timer.daemon = True
            self._backup_timer.start()

    def _safe_backup_worker(self):
        try:
            self.backup_to_blob()
        except Exception as e:
            print(f"[Storage] Debounced backup notice: {e}")

    def backup_to_blob(self):
        """Upload current SQLite DB to Azure Blob Storage with robust retry and timeout."""
        from app.services.storage import StorageService
        blob_client = StorageService._get_blob_client("rate_agent.db")
        if blob_client and self.db_path.exists() and self.db_path.stat().st_size > 0:
            try:
                with open(self.db_path, "rb") as data:
                    blob_client.upload_blob(data, overwrite=True, timeout=10)
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
        
        for attempt in range(_MAX_RETRIES):
            try:
                with self._lock:
                    with self._get_conn() as conn:
                        cursor = conn.cursor()
                        cursor.execute("""
                            INSERT INTO jobs (job_id, file_name, file_size_bytes, status, progress, export_policy, summary_json, logs_json, created_at, updated_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (job_id, file_name, file_size, "NEW", 0, export_policy, json.dumps(summary.model_dump()), json.dumps(logs), now, now))
                        conn.commit()
                break  # Success
            except (sqlite3.OperationalError, sqlite3.DatabaseError) as e:
                if attempt < _MAX_RETRIES - 1:
                    print(f"[DB] create_job retry {attempt+1}/{_MAX_RETRIES} for {job_id}: {e}")
                    time.sleep(_RETRY_DELAY * (attempt + 1))
                else:
                    print(f"[DB] create_job FAILED after {_MAX_RETRIES} retries for {job_id}: {e}")
                    raise

        # Trigger debounced state backup to Azure Blob Storage
        self.trigger_debounced_backup(delay=4.0)
            
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
        for attempt in range(_MAX_RETRIES):
            try:
                with self._lock:
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
                break  # Success
            except (sqlite3.OperationalError, sqlite3.DatabaseError) as e:
                if attempt < _MAX_RETRIES - 1:
                    print(f"[DB] update_job_status retry {attempt+1}/{_MAX_RETRIES} for {job_id}: {e}")
                    time.sleep(_RETRY_DELAY * (attempt + 1))
                else:
                    print(f"[DB] update_job_status FAILED after {_MAX_RETRIES} retries for {job_id}: {e}")
                    raise

        # Debounced backup on final terminal status transitions
        if status in ["COMPLETED", "FAILED", "APPROVED", "NEEDS_REVIEW"] or progress == 100:
            self.trigger_debounced_backup(delay=2.0)

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        try:
            with self._get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,))
                row = cursor.fetchone()
                if not row:
                    return None
                
                res = dict(row)
                try:
                    res["summary"] = json.loads(res["summary_json"]) if res.get("summary_json") else {}
                except Exception:
                    res["summary"] = {}
                try:
                    res["canonical"] = json.loads(res["canonical_json"]) if res.get("canonical_json") else None
                except Exception:
                    res["canonical"] = None
                try:
                    res["logs"] = json.loads(res["logs_json"]) if res.get("logs_json") else []
                except Exception:
                    res["logs"] = []
                return res
        except Exception as e:
            print(f"[DB] Error in get_job({job_id}): {e}")
            return None

    def list_jobs(self, limit: int = 40) -> List[Dict[str, Any]]:
        rows = []
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT job_id, file_name, file_size_bytes, status, progress, export_policy, summary_json, created_at, updated_at, output_file_name FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,))
            rows = cursor.fetchall()

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
        with self._lock:
            with self._get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM jobs;")
                conn.commit()
        # Immediately trigger debounced backup of cleared state
        self.trigger_debounced_backup(delay=0.5)

def datetime_now_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
