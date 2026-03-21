"""Parse Polymarket sports market data into structured info for Eternity7 matching."""

import re
from datetime import datetime

SLUG_PREFIX_TO_LEAGUE = {
    "nba": "NBA",
    "nfl": "NFL",
    "mlb": "MLB",
    "nhl": "NHL",
    "ncaab": "NCAAB",
    "cbb": "NCAAB",
    "cfb": "NCAAF",
    "ncaaf": "NCAAF",
    "epl": "Premier League (England)",
    "mls": "Major League Soccer (USA)",
    "lal": "La Liga (Spain)",
    "bun": "Bundesliga (Germany)",
    "sea": "Serie A (Italy)",
    "fl1": "Ligue 1 (France)",
    "ucl": "UEFA Champions League",
    "ere": "Eredivisie (Netherlands)",
    "ufc": "UFC",
    "wnba": "WNBA",
    "atp": "ATP",
    "wta": "WTA",
    "ahl": "AHL",
    "f1": "Formula 1",
}

_DATE_FROM_SLUG = re.compile(r"(\d{4}-\d{2}-\d{2})")

_EXACT_SCORE = re.compile(
    r"Exact Score:\s*(.+?)\s+\d+\s*-\s*\d+\s+(.+?)(?:\s*\?|$)",
    re.IGNORECASE,
)

_VS_PATTERN = re.compile(
    r"^(.+?)\s+vs\.?\s+(.+?)(?:\s*$|\s*\?|\s*:)",
    re.IGNORECASE,
)

_TEAM_VS_COLON = re.compile(
    r"^(.+?)\s+vs\.?\s+(.+?):\s+",
    re.IGNORECASE,
)

_WIN_PATTERN = re.compile(
    r"(?:Will\s+)?(?:the\s+)?(.+?)\s+win\b",
    re.IGNORECASE,
)

_SPREAD_PATTERN = re.compile(
    r"Spread:\s*(.+?)\s*\(([-+]?[\d.]+)\)",
    re.IGNORECASE,
)

_PLAYER_PROP = re.compile(
    r"^(.+?):\s+(?:Points|Assists|Rebounds|Strikeouts|Hits|Goals|Saves|Shots|Blocks|Steals|Carries|Receptions|Passing|Rushing|Tackles|Sacks|TDs?|HR|RBI|ERA|IP)\b",
    re.IGNORECASE,
)

_OU_PATTERN = re.compile(
    r"^(.+?)\s+vs\.?\s+(.+?):\s+O/U\s+[\d.]+",
    re.IGNORECASE,
)


def parse_market(question: str, slug: str = "", event_slug: str = "") -> dict | None:
    ref_slug = slug or event_slug or ""
    slug_parts = ref_slug.split("-")
    if not slug_parts:
        return None

    prefix = slug_parts[0].lower()
    league = SLUG_PREFIX_TO_LEAGUE.get(prefix)
    if not league:
        return None

    game_date = None
    date_match = _DATE_FROM_SLUG.search(ref_slug)
    if date_match:
        try:
            game_date = datetime.strptime(date_match.group(1), "%Y-%m-%d").strftime("%Y-%m-%d")
        except ValueError:
            pass

    team_a = None
    team_b = None
    prop_type = "Moneyline"
    player = None

    player_match = _PLAYER_PROP.match(question)
    if player_match:
        player = player_match.group(1).strip()
        prop_type = "Player Prop"
        return {
            "league": league,
            "team_a": None,
            "team_b": None,
            "player": player,
            "game_date": game_date,
            "prop_type": prop_type,
        }

    exact_match = _EXACT_SCORE.search(question)
    if exact_match:
        team_a = _clean_team(exact_match.group(1))
        team_b = _clean_team(exact_match.group(2))
        prop_type = "Exact Score"
    else:
        ou_match = _OU_PATTERN.match(question)
        if ou_match:
            team_a = _clean_team(ou_match.group(1))
            team_b = _clean_team(ou_match.group(2))
            prop_type = "Total"
        else:
            colon_match = _TEAM_VS_COLON.match(question)
            if colon_match:
                team_a = _clean_team(colon_match.group(1))
                team_b = _clean_team(colon_match.group(2))
            else:
                vs_match = _VS_PATTERN.match(question)
                if vs_match:
                    team_a = _clean_team(vs_match.group(1))
                    team_b = _clean_team(vs_match.group(2))

    line = None
    spread_match = _SPREAD_PATTERN.search(question)
    if spread_match:
        team_a = _clean_team(spread_match.group(1))
        prop_type = "Spread"
        try:
            line = float(spread_match.group(2))
        except ValueError:
            pass

    if not spread_match:
        win_match = _WIN_PATTERN.search(question)
        if win_match and not team_a:
            team_a = _clean_team(win_match.group(1))

    if not team_a:
        return None

    return {
        "league": league,
        "team_a": team_a,
        "team_b": team_b,
        "player": None,
        "game_date": game_date,
        "prop_type": prop_type,
        "line": line,
    }


def _clean_team(name: str) -> str:
    name = name.strip().rstrip("?").strip()
    for suffix in (" win", " beat", " defeat", " cover"):
        if name.lower().endswith(suffix):
            name = name[: -len(suffix)]
    return name.strip()
