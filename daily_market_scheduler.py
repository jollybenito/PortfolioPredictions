"""Run one incremental market-data refresh on weekday evenings (UTC)."""

import logging
import threading
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import text

from database import ETLMetadata, engine, get_db_session


logger = logging.getLogger(__name__)
MARKET_TIMEZONE = ZoneInfo("America/New_York")
SCHEDULE_LOCAL_MINUTE = 16 * 60 + 30  # 16:30 ET, 30 minutes after the regular close.
ADVISORY_LOCK_ID = 712630114


def _read_timestamp(key: str):
    session = get_db_session()
    try:
        record = session.query(ETLMetadata).filter(ETLMetadata.key == key).first()
        if not record or not record.value:
            return None
        return datetime.fromisoformat(record.value)
    finally:
        session.close()


def _record_attempt(timestamp: datetime) -> None:
    session = get_db_session()
    try:
        session.merge(
            ETLMetadata(
                key="daily_market_update_attempt",
                value=timestamp.isoformat(),
                updated_at=timestamp.date(),
            )
        )
        session.commit()
    finally:
        session.close()


def _run_once_for_today(now: datetime) -> None:
    connection = engine.connect()
    locked = False
    try:
        locked = bool(
            connection.execute(
                text("SELECT pg_try_advisory_lock(:lock_id)"),
                {"lock_id": ADVISORY_LOCK_ID},
            ).scalar()
        )
        if not locked:
            attempted_at = _read_timestamp("daily_market_update_attempt")
            if not attempted_at or attempted_at.date() != now.date():
                logger.info("A daily market update is already running in another app instance.")
            return

        attempted_at = _read_timestamp("daily_market_update_attempt")
        if attempted_at and attempted_at.date() == now.date():
            return

        _record_attempt(now)
        logger.info("Starting scheduled market refresh at %s.", now.isoformat())
        from scripts.update_daily_market import main as update_daily_market

        update_daily_market()
        logger.info("Scheduled market refresh finished successfully.")
    except Exception:
        # Leave the attempt marker in place to avoid repeatedly hammering Yahoo
        # Finance every minute if a provider or database error occurs.
        logger.exception("Scheduled market refresh failed; the next attempt will be on the next weekday.")
    finally:
        if locked:
            connection.execute(
                text("SELECT pg_advisory_unlock(:lock_id)"),
                {"lock_id": ADVISORY_LOCK_ID},
            )
        connection.close()


def run_scheduler() -> None:
    logger.info("Daily market scheduler active: weekdays at 16:30 America/New_York.")
    attempted_today = None
    while True:
        now = datetime.now(MARKET_TIMEZONE).replace(second=0, microsecond=0)
        minute_of_day = now.hour * 60 + now.minute
        if (
            now.weekday() < 5
            and minute_of_day >= SCHEDULE_LOCAL_MINUTE
            and attempted_today != now.date()
        ):
            attempted_today = now.date()
            _run_once_for_today(now)
        time.sleep(30)


def start_scheduler() -> threading.Thread:
    thread = threading.Thread(target=run_scheduler, name="daily-market-scheduler", daemon=True)
    thread.start()
    return thread
