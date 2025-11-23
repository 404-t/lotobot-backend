from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.core.config import env_config, app_config
from src.core.logger import get_logger
from src.presentation.middlewares.logging import RequestLoggingMiddleware
from src.presentation.routers import ai, stoloto

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(
    _app: FastAPI,
) -> AsyncGenerator[None]:
    base_url: str = f'http://{env_config.APP_HOST}:{env_config.APP_PORT}'
    logger.info(f'App started on {base_url}')
    logger.info(f'See Swagger for mode info: {base_url}/docs')
    yield
    logger.warning('Stopping app...')
    await stoloto.close_clients()


app = FastAPI(title=env_config.APP_NAME, debug=env_config.DEBUG, lifespan=lifespan)
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=app_config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключение роутеров
app.include_router(stoloto.router)
app.include_router(ai.router)


@app.get('/health')
async def health():
    return {'status': 'ok'}


if __name__ == '__main__':
    import uvicorn

    uvicorn.run(app, host=env_config.APP_HOST, port=env_config.APP_PORT, log_level=50)
