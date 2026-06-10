from collections.abc import Sequence
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.filter import Filter
from app.models.user import User
from app.schemas.filter import FilterConfig, FilterCreate, FilterResponse, FilterUpdate

router = APIRouter()


def _owned_or_404(filter_row: Filter | None, user_id: UUID) -> Filter:
    if filter_row is None or filter_row.user_id != user_id:
        raise HTTPException(status_code=404, detail="Filter not found")
    return filter_row


def _to_response(row: Filter) -> FilterResponse:
    return FilterResponse(
        id=row.id,
        name=row.name,
        config=FilterConfig.model_validate(row.config),
        notify=row.notify,
        notify_digest=row.notify_digest,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.get("", response_model=list[FilterResponse])
async def list_filters(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Sequence[Filter]:
    result = await db.execute(select(Filter).where(Filter.user_id == user.id))
    return result.scalars().all()


@router.post("", response_model=FilterResponse, status_code=status.HTTP_201_CREATED)
async def create_filter(
    body: FilterCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FilterResponse:
    row = Filter(
        user_id=user.id,
        name=body.name,
        config=body.config.model_dump(),
        notify=body.notify,
        notify_digest=body.notify_digest,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return _to_response(row)


@router.get("/{filter_id}", response_model=FilterResponse)
async def get_filter(
    filter_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FilterResponse:
    row = await db.get(Filter, filter_id)
    row = _owned_or_404(row, user.id)
    return _to_response(row)


@router.put("/{filter_id}", response_model=FilterResponse)
async def replace_filter(
    filter_id: UUID,
    body: FilterCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FilterResponse:
    row = await db.get(Filter, filter_id)
    row = _owned_or_404(row, user.id)
    row.name = body.name
    row.config = body.config.model_dump()
    row.notify = body.notify
    row.notify_digest = body.notify_digest
    await db.commit()
    await db.refresh(row)
    return _to_response(row)


@router.patch("/{filter_id}", response_model=FilterResponse)
async def patch_filter(
    filter_id: UUID,
    body: FilterUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FilterResponse:
    row = await db.get(Filter, filter_id)
    row = _owned_or_404(row, user.id)
    if body.name is not None:
        row.name = body.name
    if body.config is not None:
        row.config = body.config.model_dump()
    if body.notify is not None:
        row.notify = body.notify
    if body.notify_digest is not None:
        row.notify_digest = body.notify_digest
    await db.commit()
    await db.refresh(row)
    return _to_response(row)


@router.delete("/{filter_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_filter(
    filter_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    row = await db.get(Filter, filter_id)
    row = _owned_or_404(row, user.id)
    await db.delete(row)
    await db.commit()
