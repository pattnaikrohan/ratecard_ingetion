import uvicorn
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

app = FastAPI(
    title="Carrier Rate Card Extraction & Freightify Ingestion Agent API",
    version="3.0.0",
    description="Enterprise PoC API for carrier rate card ingestion, master data validation, and Freightify upload sheet generation."
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(CacheControlMiddleware)

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
