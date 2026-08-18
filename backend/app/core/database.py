import sqlite3
import json
import time
from typing import Dict, Any, List, Optional
from app.core.config import DB_PATH
from app.models.canonical import JobStatusResponse, CanonicalRateSheet, JobSummary

class DatabaseManager:
    _instance = None

    def __init__(self, db_path: str = str(DB_PATH)):
        self.db_path = db_path
        self._init_db()

    @classmethod
    def get_instance(cls) -> "DatabaseManager":
        if cls._instance is None:
            cls._instance = DatabaseManager()
        return cls._instance

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
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

    def list_jobs(self, limit: int = 20) -> List[Dict[str, Any]]:
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT job_id, file_name, file_size_bytes, status, progress, export_policy, summary_json, created_at, updated_at, output_file_name FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,))
            rows = cursor.fetchall()
            result = []
            for r in rows:
                item = dict(r)
                item["summary"] = json.loads(item["summary_json"]) if item["summary_json"] else {}
                result.append(item)
            return result

    def clear_all_jobs(self):
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM jobs;")
            conn.commit()

def datetime_now_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
