import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root for local development
load_dotenv(Path(__file__).resolve().parent.parent.parent.parent / ".env")

# Path to D:\Rate File Template
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
DATA_DIR = BASE_DIR / "data"
UPLOADS_DIR = DATA_DIR / "uploads"
PROCESSED_DIR = DATA_DIR / "processed"
FAILED_DIR = DATA_DIR / "failed"
ARCHIVE_DIR = DATA_DIR / "archive"
DB_PATH = DATA_DIR / "rate_agent.db"

# Sample data path
SAMPLE_DIR = BASE_DIR / "Rate_File_Template_Completion_Freightify"
MASTER_DATA_XLS = SAMPLE_DIR / "Freightify Upload Template Master Data1.xls"
TEMPLATE_XLSM = SAMPLE_DIR / "Freightify Uplad Sheet Completed.xlsm"

# Ensure directories exist
for d in [DATA_DIR, UPLOADS_DIR, PROCESSED_DIR, FAILED_DIR, ARCHIVE_DIR]:
    d.mkdir(parents=True, exist_ok=True)

AZURE_DOC_INTEL_ENDPOINT = os.getenv("AZURE_DOC_INTEL_ENDPOINT", "")
AZURE_DOC_INTEL_KEY = os.getenv("AZURE_DOC_INTEL_KEY", "")

AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT", "")
AZURE_OPENAI_KEY = os.getenv("AZURE_OPENAI_KEY", "")
AZURE_OPENAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")

DEFAULT_EXPORT_POLICY = os.getenv("EXPORT_POLICY", "PARTIAL")  # STRICT, PARTIAL, WARNING_PERMISSIVE

AZURE_STORAGE_SAS_URL = os.getenv("AZURE_STORAGE_SAS_URL", "")
