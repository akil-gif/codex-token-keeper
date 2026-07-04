"""定时刷新调度器"""
from __future__ import annotations

import asyncio

from app.config import config
from app.logger import logger
from app.oauth import refresh_all


async def scheduler_loop():
    """后台循环：每 N 小时刷新所有账号"""
    interval = config.REFRESH_INTERVAL_HOURS * 3600
    logger.info(f"Scheduler started: refresh every {config.REFRESH_INTERVAL_HOURS}h")

    # 启动后等 10 秒再开始第一次
    await asyncio.sleep(10)

    while True:
        try:
            logger.info("Scheduled refresh starting...")
            await refresh_all(force=False)
        except Exception as e:
            logger.error(f"Scheduled refresh error: {e}")

        await asyncio.sleep(interval)


async def startup_refresh():
    """启动时立即刷新一次所有 pending 账号"""
    try:
        await refresh_all(force=False)
    except Exception as e:
        logger.error(f"Startup refresh error: {e}")
