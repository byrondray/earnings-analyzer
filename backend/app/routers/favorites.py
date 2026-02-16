from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.db.database import get_db
from app.db.models import UserFavorite

router = APIRouter(prefix="/api/favorites", tags=["favorites"])


class FavoriteResponse(BaseModel):
    ticker: str
    company_name: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class FavoriteCheckResponse(BaseModel):
    favorites: dict[str, bool]


@router.get("/", response_model=List[FavoriteResponse])
async def list_favorites(
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UserFavorite)
        .where(UserFavorite.clerk_user_id == user_id)
        .order_by(UserFavorite.created_at.desc())
    )
    return result.scalars().all()


@router.get("/check", response_model=FavoriteCheckResponse)
async def check_favorites(
    tickers: List[str] = Query(default=[]),
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not tickers:
        return {"favorites": {}}

    result = await db.execute(
        select(UserFavorite.ticker)
        .where(
            UserFavorite.clerk_user_id == user_id,
            UserFavorite.ticker.in_(tickers),
        )
    )
    favorited = {row[0] for row in result.all()}
    return {"favorites": {t: t in favorited for t in tickers}}


@router.post("/{ticker}", status_code=status.HTTP_201_CREATED, response_model=FavoriteResponse)
async def add_favorite(
    ticker: str,
    company_name: str | None = Query(default=None),
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    ticker = ticker.upper()

    existing = await db.execute(
        select(UserFavorite).where(
            UserFavorite.clerk_user_id == user_id,
            UserFavorite.ticker == ticker,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Already in favorites",
        )

    favorite = UserFavorite(
        clerk_user_id=user_id,
        ticker=ticker,
        company_name=company_name,
    )
    db.add(favorite)
    await db.commit()
    await db.refresh(favorite)
    return favorite


@router.delete("/{ticker}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_favorite(
    ticker: str,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    ticker = ticker.upper()
    result = await db.execute(
        delete(UserFavorite).where(
            UserFavorite.clerk_user_id == user_id,
            UserFavorite.ticker == ticker,
        )
    )
    await db.commit()
    if result.rowcount == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Favorite not found",
        )
