"""Application settings loaded from the project .env file."""

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Database and authentication settings for the application."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str
    secret_key: SecretStr = Field(min_length=32)
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    # AWS S3 storage for user uploaded profile pictures.
    s3_bucket_name: str
    s3_region: str = "ap-southeast-2"
    s3_access_key_id: SecretStr | None = None
    s3_secret_access_key: SecretStr | None = None
    # Set only for S3-compatible services such as MinIO or R2.
    s3_endpoint_url: str | None = None

    max_upload_size_bytes: int = 5 * 1024 * 1024
    items_per_page: int = 10

    reset_token_expire_minutes: int = 60

    # SMTP server used to send emails (e.g. a Mailtrap sandbox while developing).
    mail_server: str = "localhost"
    mail_port: int = 587
    mail_username: str = ""
    mail_password: SecretStr = SecretStr("")
    mail_from: str = "noreply@example.com"
    mail_use_tls: bool = True

    # Base URL of the site, used to build the reset link that opens the /reset-password page.
    frontend_url: str = "http://localhost:8000"

    # Send the login cookie only over HTTPS. Keep False on http://localhost; set True when deployed with HTTPS.
    cookie_secure: bool = False


settings = Settings()
