"""Anonymous analytics — scan and retailer-click counters.

No user id, email, IP, device id, or session id is ever written. Counters are
keyed by (date, event, key) with a single atomic $inc. This gives the admin
"how many times was product X scanned on 2026-09-23" and "how many taps went
from product X to Amazon India" without any personally identifiable data.
"""
import csv
import io
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from core.config import db
from core.deps import admin_user

router = APIRouter()


class TrackEvent(BaseModel):
    """Public event schema. Server strips anything unexpected — never stores identity."""
    event: str = Field(pattern=r"^(scan|retailer_click|contribute|share)$")
    barcode: Optional[str] = Field(default=None, max_length=32)
    retailer_id: Optional[str] = Field(default=None, max_length=32)
    category: Optional[str] = Field(default=None, max_length=32)
    country: Optional[str] = Field(default=None, max_length=6)


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


async def record(event: str, *, barcode: Optional[str] = None,
                 retailer_id: Optional[str] = None, category: Optional[str] = None,
                 country: Optional[str] = None) -> None:
    """Callable from any router. Fire-and-forget style — never raises."""
    try:
        today = _today()
        base = {"date": today, "event": event}
        # Overall counter
        await db.analytics_daily.update_one(
            {**base, "key": "_total"},
            {"$inc": {"count": 1}, "$setOnInsert": {**base, "key": "_total"}},
            upsert=True,
        )
        # Per-key counter (barcode or retailer)
        key = None
        if event in ("scan", "contribute") and barcode:
            key = f"barcode:{barcode}"
        elif event == "retailer_click" and retailer_id:
            key = f"retailer:{retailer_id}"
        elif event == "share" and barcode:
            key = f"barcode:{barcode}"
        if key:
            await db.analytics_daily.update_one(
                {**base, "key": key},
                {"$inc": {"count": 1}, "$setOnInsert": {**base, "key": key,
                                                        "category": category}},
                upsert=True,
            )
        # Category breakdown per event
        if category:
            cat_key = f"category:{category}"
            await db.analytics_daily.update_one(
                {**base, "key": cat_key},
                {"$inc": {"count": 1}, "$setOnInsert": {**base, "key": cat_key, "category": category}},
                upsert=True,
            )
        # Country breakdown per event
        if country:
            co_key = f"country:{country.upper()}"
            await db.analytics_daily.update_one(
                {**base, "key": co_key},
                {"$inc": {"count": 1}, "$setOnInsert": {**base, "key": co_key, "country": country.upper()}},
                upsert=True,
            )
        # Cross-key for retailer click on a specific product
        if event == "retailer_click" and retailer_id and barcode:
            cross = f"retailer:{retailer_id}|barcode:{barcode}"
            await db.analytics_daily.update_one(
                {**base, "key": cross},
                {"$inc": {"count": 1}, "$setOnInsert": {**base, "key": cross,
                                                        "retailer_id": retailer_id, "barcode": barcode}},
                upsert=True,
            )
    except Exception:  # noqa: BLE001 — analytics must NEVER break UX
        pass


@router.post("/analytics/track")
async def track(payload: TrackEvent) -> Dict[str, str]:
    await record(payload.event, barcode=payload.barcode,
                 retailer_id=payload.retailer_id, category=payload.category,
                 country=payload.country)
    return {"status": "recorded"}


def _csv_safe(value: Any) -> Any:
    """Neutralize CSV formula injection — prefix a quote to any cell that a
    spreadsheet would interpret as a formula (leading = + - @, tab, or CR)."""
    if isinstance(value, str) and value and value[0] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + value
    return value


