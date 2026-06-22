import os
import logging
from supabase import create_client, Client
from api.config import config

logger = logging.getLogger("supabase_client")

class SupabaseClientWrapper:
    def __init__(self):
        self._client = None
        self._is_mock = False
        
        if "mock.supabase.co" in config.SUPABASE_URL or "mock-anon" in config.SUPABASE_KEY:
            logger.warning("Default/mock Supabase credentials detected. Starting Supabase in mock mode.")
            self._is_mock = True
            return
            
        try:
            self._client = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)
            self._is_mock = False
            logger.info("Successfully connected to Supabase.")
        except Exception as e:
            logger.warning(f"Failed to connect to Supabase: {e}. Falling back to mock local storage.")
            self._is_mock = True

    def upload_file(self, bucket: str, path: str, file_content: bytes) -> str:
        if self._is_mock:
            # Root directory of the project
            root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            mock_dir = os.path.join(root_dir, "mock_storage", bucket)
            os.makedirs(mock_dir, exist_ok=True)
            local_path = os.path.join(mock_dir, os.path.basename(path))
            with open(local_path, "wb") as f:
                f.write(file_content)
            url = f"file:///{local_path.replace(os.sep, '/')}"
            logger.info(f"[MOCK] Uploaded file to local storage: {url}")
            return url
            
        try:
            # Upload to bucket
            self._client.storage.from_(bucket).upload(path, file_content, {"content-type": "application/pdf"})
            url = self._client.storage.from_(bucket).get_public_url(path)
            return url
        except Exception as e:
            logger.error(f"Failed to upload file to Supabase: {e}")
            raise e

    def download_file(self, bucket: str, path: str) -> bytes:
        if self._is_mock:
            root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            mock_dir = os.path.join(root_dir, "mock_storage", bucket)
            local_path = os.path.join(mock_dir, os.path.basename(path))
            if os.path.exists(local_path):
                with open(local_path, "rb") as f:
                    return f.read()
            raise FileNotFoundError(f"Mock file not found at {local_path}")
            
        try:
            return self._client.storage.from_(bucket).download(path)
        except Exception as e:
            logger.error(f"Failed to download file from Supabase: {e}")
            raise e

    def clear_bucket(self, bucket: str):
        if self._is_mock:
            root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            mock_dir = os.path.join(root_dir, "mock_storage", bucket)
            if os.path.exists(mock_dir):
                for f in os.listdir(mock_dir):
                    file_path = os.path.join(mock_dir, f)
                    try:
                        if os.path.isfile(file_path):
                            os.unlink(file_path)
                    except Exception as e:
                        logger.error(f"Failed to delete mock file {file_path}: {e}")
            return
            
        try:
            # List all files in the bucket
            res = self._client.storage.from_(bucket).list(options={"limit": 100})
            if res:
                file_names = [item["name"] for item in res if item.get("name") != ".emptyFolderPlaceholder"]
                if file_names:
                    # Remove the files
                    self._client.storage.from_(bucket).remove(file_names)
                    logger.info(f"Successfully cleared files from Supabase bucket '{bucket}': {file_names}")
        except Exception as e:
            logger.error(f"Failed to clear Supabase bucket '{bucket}': {e}")

supabase_client = SupabaseClientWrapper()

