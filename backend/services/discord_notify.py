import json
import logging

import httpx

from backend.config import DISCORD_WEBHOOK_URL

log = logging.getLogger("discord_notify")

_TIMEOUT = 10.0
_AMBER = 0xF59E0B


def _cents_to_american(price: float) -> int:
    if not price or price <= 0 or price >= 1:
        return 0
    if price >= 0.5:
        return round(-100 * price / (1 - price))
    return round(100 * (1 - price) / price)


def _fmt_odds(n: int) -> str:
    return f"+{n}" if n > 0 else str(n)


def _is_better_odds(book_odds: int, sharp_odds: int) -> bool:
    if book_odds > 0 and sharp_odds > 0:
        return book_odds > sharp_odds
    if book_odds < 0 and sharp_odds < 0:
        return book_odds > sharp_odds
    if book_odds > 0 and sharp_odds < 0:
        return True
    return False


def _side_matches_outcome(side_key: str, outcome: str) -> bool:
    if not outcome:
        return False
    s = side_key.lower()
    words = outcome.lower().split()
    return any(w in s for w in words if len(w) > 2)


def _build_embed(alert, wallet, e7_data: dict) -> dict | None:
    sharp_am = _cents_to_american(alert.price)
    best_books = e7_data.get("best_books", {})
    all_books = e7_data.get("all_books", {})
    sides = list(best_books.keys())

    if not sides:
        return None

    sharp_side_key = next(
        (s for s in sides if _side_matches_outcome(s, alert.outcome)),
        sides[0],
    )

    better_lines = []
    for book_name, book_data in all_books.items():
        if book_name in ("Polymarket", "Prophet X", "Kalshi"):
            continue
        side_data = book_data.get(sharp_side_key)
        if not side_data:
            continue
        try:
            book_odds = int(side_data.get("am_odds", 0))
        except (ValueError, TypeError):
            continue
        if _is_better_odds(book_odds, sharp_am):
            better_lines.append({
                "book": book_name,
                "odds": book_odds,
                "ev": side_data.get("ev", 0),
                "link": side_data.get("betlink", ""),
            })

    if not better_lines:
        return None

    better_lines.sort(key=lambda x: -x["odds"] if x["odds"] > 0 else x["odds"])

    vol = float(wallet.volume or 0)
    pnl = float(wallet.pnl or 0)
    roi = round(pnl / vol * 100, 1) if vol else 0.0
    label = wallet.label or wallet.profile_name or wallet.address[:10]

    lines_text = "\n".join(
        f"{'🟢 ' if b['ev'] > 0 else ''}"
        f"**{b['book']}** {_fmt_odds(b['odds'])} "
        f"({'+' if b['ev'] > 0 else ''}{b['ev']:.1f}% EV)"
        f"{' — [Bet](' + b['link'] + ')' if b['link'] else ''}"
        for b in better_lines[:8]
    )

    match_name = e7_data.get("match_short") or e7_data.get("match", "")
    prop_stat = e7_data.get("prop", "")
    if e7_data.get("stat"):
        prop_stat += f" · {e7_data['stat']}"

    return {
        "embeds": [{
            "title": f"WINDOW SHOPPER — {alert.sport or 'Sports'}",
            "color": _AMBER,
            "fields": [
                {
                    "name": "Sharp",
                    "value": f"{label} · {'+' if roi > 0 else ''}{roi}% ROI · {'+' if pnl >= 0 else ''}${pnl:,.0f} net",
                    "inline": False,
                },
                {
                    "name": "Play",
                    "value": (
                        f"**{match_name}**\n"
                        f"{prop_stat}\n"
                        f"**{alert.outcome}** · ${alert.size:,.0f} at {_fmt_odds(sharp_am)}"
                    ),
                    "inline": False,
                },
                {
                    "name": f"Better Prices ({len(better_lines)})",
                    "value": lines_text,
                    "inline": False,
                },
            ],
            "footer": {
                "text": "Not financial advice. Informational only \u2014 do your own research before placing any wagers.",
            },
        }],
    }


async def send_alert(alert, wallet, e7_data: dict):
    if not DISCORD_WEBHOOK_URL:
        return

    payload = _build_embed(alert, wallet, e7_data)
    if not payload:
        log.debug("No books beat sharp price for %s, skipping Discord", alert.title[:40])
        return

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(DISCORD_WEBHOOK_URL, json=payload)
            if resp.status_code == 204:
                log.info("Discord notification sent: %s", alert.title[:50])
            else:
                log.warning("Discord webhook returned %d: %s", resp.status_code, resp.text[:200])
    except Exception as e:
        log.warning("Discord notification failed: %s", e)