def _date_range(days: int) -> List[str]:
    today = datetime.now(timezone.utc).date()
    return [(today - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(days)][::-1]


@router.get("/admin/analytics/overview")
async def analytics_overview(days: int = 30, _: Dict[str, Any] = Depends(admin_user)) -> Dict[str, Any]:
    days = max(1, min(days, 90))
    dates = _date_range(days)
    start = dates[0]
    # Totals per event per day
    pipeline_daily = [
        {"$match": {"date": {"$gte": start}, "key": "_total"}},
        {"$group": {"_id": {"date": "$date", "event": "$event"}, "count": {"$sum": "$count"}}},
        {"$sort": {"_id.date": 1}},
    ]
    per_day = await db.analytics_daily.aggregate(pipeline_daily).to_list(1000)
    daily: Dict[str, Dict[str, int]] = {d: {"scan": 0, "retailer_click": 0, "contribute": 0, "share": 0} for d in dates}
    for row in per_day:
        d = row["_id"]["date"]; e = row["_id"]["event"]
        if d in daily:
            daily[d][e] = row["count"]

    # Top products by scans
    pipeline_top_products = [
        {"$match": {"date": {"$gte": start}, "event": "scan", "key": {"$regex": "^barcode:"}}},
        {"$group": {"_id": "$key", "count": {"$sum": "$count"}}},
        {"$sort": {"count": -1}},
        {"$limit": 20},
    ]
    top_products_raw = await db.analytics_daily.aggregate(pipeline_top_products).to_list(20)
    top_products = []
    for row in top_products_raw:
        barcode = row["_id"].split(":", 1)[1]
        product = await db.products.find_one({"barcode": barcode}, {"_id": 0, "name": 1, "brand": 1, "category": 1})
        top_products.append({
            "barcode": barcode, "count": row["count"],
            "name": (product or {}).get("name", "Unknown"),
            "brand": (product or {}).get("brand", ""),
            "category": (product or {}).get("category", ""),
        })

    # Retailer clicks breakdown
    pipeline_retailers = [
        {"$match": {"date": {"$gte": start}, "event": "retailer_click", "key": {"$regex": "^retailer:[^|]+$"}}},
        {"$group": {"_id": "$key", "count": {"$sum": "$count"}}},
        {"$sort": {"count": -1}},
    ]
    retailer_rows = await db.analytics_daily.aggregate(pipeline_retailers).to_list(50)
    retailers = [{"retailer_id": row["_id"].split(":", 1)[1], "count": row["count"]}
                 for row in retailer_rows]

    # Category breakdown across scans + retailer clicks
    pipeline_categories = [
        {"$match": {"date": {"$gte": start}, "key": {"$regex": "^category:"}}},
        {"$group": {"_id": {"cat": "$key", "event": "$event"}, "count": {"$sum": "$count"}}},
        {"$sort": {"count": -1}},
    ]
    cat_rows = await db.analytics_daily.aggregate(pipeline_categories).to_list(60)
    categories: Dict[str, Dict[str, int]] = {}
    for row in cat_rows:
        cat = row["_id"]["cat"].split(":", 1)[1]
        ev = row["_id"]["event"]
        categories.setdefault(cat, {"scan": 0, "retailer_click": 0, "contribute": 0, "share": 0})
        categories[cat][ev] = categories[cat].get(ev, 0) + row["count"]
    category_list = [{"category": k, **v, "total": sum(v.values())}
                     for k, v in categories.items()]
    category_list.sort(key=lambda r: r["total"], reverse=True)

    # Country breakdown across scans
    pipeline_countries = [
        {"$match": {"date": {"$gte": start}, "event": "scan", "key": {"$regex": "^country:"}}},
        {"$group": {"_id": "$key", "count": {"$sum": "$count"}}},
        {"$sort": {"count": -1}},
    ]
    country_rows = await db.analytics_daily.aggregate(pipeline_countries).to_list(60)
    countries = [{"country": row["_id"].split(":", 1)[1], "count": row["count"]}
                 for row in country_rows]

    totals = {
        "scan": sum(d["scan"] for d in daily.values()),
        "retailer_click": sum(d["retailer_click"] for d in daily.values()),
        "contribute": sum(d["contribute"] for d in daily.values()),
        "share": sum(d["share"] for d in daily.values()),
    }
    return {
        "days": days, "totals": totals,
        "daily": [{"date": d, **daily[d]} for d in dates],
        "top_products": top_products, "retailers": retailers,
        "categories": category_list, "countries": countries,
    }


@router.get("/admin/analytics/export")
async def analytics_export(_: Dict[str, Any] = Depends(admin_user), days: int = 90) -> StreamingResponse:
    """Downloadable CSV: date, event, key, count. No personal data."""
    days = max(1, min(days, 365))
    start = (datetime.now(timezone.utc).date() - timedelta(days=days)).strftime("%Y-%m-%d")
    rows = await db.analytics_daily.find(
        {"date": {"$gte": start}}, {"_id": 0}
    ).sort([("date", 1), ("event", 1)]).to_list(50000)
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["date", "event", "key", "count", "category", "retailer_id", "barcode"])
    for row in rows:
        writer.writerow([
            _csv_safe(row.get("date", "")), _csv_safe(row.get("event", "")),
            _csv_safe(row.get("key", "")), row.get("count", 0),
            _csv_safe(row.get("category", "")), _csv_safe(row.get("retailer_id", "")),
            _csv_safe(row.get("barcode", "")),
        ])
    buffer.seek(0)
    filename = f"veriscan-analytics-{date.today().isoformat()}.csv"
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
