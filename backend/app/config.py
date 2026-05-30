import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv
from typing import List

# Load .env file explicitly
load_dotenv()

class Settings(BaseSettings):
    google_api_key: str = os.getenv("GOOGLE_API_KEY", "")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "") # Kept for fallback if someone still uses it, but default is google
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    pinecone_api_key: str = os.getenv("PINECONE_API_KEY", "")
    pinecone_index_name: str = os.getenv("PINECONE_INDEX_NAME", "creatorjoy")
    cache_expiry_seconds: int = 3600
    host: str = "127.0.0.1"
    port: int = 8000
    rate_limit_per_minute: int = 20

    # CORS: comma-separated list of allowed origins.
    # Override via CORS_ORIGINS env var for staging/production.
    # Example: CORS_ORIGINS=https://app.example.com,https://staging.example.com
    cors_origins: List[str] = [
        o.strip()
        for o in os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")
        if o.strip()
    ]

    # Configure settings config dict to load env files
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
