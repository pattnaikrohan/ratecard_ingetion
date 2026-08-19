import os
import asyncio
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse
from typing import Optional, List, Dict, Any
from app.services.job_manager import JobManager
from app.core.database import DatabaseManager
from app.core.master_data import MasterDataEngine
from app.services.storage import StorageService
from app.models.canonical import CanonicalRateSheet, RateRow

router = APIRouter(prefix="/api")

job_manager = JobManager.get_instance()
db = DatabaseManager.get_instance()
md = MasterDataEngine.get_instance()

@router.post("/upload")
async def upload_rate_card(file: UploadFile = File(...), export_policy: str = Form("PARTIAL")):
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")
    
    file_bytes = await file.read()
    job_id = job_manager.submit_job(file_bytes, file.filename, export_policy)
    return {"job_id": job_id, "file_name": file.filename, "status": "QUEUED", "message": "File uploaded successfully"}

@router.post("/upload-batch")
async def upload_batch_rate_cards(files: List[UploadFile] = File(...), export_policy: str = Form("PARTIAL")):
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")
    
    results = []
    for file in files:
        if file.filename:
            file_bytes = await file.read()
            job_id = job_manager.submit_job(file_bytes, file.filename, export_policy)
            results.append({"job_id": job_id, "file_name": file.filename, "status": "QUEUED"})
            
    return {"total_files": len(results), "jobs": results, "message": f"Successfully queued batch of {len(results)} files"}

@router.get("/jobs")
async def list_jobs(limit: int = 20):
    return db.list_jobs(limit)

@router.post("/jobs/clear")
async def clear_all_jobs_post():
    db.clear_all_jobs()
    return {"message": "All jobs and ingestion history cleared successfully"}

@router.delete("/jobs/clear")
async def clear_all_jobs_delete():
    db.clear_all_jobs()
    return {"message": "All jobs and ingestion history cleared successfully"}

@router.get("/jobs/{job_id}")
async def get_job(job_id: str):
    job = db.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job

@router.get("/jobs/{job_id}/logs")
async def get_job_logs(job_id: str):
    job = db.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"job_id": job_id, "logs": job.get("logs", [])}

@router.post("/jobs/{job_id}/revalidate")
async def revalidate_job(job_id: str, updated_rates: List[RateRow]):
    job = db.get_job(job_id)
    if not job or not job.get("canonical"):
        raise HTTPException(status_code=404, detail="Job not found")
    
    canonical_data = job["canonical"]
    sheet = CanonicalRateSheet(**canonical_data)
    sheet.rates = updated_rates

    valid_cnt = 0
    warn_cnt = 0
    err_cnt = 0
    crit_cnt = 0

    validator = job_manager.validator
    for idx, r in enumerate(sheet.rates):
        val_row = validator.validate_row(r)
        
        # Save user corrections into persistent synonym memory for auto-learning!
        if val_row.origin_raw and val_row.origin_locode and val_row.validation_status == "VALID":
            md.port_synonyms[val_row.origin_raw.strip().upper()] = val_row.origin_locode
            city_only = val_row.origin_raw.split(',')[0].strip().upper()
            md.port_synonyms[city_only] = val_row.origin_locode

        if val_row.destination_raw and val_row.destination_locode and val_row.validation_status == "VALID":
            md.port_synonyms[val_row.destination_raw.strip().upper()] = val_row.destination_locode
            city_only = val_row.destination_raw.split(',')[0].strip().upper()
            md.port_synonyms[city_only] = val_row.destination_locode

        sheet.rates[idx] = val_row
        if val_row.validation_status == "VALID": valid_cnt += 1
        elif val_row.validation_status == "WARNING": warn_cnt += 1
        elif val_row.validation_status == "ERROR": err_cnt += 1
        elif val_row.validation_status == "CRITICAL": crit_cnt += 1

    sheet.summary.valid_rows = valid_cnt
    sheet.summary.warning_rows = warn_cnt
    sheet.summary.error_rows = err_cnt
    sheet.summary.critical_rows = crit_cnt

    next_status = "NEEDS_REVIEW" if (err_cnt > 0 or crit_cnt > 0) else "APPROVED"
    db.update_job_status(job_id, next_status, progress=85, log_msg="Re-validated rate rows & saved corrections to Master Data Memory", canonical_sheet=sheet)
    
    return {"job_id": job_id, "status": next_status, "summary": sheet.summary}

@router.post("/jobs/{job_id}/approve")
async def approve_job(job_id: str, export_policy: str = "PARTIAL"):
    # Always regenerate to guarantee export reflects the latest canonical data
    output_filename = await job_manager.generate_export(job_id, export_policy)
    return {"job_id": job_id, "status": "COMPLETED", "output_file_name": output_filename}

@router.get("/jobs/{job_id}/download")
async def download_output_sheet(job_id: str):
    job = db.get_job(job_id)
    if not job or not job.get("output_file_name"):
        raise HTTPException(status_code=404, detail="Export file not ready for download")
    
    out_file = StorageService.get_output_path(job["output_file_name"])
    if not out_file.exists():
        raise HTTPException(status_code=404, detail="Output file missing from storage")
        
    return FileResponse(out_file, media_type="application/vnd.ms-excel.sheet.macroEnabled.12", filename=job["output_file_name"])

@router.get("/master-data")
async def get_master_data_summary():
    return {
        "loaded_at": md.loaded_at,
        "version": md.version,
        "carriers_count": len(md.carriers),
        "ports_count": len(md.ports),
        "load_types": list(md.load_types),
        "currencies_count": len(md.currencies)
    }

@router.post("/master-data/reload")
async def reload_master_data():
    success = md.load_master_data()
    return {"success": success, "message": "Master Data reloaded successfully"}

@router.get("/metrics")
async def get_metrics():
    jobs = db.list_jobs(limit=100)
    total_jobs = len(jobs)
    completed_jobs = sum(1 for j in jobs if j["status"] in ["COMPLETED", "APPROVED", "NEEDS_REVIEW"])
    total_rows = sum(j.get("summary", {}).get("total_rows", 0) for j in jobs)
    
    avg_time_ms = 0.0
    if total_jobs > 0:
        times = [j.get("summary", {}).get("processing_time_ms", 0) for j in jobs if j.get("summary", {}).get("processing_time_ms", 0) > 0]
        if times:
            avg_time_ms = sum(times) / len(times)
            
    time_saved_hrs = round(completed_jobs * 0.45, 1)
    
    return {
        "total_jobs": total_jobs,
        "completed_jobs": completed_jobs,
        "total_rows_ingested": total_rows,
        "avg_processing_time_ms": round(avg_time_ms, 2),
        "average_time_saved_mins": time_saved_hrs
    }

@router.get("/ai/learned-synonyms")
async def get_learned_synonyms():
    """Return the self-learning synonym dictionary built from AI mappings."""
    from app.services.ai_column_mapper import AIColumnMapper
    mapper = AIColumnMapper.get_instance()
    return mapper.get_learned_stats()
