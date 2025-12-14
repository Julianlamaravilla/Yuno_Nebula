"""
Yuno Sentinel - Configuration Management
All secrets and settings loaded from environment variables
"""
from pydantic_settings import BaseSettings
from typing import Literal


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # Database Configuration
    database_url: str = "postgresql+asyncpg://yuno_admin:yuno_secret_2024@localhost:5432/yuno_sentinel"

    # Redis Configuration
    redis_url: str = "redis://localhost:6379"
    redis_pool_max_connections: int = 50

    # LLM Provider Configuration
    llm_provider: Literal["openai", "gemini"] = "gemini"
    gemini_api_key: str | None = None
    openai_api_key: str | None = None

    # Alert Thresholds
    alert_threshold_error_rate: float = 0.20  # 20%
    alert_threshold_decline_rate: float = 0.50  # 50% decline rate
    min_transactions_for_alert: int = 50  # Minimum sample size
    alert_cooldown_seconds: int = 600  # 10 minutes between duplicate alerts

    # Worker Configuration
    check_interval_seconds: int = 10

    # AI Agent Service URL (for Detection Team → AI Team communication)
    ai_agent_url: str = "http://ai-agent:8001"

    # Redis Key Patterns
    redis_stats_key_pattern: str = "stats:{country}:{provider}:{status}:{minute}"
    redis_key_ttl_seconds: int = 3600  # 1 hour

    # Time Windows
    metrics_lookback_minutes: int = 5

    # Application
    env: str = "development"
    log_level: str = "INFO"

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"

    def get_llm_api_key(self) -> str:
        """Get the appropriate API key based on LLM provider"""
        if self.llm_provider == "gemini":
            if not self.gemini_api_key:
                raise ValueError("GEMINI_API_KEY not set in environment")
            return self.gemini_api_key
        elif self.llm_provider == "openai":
            if not self.openai_api_key:
                raise ValueError("OPENAI_API_KEY not set in environment")
            return self.openai_api_key
        else:
            raise ValueError(f"Unsupported LLM provider: {self.llm_provider}")


# Global settings instance
settings = Settings()
