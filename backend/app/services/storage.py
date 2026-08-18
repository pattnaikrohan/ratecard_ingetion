import os
import shutil
from pathlib import Path
from app.core.config import UPLOADS_DIR, PROCESSED_DIR, FAILED_DIR, ARCHIVE_DIR

class StorageService:
    @staticmethod
    def save_upload(file_bytes: bytes, filename: str) -> Path:
        target = UPLOADS_DIR / filename
        with open(target, "wb") as f:
            f.write(file_bytes)
        return target

    @staticmethod
    def get_upload_path(filename: str) -> Path:
        return UPLOADS_DIR / filename

    @staticmethod
    def save_processed_output(source_path: Path, output_filename: str) -> Path:
        target = PROCESSED_DIR / output_filename
        shutil.copy(source_path, target)
        return target

    @staticmethod
    def get_output_path(output_filename: str) -> Path:
        return PROCESSED_DIR / output_filename
