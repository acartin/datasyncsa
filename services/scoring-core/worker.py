import asyncio
import logging

from app.core.config import settings
from app.dependencies.database import close_database, init_database
from app.services.cache_service import cache_service
from app.services.scoring_worker import ScoringWorker


logger = logging.getLogger("scoring-core.worker-main")


async def _run() -> None:
    await init_database()
    await cache_service.connect()
    concurrency = max(1, int(settings.scoring_worker_concurrency or 1))
    logger.info("Starting scoring worker pool with concurrency=%s", concurrency)
    workers = [ScoringWorker() for _ in range(concurrency)]
    tasks = [asyncio.create_task(worker.run_forever()) for worker in workers]
    try:
        await asyncio.gather(*tasks)
    finally:
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        await cache_service.disconnect()
        await close_database()


if __name__ == "__main__":
    logging.basicConfig(level=settings.log_level)
    asyncio.run(_run())
