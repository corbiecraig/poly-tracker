from fastapi import APIRouter, Query

from backend.services import polymarket as pm

router = APIRouter(prefix="/api/markets", tags=["markets"])


@router.get("/sports")
async def sports_markets(
    tag_id: int | None = Query(None),
    limit: int = Query(50, le=100),
    offset: int = Query(0),
):
    return await pm.get_sports_markets(tag_id=tag_id, limit=limit, offset=offset)


@router.get("/sports/metadata")
async def sports_metadata():
    return await pm.get_sports_metadata()


@router.get("/{condition_id}/holders")
async def market_holders(condition_id: str):
    return await pm.get_market_holders(condition_id)
