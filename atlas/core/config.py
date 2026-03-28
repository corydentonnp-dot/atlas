"""Atlas configuration — typed application settings loaded from the environment."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, SecretStr, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AtlasSettings(BaseSettings):
	"""Runtime configuration for Atlas.

	Settings are loaded from environment variables and an optional local `.env` file.
	Sensitive fields are stored as `SecretStr` to avoid accidental log exposure.
	"""

	model_config = SettingsConfigDict(
		env_file=".env",
		env_file_encoding="utf-8",
		case_sensitive=False,
		extra="ignore",
	)

	app_name: str = Field(default="Atlas")
	environment: str = Field(default="development")

	postgres_host: str = Field(default="localhost", alias="POSTGRES_HOST")
	postgres_port: int = Field(default=5432, alias="POSTGRES_PORT")
	postgres_user: str = Field(default="atlas", alias="POSTGRES_USER")
	postgres_password: SecretStr = Field(
		default=SecretStr("atlas_dev_password_change_me"),
		alias="POSTGRES_PASSWORD",
	)
	postgres_db: str = Field(default="atlas_dev", alias="POSTGRES_DB")
	database_url: str | None = Field(default=None, alias="DATABASE_URL")

	redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")

	api_host: str = Field(default="0.0.0.0", alias="API_HOST")
	api_port: int = Field(default=8000, alias="API_PORT")
	api_debug: bool = Field(default=True, alias="API_DEBUG")
	api_secret_key: SecretStr = Field(
		default=SecretStr("change-me-to-a-random-secret-key"),
		alias="API_SECRET_KEY",
	)

	telegram_bot_token: SecretStr | None = Field(default=None, alias="TELEGRAM_BOT_TOKEN")
	telegram_chat_id: str | None = Field(default=None, alias="TELEGRAM_CHAT_ID")

	google_client_id: SecretStr | None = Field(default=None, alias="GOOGLE_CLIENT_ID")
	google_client_secret: SecretStr | None = Field(default=None, alias="GOOGLE_CLIENT_SECRET")
	google_redirect_uri: str | None = Field(default=None, alias="GOOGLE_REDIRECT_URI")

	home_assistant_url: str | None = Field(default=None, alias="HOME_ASSISTANT_URL")
	home_assistant_token: SecretStr | None = Field(default=None, alias="HOME_ASSISTANT_TOKEN")

	tesla_access_token: SecretStr | None = Field(default=None, alias="TESLA_ACCESS_TOKEN")
	tesla_refresh_token: SecretStr | None = Field(default=None, alias="TESLA_REFRESH_TOKEN")

	log_level: str = Field(default="INFO", alias="LOG_LEVEL")
	log_format: str = Field(default="json", alias="LOG_FORMAT")

	quiet_hours_start: str = Field(default="22:00", alias="QUIET_HOURS_START")
	quiet_hours_end: str = Field(default="07:00", alias="QUIET_HOURS_END")
	digest_interval_minutes: int = Field(default=60, alias="DIGEST_INTERVAL_MINUTES")
	default_timezone: str = Field(default="America/New_York", alias="DEFAULT_TIMEZONE")

	enable_browser_automation: bool = Field(default=False, alias="ENABLE_BROWSER_AUTOMATION")
	enable_outbound_actions: bool = Field(default=False, alias="ENABLE_OUTBOUND_ACTIONS")

	@computed_field  # type: ignore[prop-decorator]
	@property
	def sqlalchemy_database_url(self) -> str:
		"""Return the async SQLAlchemy database URL."""
		if self.database_url:
			return self.database_url

		password = self.postgres_password.get_secret_value()
		return (
			"postgresql+asyncpg://"
			f"{self.postgres_user}:{password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
		)

	@computed_field  # type: ignore[prop-decorator]
	@property
	def is_development(self) -> bool:
		return self.environment.lower() == "development"


@lru_cache(maxsize=1)
def get_settings() -> AtlasSettings:
	"""Return a cached settings instance for application-wide reuse."""
	return AtlasSettings()
