import logging
import time
from datetime import datetime
from typing import Any

import httpx

from backend.config import ETERNITY7_URL, ETERNITY7_TOKEN

log = logging.getLogger("eternity7")

_TIMEOUT = 20.0
_CACHE_TTL = 300
_cache: dict[str, Any] = {"data": None, "ts": 0}

_GF = "https://www.google.com/s2/favicons?domain={}&sz=64"

SPORTSBOOK_LOGOS = {
    "DraftKings": _GF.format("draftkings.com"),
    "FanDuel": _GF.format("fanduel.com"),
    "Caesars": _GF.format("caesars.com"),
    "BetMGM": _GF.format("betmgm.com"),
    "Kambi": _GF.format("betrivers.com"),
    "Fanatics": _GF.format("fanatics.com"),
    "Hard Rock": _GF.format("hardrocksportsbook.com"),
    "Bovada": _GF.format("bovada.lv"),
    "Bodog": _GF.format("bodog.eu"),
    "Stake": _GF.format("stake.com"),
    "Betway": _GF.format("betway.com"),
    "Sporttrade": _GF.format("sporttrade.com"),
    "Fliff": _GF.format("getfliff.com"),
    "Onyx Odds": _GF.format("onyxodds.com"),
    "Rebet": _GF.format("rebet.app"),
    "William Hill": _GF.format("williamhill.com"),
    "Kalshi": _GF.format("kalshi.com"),
    "ESPN BET": _GF.format("espnbet.com"),
    "BetOnline": _GF.format("betonline.ag"),
    "TheScore": _GF.format("thescore.bet"),
    "Novig": _GF.format("novig.com"),
    "BookMaker": _GF.format("bookmaker.eu"),
}

_NOISE_WORDS = {"fc", "sc", "cf", "afc", "the", "de", "1907", "1913", "1901", "1899"}

GAME_LINE_PROPS = {
    "Moneyline", "Money Line", "Point Spread", "Total Points",
    "Puck Line", "Run Line", "Game Lines", "Spread",
}


async def fetch_feed() -> dict:
    now = time.time()
    if _cache["data"] and (now - _cache["ts"]) < _CACHE_TTL:
        return _cache["data"]

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(
                ETERNITY7_URL,
                headers={"auth_token": ETERNITY7_TOKEN, "Accept-Encoding": "gzip"},
            )
            if resp.status_code != 200:
                log.warning("E7 API returned %d", resp.status_code)
                return _cache["data"] or {}
            data = resp.json()
            _cache["data"] = data
            _cache["ts"] = now
            return data
    except Exception as e:
        log.warning("E7 fetch failed: %s", e)
        return _cache["data"] or {}


def _normalize(name: str) -> str:
    return name.lower().strip().replace(".", "").replace("-", " ").replace("'", "")


def _significant_words(name: str) -> set[str]:
    words = set(_normalize(name).split())
    return words - _NOISE_WORDS


def _team_in_match(team_name: str, e7_match: str) -> bool:
    team_n = _normalize(team_name)
    match_n = _normalize(e7_match)

    if team_n in match_n:
        return True

    e7_sides = [_normalize(s) for s in e7_match.split(" vs ")]
    for side in e7_sides:
        if team_n in side or side in team_n:
            return True

    team_words = _significant_words(team_name)
    if len(team_words) < 1:
        return False

    for side in e7_sides:
        side_words = set(side.split()) - _NOISE_WORDS
        if not side_words:
            continue
        overlap = team_words & side_words
        if len(overlap) >= max(1, len(team_words) - 1) and len(overlap) >= len(side_words):
            return True

    return False


def _parse_e7_date(date_str: str) -> str | None:
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(date_str[:19], fmt).strftime("%Y-%m-%d")
        except (ValueError, TypeError):
            continue
    if date_str and len(date_str) >= 10:
        return date_str[:10]
    return None


PROP_TYPE_TO_E7 = {
    "Spread": {"Point Spread"},
    "Moneyline": {"Moneyline", "Money Line"},
    "Total": {"Total Points"},
}


def find_matching_odds(
    league: str | None,
    team_a: str | None,
    team_b: str | None,
    feed: dict,
    game_date: str | None = None,
    prop_type: str | None = None,
    line: float | None = None,
) -> dict | None:
    if not feed or (not team_a and not team_b):
        return None

    target_props = PROP_TYPE_TO_E7.get(prop_type or "Moneyline", GAME_LINE_PROPS)

    best_match = None
    best_book_count = 0

    for entry in feed.values():
        if league and entry.get("League") != league:
            continue

        if game_date:
            e7_date = _parse_e7_date(entry.get("Date", ""))
            if e7_date != game_date:
                continue

        e7_match = entry.get("Match", "")

        if team_a and not _team_in_match(team_a, e7_match):
            continue
        if team_b and not _team_in_match(team_b, e7_match):
            continue

        prop = entry.get("Prop", "")
        if prop not in target_props:
            continue

        if prop_type == "Spread" and line is not None:
            stat = entry.get("Stat", "")
            try:
                stat_line = float(stat.split()[-1])
                if abs(abs(stat_line) - abs(line)) > 0.01:
                    continue
            except (ValueError, IndexError):
                continue

        book_count = len(entry.get("book_feed", {}))
        if book_count > best_book_count:
            best_book_count = book_count
            best_match = entry

    if not best_match:
        if prop_type == "Spread" and line is not None:
            return find_matching_odds(
                league=league, team_a=team_a, team_b=team_b,
                feed=feed, game_date=game_date, prop_type="Moneyline",
            )
        log.debug(
            "No E7 match: league=%s team_a=%s team_b=%s date=%s prop=%s",
            league, team_a, team_b, game_date, prop_type,
        )
        return None

    log.info(
        "E7 matched: %s → %s (%s %s)",
        team_a or team_b, best_match.get("Match", ""),
        best_match.get("Prop", ""), best_match.get("Stat", ""),
    )
    return _format_odds(best_match)


def _format_odds(entry: dict) -> dict:
    highest = entry.get("highest", {})
    book_feed = entry.get("book_feed", {})

    best_books = {}
    for side_key, info in highest.items():
        best_books[side_key] = {
            "book": info.get("book", ""),
            "am_odds": info.get("am_odds", 0),
            "betlink": info.get("betlink", ""),
            "ev": info.get("ev", 0),
            "logo": SPORTSBOOK_LOGOS.get(info.get("book", ""), ""),
        }

    all_books = {}
    for book_name, book_sides in book_feed.items():
        book_entry = {"logo": SPORTSBOOK_LOGOS.get(book_name, "")}
        for side_key, info in book_sides.items():
            book_entry[side_key] = {
                "am_odds": info.get("am_odds", 0),
                "betlink": info.get("betlink", ""),
                "ev": info.get("ev", 0),
            }
        all_books[book_name] = book_entry

    return {
        "match": entry.get("Match", ""),
        "match_short": entry.get("Match Short", ""),
        "prop": entry.get("Prop", ""),
        "stat": entry.get("Stat", ""),
        "date": entry.get("Date", ""),
        "nvig": entry.get("NVIG", 0),
        "highest_ev": entry.get("highest_ev", 0),
        "best_books": best_books,
        "all_books": all_books,
    }
