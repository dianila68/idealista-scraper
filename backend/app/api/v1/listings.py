import base64
import json
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.filter import Filter
from app.models.listing import Listing
from app.models.user import User
from app.schemas.listing import ListingDetailResponse, ListingPage, ListingResponse, SourceStatus

router = APIRouter()

SOURCES = ["idealista", "immobiliare", "subito"]


def _encode_cursor(scraped_at: datetime, listing_id: UUID) -> str:
    payload = json.dumps({"t": scraped_at.isoformat(), "id": str(listing_id)})
    return base64.urlsafe_b64encode(payload.encode()).decode()


def _decode_cursor(cursor: str) -> tuple[datetime, UUID]:
    payload = json.loads(base64.urlsafe_b64decode(cursor.encode()))
    return datetime.fromisoformat(payload["t"]), UUID(payload["id"])


@router.get("", response_model=ListingPage)
async def list_listings(
    filter_id: UUID | None = Query(default=None),
    source: str | None = Query(default=None),
    cursor: str | None = Query(default=None),
    per_page: int = Query(default=20, ge=1, le=100),
    sort: str = Query(default="newest"),
    suggest_roommate: bool = Query(default=False),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(Listing)

    if filter_id is not None:
        filter_row = await db.get(Filter, filter_id)
        if filter_row is None or filter_row.user_id != user.id:
            raise HTTPException(status_code=404, detail="Filter not found")
        config = filter_row.config
        _apply_filter_config(query, config)

    if source is not None:
        if source not in SOURCES:
            raise HTTPException(status_code=400, detail=f"Unknown source: {source}")
        query = query.where(Listing.source == source)

    if cursor is not None:
        try:
            cur_time, cur_id = _decode_cursor(cursor)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid cursor")
        query = query.where(
            (Listing.scraped_at < cur_time)
            | ((Listing.scraped_at == cur_time) & (Listing.id < cur_id))
        )

    if sort == "price_asc":
        query = query.order_by(Listing.price.asc().nullslast(), Listing.scraped_at.desc())
    elif sort == "price_desc":
        query = query.order_by(Listing.price.desc().nullsfirst(), Listing.scraped_at.desc())
    else:
        query = query.order_by(Listing.scraped_at.desc(), Listing.id.desc())

    count_q = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_q) or 0

    result = await db.execute(query.limit(per_page + 1))
    rows = result.scalars().all()
    has_more = len(rows) > per_page
    rows = rows[:per_page]

    next_cursor = None
    if has_more and rows:
        last = rows[-1]
        next_cursor = _encode_cursor(last.scraped_at, last.id)

    suggestions: list[ListingResponse] = []
    if suggest_roommate and filter_id is not None:
        filter_row = await db.get(Filter, filter_id)
        if filter_row:
            suggestions = await _roommate_suggestions(db, filter_row.config, per_page=5)

    return ListingPage(
        results=[ListingResponse.model_validate(r) for r in rows],
        suggestions=suggestions,
        total_count=total,
        next_cursor=next_cursor,
        has_more=has_more,
    )


@router.get("/sources", response_model=list[SourceStatus])
async def list_sources(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    statuses = []
    for src in SOURCES:
        count = await db.scalar(select(func.count()).where(Listing.source == src)) or 0
        last = await db.scalar(
            select(func.max(Listing.scraped_at)).where(Listing.source == src)
        )
        statuses.append(
            SourceStatus(source=src, last_scraped_at=last, listing_count=count, is_healthy=True)
        )
    return statuses


@router.get("/{listing_id}", response_model=ListingDetailResponse)
async def get_listing(
    listing_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    row = await db.get(Listing, listing_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Listing not found")
    return ListingDetailResponse.model_validate(row)


def _apply_filter_config(query, config: dict):
    """Narrow a Listing query based on a stored filter config dict."""
    from app.schemas.filter import FilterConfig
    fc = FilterConfig.model_validate(config)
    if fc.listing_type:
        query = query.where(Listing.listing_type == fc.listing_type)
    if fc.price.max is not None:
        query = query.where((Listing.price <= fc.price.max) | (Listing.price.is_(None)))
    if fc.price.min is not None:
        query = query.where((Listing.price >= fc.price.min) | (Listing.price.is_(None)))
    if fc.size_sqm.min is not None:
        query = query.where((Listing.size_sqm >= fc.size_sqm.min) | (Listing.size_sqm.is_(None)))
    if fc.rooms.min is not None:
        query = query.where((Listing.rooms >= fc.rooms.min) | (Listing.rooms.is_(None)))
    if fc.locations:
        cities = [loc.city for loc in fc.locations]
        query = query.where(Listing.city.in_(cities))
    return query


async def _roommate_suggestions(db: AsyncSession, config: dict, per_page: int) -> list[ListingResponse]:
    from app.core.config import settings
    from app.schemas.filter import FilterConfig
    fc = FilterConfig.model_validate(config)
    if fc.price.max is None:
        return []
    apartment_budget = fc.price.max * settings.roommate_price_multiplier
    q = select(Listing).where(
        Listing.listing_type == "rent",
        Listing.price <= apartment_budget,
    )
    if fc.locations:
        q = q.where(Listing.city.in_([loc.city for loc in fc.locations]))
    q = q.order_by(Listing.scraped_at.desc()).limit(per_page)
    result = await db.execute(q)
    return [ListingResponse.model_validate(r) for r in result.scalars().all()]
