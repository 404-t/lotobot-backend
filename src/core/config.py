from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class EnvConfig(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8')

    # ----- APP ENV CONFIG -----
    APP_NAME: str = 'LotoBot'
    APP_HOST: str
    APP_PORT: int

    DEBUG: bool = False

    # ----- REDIS -----
    REDIS_HOST: str
    REDIS_PORT: int
    REDIS_PASS: str | None = None
    REDIS_DB: int

    @property
    def REDIS_URL(self) -> str:
        if self.REDIS_PASS:
            redis_url = f'redis://:{self.REDIS_PASS}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}'
        else:
            redis_url = f'redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}'

        return redis_url

    # ----- OPENAI / AI -----
    OPENAI_API_KEY: str | None = None
    OPENAI_BASE_URL: str = 'https://openrouter.ai/api/v1'

    # ----- LOGGER -----
    SENSITIVE_DATA: list[str] = []
    LOG_LEVEL: str = 'INFO'
    LOG_TO_FILE: bool = False
    LOG_FORMAT: str = '%(asctime)s | %(levelname)-8s | %(name)s | [%(filename)s:%(funcName)s:%(lineno)d] - %(message)s'
    LOG_DATE_FORMAT: str = '%Y-%m-%d %H:%M:%S.%f'

    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent
    _LOGS_DIR: Path = BASE_DIR / 'logs'

    @property
    def LOGS_DIR(self) -> Path:
        Path.mkdir(self._LOGS_DIR, parents=True, exist_ok=True)
        return self._LOGS_DIR


class AppConfig(BaseSettings):
    CORS_ORIGINS: list[str] = [
        'http://localhost:5173',
        'http://localhost:3000',
        'http://62.217.177.201',
        'https://404-team.ru',
    ]


env_config = EnvConfig()
app_config = AppConfig()
