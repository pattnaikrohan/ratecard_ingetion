import os
import shutil
from pathlib import Path
from azure.storage.blob import BlobServiceClient
from app.core.config import UPLOADS_DIR, PROCESSED_DIR, FAILED_DIR, ARCHIVE_DIR, AZURE_STORAGE_SAS_URL

class StorageService:
    @staticmethod
    def _get_blob_client(blob_name: str):
        if not AZURE_STORAGE_SAS_URL:
            return None
        try:
            # AZURE_STORAGE_SAS_URL includes the container name and SAS token
            blob_service_client = BlobServiceClient(account_url=AZURE_STORAGE_SAS_URL)
            # The SAS URL typically points to a container if it has a container name in the path, 
            # but usually BlobServiceClient expects the account URL.
            # Let's extract account URL and SAS token to use ContainerClient directly.
            from azure.storage.blob import ContainerClient
            container_client = ContainerClient.from_container_url(AZURE_STORAGE_SAS_URL)
            return container_client.get_blob_client(blob_name)
        except Exception as e:
            print(f"Error getting blob client for {blob_name}: {e}")
            return None

    @staticmethod
    def save_upload(file_bytes: bytes, filename: str) -> Path:
        # Save locally for parsers
        target = UPLOADS_DIR / filename
        with open(target, "wb") as f:
            f.write(file_bytes)
            
        # Upload to Blob Storage
        blob_client = StorageService._get_blob_client(f"uploads/{filename}")
        if blob_client:
            try:
                blob_client.upload_blob(file_bytes, overwrite=True)
                print(f"Uploaded {filename} to Azure Blob Storage (uploads/)")
            except Exception as e:
                print(f"Failed to upload {filename} to Blob Storage: {e}")
                
        return target

    @staticmethod
    def get_upload_path(filename: str) -> Path:
        return UPLOADS_DIR / filename

    @staticmethod
    def save_processed_output(source_path: Path, output_filename: str) -> Path:
        # Save locally
        target = PROCESSED_DIR / output_filename
        shutil.copy(source_path, target)
        
        # Upload to Blob Storage
        blob_client = StorageService._get_blob_client(f"processed/{output_filename}")
        if blob_client:
            try:
                with open(target, "rb") as data:
                    blob_client.upload_blob(data, overwrite=True)
                print(f"Uploaded {output_filename} to Azure Blob Storage (processed/)")
            except Exception as e:
                print(f"Failed to upload {output_filename} to Blob Storage: {e}")
                
        return target

    @staticmethod
    def get_output_path(output_filename: str) -> Path:
        target = PROCESSED_DIR / output_filename
        # If the file doesn't exist locally, try downloading it from Blob Storage
        if not target.exists():
            blob_client = StorageService._get_blob_client(f"processed/{output_filename}")
            if blob_client and blob_client.exists():
                try:
                    with open(target, "wb") as f:
                        f.write(blob_client.download_blob().readall())
                    print(f"Downloaded {output_filename} from Azure Blob Storage")
                except Exception as e:
                    print(f"Failed to download {output_filename} from Blob Storage: {e}")
        return target
