"""Run one incremental market-data refresh on weekday evenings (UTC)."""

import logging
import threading
import time
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import text

from database import ETLMetadata, engine, get_db_session, init_db


logger = logging.getLogger(__name__)
MARKET_TIMEZONE = ZoneInfo("America/New_York")
CAPTURE_TIMEZONE = ZoneInfo("America/Mexico_City")
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


def _last_weekday_of_month(year: int, month: int) -> date:
    day = date(year + (month == 12), 1 if month == 12 else month + 1, 1) - timedelta(days=1)
    while day.weekday() >= 5:
        day -= timedelta(days=1)
    return day


def _should_collect_capitol_signals(now: datetime) -> bool:
    session = get_db_session()
    try:
        last_collection = (
            session.query(ETLMetadata)
            .filter(ETLMetadata.key == "capitol_signal_last_collection")
            .first()
        )
        last_collection_date = (
            datetime.fromisoformat(last_collection.value).date()
            if last_collection and last_collection.value
            else None
        )
    finally:
        session.close()

    if last_collection_date is None:
        return True
    if now.date() == _last_weekday_of_month(now.year, now.month):
        return last_collection_date < now.date()

    previous_month_end = now.date().replace(day=1) - timedelta(days=1)
    previous_month_refresh = _last_weekday_of_month(previous_month_end.year, previous_month_end.month)
    return last_collection_date < previous_month_refresh and now.date() > previous_month_refresh


def _record_capitol_collection(timestamp: datetime) -> None:
    session = get_db_session()
    try:
        session.merge(
            ETLMetadata(
                key="capitol_signal_last_collection",
                value=timestamp.isoformat(),
                updated_at=timestamp.date(),
            )
        )
        session.commit()
    finally:
        session.close()


def _collect_capitol_signals(as_of: date, collected_at: datetime) -> None:
    from politician_trades_pipeline import main as collect_capitol_signals

    logger.info("Starting Capitol Trades point-in-time collection for %s.", as_of)
    signals = collect_capitol_signals(as_of=as_of)
    if signals.empty:
        raise RuntimeError("Capitol Trades collection produced no signal rows.")
    _record_capitol_collection(collected_at)
    logger.info("Saved Capitol Trades signal snapshot for %s.", as_of)


def _run_initial_capitol_collection() -> None:
    init_db()
    connection = engine.connect()
    locked = False
    try:
        locked = bool(
            connection.execute(
                text("SELECT pg_try_advisory_lock(:lock_id)"),
                {"lock_id": ADVISORY_LOCK_ID},
            ).scalar()
        )
        if not locked or _read_timestamp("capitol_signal_last_collection"):
            return
        collected_at = datetime.now(MARKET_TIMEZONE)
        _collect_capitol_signals(datetime.now(CAPTURE_TIMEZONE).date(), collected_at)
    except Exception:
        logger.exception("Initial Capitol Trades collection failed; it will retry at the next scheduled refresh.")
    finally:
        if locked:
            connection.execute(
                text("SELECT pg_advisory_unlock(:lock_id)"),
                {"lock_id": ADVISORY_LOCK_ID},
            )
        connection.close()


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

        if _should_collect_capitol_signals(now):
            _collect_capitol_signals(now.date(), now)
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
    _run_initial_capitol_collection()
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
