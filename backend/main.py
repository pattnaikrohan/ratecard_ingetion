import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.endpoints import router as api_router

app = FastAPI(
    title="Carrier Rate Card Extraction & Freightify Ingestion Agent API",
    version="3.0.0",
    description="Enterprise PoC API for carrier rate card ingestion, master data validation, and Freightify upload sheet generation."
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://icy-bush-00b71b600.7.azurestaticapps.net",
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
