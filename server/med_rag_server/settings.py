import enum
from pathlib import Path
from tempfile import gettempdir

from pydantic_settings import BaseSettings, SettingsConfigDict
from yarl import URL

TEMP_DIR = Path(gettempdir())


class LogLevel(str, enum.Enum):
    """Possible log levels."""

    NOTSET = "NOTSET"
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    FATAL = "FATAL"


class Settings(BaseSettings):
    """
    Application settings.

    These parameters can be configured
    with environment variables.
    """

    host: str = "127.0.0.1"
    port: int = 8000
    # quantity of workers for uvicorn
    workers_count: int = 1
    # Enable uvicorn reloading
    reload: bool = True

    # Current environment
    environment: str = "dev"

    log_level: LogLevel = LogLevel.INFO
    # Variables for the database
    db_host: str = "localhost"
    db_port: int = 5432
    db_user: str = "med_rag_server"
    db_pass: str = "med_rag_server"
    db_base: str = "admin"
    db_echo: bool = False
    
    # file save
    UPLOAD_ROOT: str = "./med_rag_server/static/uploads"
    VECTORSTORAGE_ROOT: str = "./med_rag_server/vectorstorage"
    MAX_FILE_SIZE: int = 1024 * 1024 * 100 * 2
    
    MODELSNAME: str = "bge-m3:latest"
    
    # Prefect 配置
    PREFECT_API_URL: str = "http://prefect-server:4200/api"
    PREFECT_UI_URL: str = "http://127.0.0.1:4200"
    PREFECT_API_KEY: str = "api-key"
    
    # 路径配置
    RAW_DOCS_ROOT: str = "../../server/med_rag_server/static/uploads"
    PROCESSED_ROOT: str = "../data/processed"
    OUTPUT_ROOT: str = "../data/output/markdown"
    STATIC_ROOT: str = "../../server/med_rag_server/static/images"

    @property
    def db_url(self) -> URL:
        """
        Assemble database URL from settings.

        :return: database URL.
        """
        return URL.build(
            scheme="postgresql+asyncpg",
            host=self.db_host,
            port=self.db_port,
            user=self.db_user,
            password=self.db_pass,
            path=f"/{self.db_base}",
        )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="MED_RAG_SERVER_",
        env_file_encoding="utf-8",
    )


settings = Settings()
