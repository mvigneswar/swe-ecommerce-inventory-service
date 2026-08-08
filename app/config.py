"""Configuration objects loaded from environment variables."""

import os

from dotenv import load_dotenv

load_dotenv()


def _int_env(key: str, default: int) -> int:
    try:
        return int(os.getenv(key, default))
    except (TypeError, ValueError):
        return default


class BaseConfig:
    """Settings shared by every environment."""

    SECRET_KEY = os.getenv("SECRET_KEY", "dev_secret_key")

    # ---- MySQL ----
    MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
    MYSQL_PORT = _int_env("MYSQL_PORT", 3307)
    MYSQL_USER = os.getenv("MYSQL_USER", "ecom_user")
    MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "ecom_pass_dev")
    MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "ecommerce_db")

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,   # drop dead connections instead of erroring
        "pool_recycle": 280,     # stay under MySQL's wait_timeout
        "pool_size": 10,
        "max_overflow": 20,
    }

    # ---- Redis ----
    REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT = _int_env("REDIS_PORT", 6379)
    REDIS_DB = _int_env("REDIS_DB", 0)
    REDIS_PASSWORD = os.getenv("REDIS_PASSWORD") or None
    CACHE_TTL_SECONDS = _int_env("CACHE_TTL_SECONDS", 60)
    CACHE_ENABLED = True

    # ---- Pagination ----
    DEFAULT_PAGE_SIZE = _int_env("DEFAULT_PAGE_SIZE", 20)
    MAX_PAGE_SIZE = _int_env("MAX_PAGE_SIZE", 100)

    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:  # noqa: N802 (Flask naming)
        return (
            f"mysql+pymysql://{self.MYSQL_USER}:{self.MYSQL_PASSWORD}"
            f"@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DATABASE}"
            "?charset=utf8mb4"
        )


class DevelopmentConfig(BaseConfig):
    DEBUG = True


class TestingConfig(BaseConfig):
    """Tests run against a separate database and with caching disabled."""

    TESTING = True
    DEBUG = True
    CACHE_ENABLED = False
    MYSQL_DATABASE = os.getenv("MYSQL_TEST_DATABASE", "ecommerce_test_db")


class ProductionConfig(BaseConfig):
    DEBUG = False


CONFIG_MAP = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}


def get_config(name: str | None = None) -> BaseConfig:
    env = (name or os.getenv("FLASK_ENV") or "development").lower()
    return CONFIG_MAP.get(env, DevelopmentConfig)()
