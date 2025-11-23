import asyncio
import time
from fastapi import APIRouter, Query

from src.integrations.redis import RedisClient
from src.integrations.stoloto import (
    StolotoClient,
    MainStolotoClient,
    NewsStolotoClient,
    TabsStolotoClient,
    DetailsStolotoClient,
    ListStolotoClient,
)
from src.core.config import env_config
from src.core.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix='/api/stoloto', tags=['stoloto'])

_stoloto_client: StolotoClient | None = None
_redis_client: RedisClient | None = None


def get_stoloto_client() -> StolotoClient:
    """Dependency for getting StolotoClient."""
    global _stoloto_client # noqa
    if _stoloto_client is None:
        _stoloto_client = StolotoClient(rate_limit=1.0)
    return _stoloto_client


def get_redis_client() -> RedisClient:
    """Dependency for getting RedisClient."""
    global _redis_client # noqa
    if _redis_client is None:
        _redis_client = RedisClient(env_config.REDIS_URL)
    return _redis_client


async def close_clients():
    """Close clients on application shutdown."""
    global _stoloto_client, _redis_client # noqa
    if _stoloto_client:
        await _stoloto_client.close()
        _stoloto_client = None
    if _redis_client:
        await _redis_client.client.aclose()
        _redis_client = None
        logger.info('Clients closed')


@router.get('/main')
async def get_main_categories(force_refresh: bool = Query(False, description='Force refresh from API')):
    """
    Get main categories from Stoloto.
    
    - **force_refresh**: If True, ignores cache and fetches fresh data
    """
    stoloto_client = get_stoloto_client()
    redis_client = get_redis_client()
    
    client = MainStolotoClient(stoloto_client, redis_client)
    data = await client.get(force_refresh=force_refresh)
    
    return data.model_dump()


@router.get('/news')
async def get_news(force_refresh: bool = Query(False, description='Force refresh from API')):
    """
    Get news from Stoloto.
    
    - **force_refresh**: If True, ignores cache and fetches fresh data
    """
    stoloto_client = get_stoloto_client()
    redis_client = get_redis_client()
    
    client = NewsStolotoClient(stoloto_client, redis_client)
    data = await client.get(force_refresh=force_refresh)
    
    return data.model_dump()


@router.get('/tabs')
async def get_tabs(force_refresh: bool = Query(False, description='Force refresh from API')):
    """
    Get active draws and promotions (tabs) from Stoloto.
    
    - **force_refresh**: If True, ignores cache and fetches fresh data
    """
    stoloto_client = get_stoloto_client()
    redis_client = get_redis_client()
    
    client = TabsStolotoClient(stoloto_client, redis_client)
    data = await client.get(force_refresh=force_refresh)
    
    return data.model_dump()


@router.get('/details')
async def get_details(
    lottery_code: str = Query('ruslotto', description='Lottery code (ruslotto, gzhl, 5x36, etc.)'),
    count: int = Query(5, ge=1, le=50, description='Number of draws'),
    force_refresh: bool = Query(False, description='Force refresh from API'),
):
    """
    Get draw details for Stoloto lottery.
    
    - **lottery_code**: Lottery code
    - **count**: Number of draws to fetch (1-50)
    - **force_refresh**: If True, ignores cache and fetches fresh data
    """
    stoloto_client = get_stoloto_client()
    redis_client = get_redis_client()
    
    client = DetailsStolotoClient(stoloto_client, redis_client, lottery_code=lottery_code, count=count)
    data = await client.get(force_refresh=force_refresh)
    
    return data.model_dump()


@router.get('/list')
async def get_packets(force_refresh: bool = Query(False, description='Force refresh from API')):
    """
    Get ticket packets list from Stoloto.
    
    - **force_refresh**: If True, ignores cache and fetches fresh data
    """
    stoloto_client = get_stoloto_client()
    redis_client = get_redis_client()
    
    client = ListStolotoClient(stoloto_client, redis_client)
    data = await client.get(force_refresh=force_refresh)
    
    return data.model_dump()


@router.get('/all')
async def get_all(
    force_refresh: bool = Query(False, description='Force refresh from API'),
    lottery_code: str = Query('ruslotto', description='Lottery code for details endpoint'),
    count: int = Query(5, ge=1, le=50, description='Number of draws for details endpoint'),
):
    """
    Get data from all Stoloto clients in parallel.
    
    This endpoint is designed to test the request queue and rate limiting (1 request per second).
    All clients are called simultaneously, so requests will be queued and rate-limited.
    
    - **force_refresh**: If True, ignores cache and fetches fresh data
    - **lottery_code**: Lottery code for details endpoint (ruslotto, gzhl, 5x36, etc.)
    - **count**: Number of draws for details endpoint (1-50)
    
    Returns a dictionary with results from all endpoints and timing information.
    """
    stoloto_client = get_stoloto_client()
    redis_client = get_redis_client()

    # Create all clients
    main_client = MainStolotoClient(stoloto_client, redis_client)
    news_client = NewsStolotoClient(stoloto_client, redis_client)
    tabs_client = TabsStolotoClient(stoloto_client, redis_client)
    details_client = DetailsStolotoClient(stoloto_client, redis_client, lottery_code=lottery_code, count=count)
    list_client = ListStolotoClient(stoloto_client, redis_client)

    logger.info('Starting parallel requests to all Stoloto clients')
    start_time = time.time()

    results = await asyncio.gather(
        main_client.get(force_refresh=force_refresh),
        news_client.get(force_refresh=force_refresh),
        tabs_client.get(force_refresh=force_refresh),
        details_client.get(force_refresh=force_refresh),
        list_client.get(force_refresh=force_refresh),
        return_exceptions=True,
    )
    
    end_time = time.time()
    elapsed_time = end_time - start_time
    
    # Process results
    response_data = {
        'main': results[0].model_dump() if not isinstance(results[0], Exception) else {'error': str(results[0])},
        'news': results[1].model_dump() if not isinstance(results[1], Exception) else {'error': str(results[1])},
        'tabs': results[2].model_dump() if not isinstance(results[2], Exception) else {'error': str(results[2])},
        'details': results[3].model_dump() if not isinstance(results[3], Exception) else {'error': str(results[3])},
        'list': results[4].model_dump() if not isinstance(results[4], Exception) else {'error': str(results[4])},
        'timing': {
            'total_time_seconds': round(elapsed_time, 2),
            'requests_count': 5,
            'average_time_per_request': round(elapsed_time / 4, 2),
        },
    }
    
    logger.info(f'All requests completed in {elapsed_time:.2f} seconds')
    
    return response_data

