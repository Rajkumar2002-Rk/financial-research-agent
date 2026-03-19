from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    OPENAI_API_KEY: str
    TAVILY_API_KEY: str
    REDIS_URL: str = "redis://localhost:6379"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "console"
    OPENAI_MODEL: str = "gpt-4o"
    OPENAI_TEMPERATURE: float = 0.1
    REDIS_CACHE_TTL: int = 900
    REDIS_SESSION_TTL: int = 3600
    AGENT_TIMEOUT_SECONDS: int = 60
    MIN_CONFIDENCE_THRESHOLD: float = 0.4
    HISTORICAL_DATA_PERIOD: str = "1y"

    class Config:
        env_file = ".env"
        
        
        
@lru_cache()
def get_settings() -> Settings:
  return Settings()