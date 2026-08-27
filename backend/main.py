import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from app.api.endpoints import router as api_router


class CacheControlMiddleware(BaseHTTPMiddleware):
    """Sets Cache-Control headers on GET responses for faster client performance."""
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        if request.method == "GET":
            path = request.url.path
            if "/api/master-data" in path:
                response.headers["Cache-Control"] = "public, max-age=300"
            elif "/api/metrics" in path:
                response.headers["Cache-Control"] = "public, max-age=30"
            elif "/api/ai/learned-synonyms" in path:
                response.headers["Cache-Control"] = "public, max-age=120"
            elif path in ("/api/jobs", "/api/jobs/"):
                response.headers["Cache-Control"] = "public, max-age=1"
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── STARTUP ──────────────────────────────────────────────
    # Eagerly initialize the DatabaseManager singleton.
    # This triggers blob restore BEFORE any request is served,
    # ensuring the dashboard has data immediately after container restart.
    from app.core.database import DatabaseManager
    db = DatabaseManager.get_instance()
    job_count = db.get_job_count()
    print(f"[Startup] ✅ DatabaseManager initialized. Jobs in DB: {job_count}")
    if job_count == 0:
        print("[Startup] ⚠️ DB has 0 jobs — if this is unexpected, check Azure Blob restore logs above.")
    else:
        print(f"[Startup] 📦 {job_count} jobs restored and ready to serve.")

    yield  # App is now running and serving requests

    # ── SHUTDOWN ─────────────────────────────────────────────
    # Force a final synchronous backup before the container shuts down
    print("[Shutdown] Performing final synchronous DB backup to Azure Blob...")
    try:
        db.backup_to_blob()
        print("[Shutdown] ✅ Final backup completed successfully.")
    except Exception as e:
        print(f"[Shutdown] ⚠️ Final backup failed: {e}")


app = FastAPI(
    title="Carrier Rate Card Extraction & Freightify Ingestion Agent API",
    version="3.0.0",
    description="Enterprise PoC API for carrier rate card ingestion, master data validation, and Freightify upload sheet generation.",
    lifespan=lifespan,
)

# 1. Custom caching middleware (inner)
app.add_middleware(CacheControlMiddleware)

# 2. CORS middleware (outermost so all preflight and error responses include CORS headers)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://icy-bush-00b71b600.7.azurestaticapps.net",
        "http://localhost:5173",
        "http://localhost:3000",
        "*"
    ],
    allow_origin_regex=r"https://.*\.azurestaticapps\.net",
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

app.include_router(api_router)

@app.get("/")
async def root():
    return {
        "status": "online",
        "service": "Carrier Rate Card Extraction Agent",
        "version": "3.0.0",
        "docs": "/docs"
    }

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)

