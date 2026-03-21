from typing import Any

import httpx

from backend.config import GAMMA_API_BASE, DATA_API_BASE

_TIMEOUT = 20.0


async def _get(base: str, path: str, params: dict | None = None) -> Any:
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.get(f"{base}{path}", params=params)
        resp.raise_for_status()
        return resp.json()


async def get_profile(address: str) -> dict:
    return await _get(GAMMA_API_BASE, "/public-profile", {"address": address})


async def get_positions(
    address: str, limit: int = 100, offset: int = 0, sort_by: str = "CURRENT"
) -> list[dict]:
    return await _get(
        DATA_API_BASE,
        "/positions",
        {
            "user": address,
            "limit": limit,
            "offset": offset,
            "sortBy": sort_by,
            "sortDirection": "DESC",
            "sizeThreshold": 0,
        },
    )


async def get_trades(
    address: str, limit: int = 100, offset: int = 0
) -> list[dict]:
    return await _get(
        DATA_API_BASE,
        "/trades",
        {"user": address, "limit": limit, "offset": offset},
    )


async def get_portfolio_value(address: str) -> float:
    data = await _get(DATA_API_BASE, "/value", {"user": address})
    if isinstance(data, list) and data:
        return float(data[0].get("value", 0))
    return 0.0


async def get_activity(
    address: str,
    start: int | None = None,
    end: int | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict]:
    params: dict[str, Any] = {"user": address, "limit": limit, "offset": offset}
    if start:
        params["start"] = start
    if end:
        params["end"] = end
    return await _get(DATA_API_BASE, "/activity", params)


async def get_sports_leaderboard(
    period: str = "WEEK", order_by: str = "PNL", limit: int = 50, offset: int = 0
) -> list[dict]:
    return await _get(
        DATA_API_BASE,
        "/v1/leaderboard",
        {
            "category": "SPORTS",
            "timePeriod": period,
            "orderBy": order_by,
            "limit": limit,
            "offset": offset,
        },
    )


async def get_sports_metadata() -> list[dict]:
    return await _get(GAMMA_API_BASE, "/sports")


async def get_sports_markets(
    tag_id: int | None = None,
    limit: int = 50,
    offset: int = 0,
    order: str = "liquidity",
) -> list[dict]:
    params: dict[str, Any] = {
        "active": "true",
        "closed": "false",
        "limit": limit,
        "offset": offset,
    }
    if order:
        params["order"] = order
        params["ascending"] = "false"
    if tag_id:
        params["tag_id"] = tag_id
    return await _get(GAMMA_API_BASE, "/markets", params)


async def get_market_holders(condition_id: str, limit: int = 20) -> list[dict]:
    return await _get(
        DATA_API_BASE,
        "/holders",
        {"market": condition_id, "limit": limit},
    )
