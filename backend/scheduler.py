"""Background scheduler — trial reminders and monthly admin analytics reports.

Runs a single asyncio task that wakes every hour. It sends:
- Trial reminders: 7 days before `trial_expires_at` (once per user, tracked
  via `trial_reminder_sent_at`).
- Monthly analytics report: on the first day of each month, delivered to
  every admin user's email, containing the previous month's totals, top
  scanned products and retailer tap breakdown.

Fail-quiet: all work is wrapped so any provider outage never crashes uvicorn.
"""
import asyncio
import calendar
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from core.config import db
from emailer import render_admin_monthly_report, render_trial_reminder, send_email

logger = logging.getLogger(__name__)

TRIAL_REMINDER_DAYS = 7
_TASK: asyncio.Task | None = None


async def _send_trial_reminders() -> int:
    """Find users whose trial ends within `TRIAL_REMINDER_DAYS` days and haven't
    been reminded yet. Returns the number of reminders sent."""
    now = datetime.now(timezone.utc)
    window_end = (now + timedelta(days=TRIAL_REMINDER_DAYS + 1)).isoformat()
    window_start = now.isoformat()
    cursor = db.users.find({
        "role": "user",
        "suspended": {"$ne": True},
        "trial_expires_at": {"$gte": window_start, "$lte": window_end},
        "trial_reminder_sent_at": {"$exists": False},
    }, {"_id": 0, "id": 1, "email": 1, "trial_expires_at": 1})
    sent = 0
    async for user in cursor:
        try:
            expires = datetime.fromisoformat(user["trial_expires_at"])
            days_left = max(1, int((expires - now).total_seconds() // 86400))
            subject, html = render_trial_reminder(days_left)
            await send_email(to=user["email"], subject=subject, html=html)
            await db.users.update_one(
                {"id": user["id"]},
                {"$set": {"trial_reminder_sent_at": now.isoformat()}},
            )
            sent += 1
        except Exception as exc:  # noqa: BLE001
            logger.warning("Trial reminder skipped for %s: %s", user.get("id"), exc)
    if sent:
        logger.info("Trial reminders sent: %s", sent)
    return sent


async def _send_monthly_reports(force: bool = False) -> int:
    """On the first day of the month (or when force=True), email each admin an
    analytics summary of the previous month. Idempotent — uses a
    `monthly_report_log` collection to ensure at-most-once delivery per admin
    per period."""
    now = datetime.now(timezone.utc)
    if now.day != 1 and not force:
        return 0
    # Previous month period (YYYY-MM)
    if now.month == 1:
        period_year, period_month = now.year - 1, 12
    else:
        period_year, period_month = now.year, now.month - 1
    period = f"{period_year:04d}-{period_month:02d}"
    start = f"{period}-01"
    last_day = calendar.monthrange(period_year, period_month)[1]
    end = f"{period}-{last_day:02d}"

    # Aggregate previous month's counters
    pipeline_totals = [
        {"$match": {"date": {"$gte": start, "$lte": end}, "key": "_total"}},
        {"$group": {"_id": "$event", "count": {"$sum": "$count"}}},
    ]
    total_rows = await db.analytics_daily.aggregate(pipeline_totals).to_list(50)
    totals = {row["_id"]: row["count"] for row in total_rows}

    pipeline_products = [
        {"$match": {"date": {"$gte": start, "$lte": end}, "event": "scan",
                    "key": {"$regex": "^barcode:"}}},
        {"$group": {"_id": "$key", "count": {"$sum": "$count"}}},
        {"$sort": {"count": -1}},
        {"$limit": 10},
    ]
    product_rows = await db.analytics_daily.aggregate(pipeline_products).to_list(10)
    top_products: List[Dict[str, Any]] = []
    for row in product_rows:
        barcode = row["_id"].split(":", 1)[1]
        product = await db.products.find_one({"barcode": barcode}, {"_id": 0, "name": 1})
        top_products.append({"name": (product or {}).get("name", barcode), "count": row["count"]})

    pipeline_retailers = [
        {"$match": {"date": {"$gte": start, "$lte": end}, "event": "retailer_click",
                    "key": {"$regex": "^retailer:[^|]+$"}}},
        {"$group": {"_id": "$key", "count": {"$sum": "$count"}}},
        {"$sort": {"count": -1}},
        {"$limit": 10},
    ]
    retailer_rows = await db.analytics_daily.aggregate(pipeline_retailers).to_list(10)
    top_retailers = [{"retailer_id": row["_id"].split(":", 1)[1], "count": row["count"]}
                     for row in retailer_rows]

    sent = 0
    admins = db.users.find({"role": "admin"}, {"_id": 0, "id": 1, "email": 1})
    async for admin in admins:
        already = await db.monthly_report_log.find_one(
            {"admin_id": admin["id"], "period": period}, {"_id": 0},
        )
        if already:
            continue
        try:
            subject, html = render_admin_monthly_report(period, totals, top_products, top_retailers)
            await send_email(to=admin["email"], subject=subject, html=html)
            await db.monthly_report_log.insert_one({
                "admin_id": admin["id"], "period": period,
                "sent_at": now.isoformat(), "totals": totals,
            })
            sent += 1
        except Exception as exc:  # noqa: BLE001
            logger.warning("Monthly report skipped for admin %s: %s", admin.get("id"), exc)
    if sent:
        logger.info("Monthly report sent to %s admin(s) for %s", sent, period)
    return sent


async def _scheduler_loop() -> None:
    """Wake every hour. Cheap idempotent checks make this safe on every tick."""
    logger.info("VeriScan scheduler started")
    while True:
        try:
            await _send_trial_reminders()
            await _send_monthly_reports()
        except Exception as exc:  # noqa: BLE001
            logger.error("Scheduler tick failed: %s", exc)
        # Sleep 1 hour. In tests we can shorten via env var.
        await asyncio.sleep(int(os.environ.get("VERISCAN_SCHEDULER_INTERVAL_SEC", 3600)))


def start_scheduler() -> None:
    global _TASK
    if _TASK and not _TASK.done():
        return
    try:
        loop = asyncio.get_event_loop()
        _TASK = loop.create_task(_scheduler_loop())
    except RuntimeError:
        logger.warning("No running loop yet — scheduler will start on next startup")
