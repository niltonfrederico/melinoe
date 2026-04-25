"""ARQ worker: defines async tasks and cron jobs for background processing."""

from typing import Any
from typing import ClassVar

from arq import cron
from arq.connections import ArqRedis
from arq.connections import RedisSettings

from melinoe.clients.redis import get_redis_pool
from melinoe.clients.redis import get_redis_settings
from melinoe.logger import workflow_log


async def scrape_task(ctx: dict[str, Any], trigger: str = "cron") -> dict[str, Any]:
    """Run SenhorDasHorasMortasWorkflow — triggered by cron or by KardoNavalhaWorkflow."""
    from melinoe.workflows.senhor_das_horas_mortas import SenhorDasHorasMortasWorkflow

    workflow_log.info(f"scrape_task started — trigger={trigger}")
    wf = SenhorDasHorasMortasWorkflow()
    result = wf.run(trigger=trigger)
    workflow_log.info(
        f"scrape_task complete — mentions={result.get('new_mentions_found')}, enriched={result.get('profile_enriched')}"
    )
    return result


async def scrape_cron(ctx: dict[str, Any]) -> dict[str, Any]:
    """Cron wrapper for scrape_task — hardcodes trigger='cron' for daily scheduling."""
    return await scrape_task(ctx, trigger="cron")


async def enqueue_scrape_task(trigger: str = "new_work") -> None:
    """Enqueue a scraping task. Called by KardoNavalhaWorkflow after cataloging a new work."""
    pool: ArqRedis = await get_redis_pool()
    await pool.enqueue_job("scrape_task", trigger)
    await pool.aclose()
    workflow_log.info(f"scrape_task enqueued — trigger={trigger}")


class WorkerSettings:
    functions: ClassVar[list] = [scrape_task, scrape_cron]
    redis_settings: ClassVar[RedisSettings] = get_redis_settings()
    # Run a full scraping session every day at 03:00 UTC (horas mortas)
    cron_jobs: ClassVar[list] = [
        cron(scrape_cron, hour=3, minute=0),
    ]
    max_jobs: ClassVar[int] = 2
    job_timeout: ClassVar[int] = 600  # 10 minutes max per scraping session
