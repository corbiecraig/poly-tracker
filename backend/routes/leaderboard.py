from fastapi import APIRouter, Query

from backend.services import polymarket as pm

router = APIRouter(prefix="/api/leaderboard", tags=["leaderboard"])


@router.get("/sports")
async def sports_leaderboard(
    period: str = Query("WEEK", pattern="^(DAY|WEEK|MONTH|ALL)$"),
    order_by: str = Query("PNL", pattern="^(PNL|VOL)$"),
    limit: int = Query(50, le=50),
    offset: int = Query(0),
):
    rows = await pm.get_sports_leaderboard(
        period=period, order_by=order_by, limit=limit, offset=offset
    )
    for row in rows:
        vol = float(row.get("vol") or 0)
        pnl = float(row.get("pnl") or 0)
        row["roi_pct"] = round(pnl / vol * 100, 1) if vol else 0.0
    return rows
