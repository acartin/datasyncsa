import asyncio
import logging

from app.dependencies.database import close_database, init_database
from app.services.cache_service import cache_service
from app.services.scoring_worker import ScoringWorker


logger = logging.getLogger("inference-core-v2.worker-main")


async def _run() -> None:
    await init_database()
    await cache_service.connect()
    worker = ScoringWorker()
    try:
        await worker.run_forever()
    finally:
        await cache_service.disconnect()
        await close_database()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(_run())
