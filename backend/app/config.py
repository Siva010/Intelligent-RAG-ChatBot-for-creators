import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv

# Load .env file explicitly
load_dotenv()

class Settings(BaseSettings):
    google_api_key: str = os.getenv("GOOGLE_API_KEY", "")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "") # Kept for fallback if someone still uses it, but default is google
    chroma_db_dir: str = os.getenv("CHROMA_DB_DIR", "./chroma_db")
    cache_expiry_seconds: int = 3600
    host: str = "127.0.0.1"
    port: int = 8000
    
    # Configure settings config dict to load env files
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
