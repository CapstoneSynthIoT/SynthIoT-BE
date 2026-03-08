from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Loads and validates application settings from environment variables."""
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

    # LLM Provider
    GROQ_API_KEY: str
    SERPER_API_KEY: str

    # JWT
    JWT_SECRET: str = 'change-me-in-production'
    JWT_ALGORITHM: str = 'HS256'
    JWT_EXPIRE_MINUTES: int = 60 * 24  # 24 hours

    # OTP (stateless HMAC-based email verification)
    OTP_SECRET: str = 'change-me-otp-secret'
    OTP_EXPIRE_MINUTES: int = 10  # How long the verification JWT is valid after OTP success

    # SMTP (Gmail + App Password)
    SMTP_HOST: str = 'smtp.gmail.com'
    SMTP_PORT: int = 587
    SMTP_USER: str = ''
    SMTP_PASSWORD: str = ''  # Gmail App Password
    SMTP_FROM: str = ''  # e.g. "SynthIoT <you@gmail.com>"

    # Database
    DATABASE_URL: str = ''

    # Model Artifacts
    MODEL_PATH: str = 'AI/timegan_model.pkl'
    SCALER_PATH: str = 'AI/scaler.joblib'

settings = Settings()