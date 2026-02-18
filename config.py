from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """Loads and validates application settings from environment variables."""
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8')

    # LLM Provider
    GROQ_API_KEY: str
    SERPER_API_KEY: str

    # Model Artifacts
    MODEL_PATH: str = 'AI/timegan_model.pkl'
    SCALER_PATH: str = 'AI/scaler.joblib'

settings = Settings()