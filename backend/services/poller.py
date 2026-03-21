"""Background poller: detect new positions from watched wallets, cross-reference Eternity7."""

import asyncio
import json
import logging
from datetime import datetime, timezone

from backend.config import POLL_INTERVAL_SECONDS
from backend.db.database import SessionLocal
from backend.db.models import WatchedWallet, KnownPosition, Alert
from backend.services import polymarket as pm
from backend.services import eternity7 as e7
from backend.services.parser import parse_market
from backend.services import discord_notify

log = logging.getLogger("poller")

_task: asyncio.Task | None = None

MIN_POSITION_SIZE = 5000


async def _poll_once():
    db = SessionLocal()
    try:
        wallets = db.query(WatchedWallet).all()
        if not wallets:
            return

        feed = await e7.fetch_feed()

        for wallet in wallets:
            try:
                await _poll_wallet(db, wallet, feed)
            except Exception as exc:
                log.warning("Poll failed for %s: %s", wallet.address[:10], exc)
    finally:
        db.close()


async def _poll_wallet(db, wallet: WatchedWallet, feed: dict):
    positions = await pm.get_positions(wallet.address, limit=500, offset=0)

    known = {
        (kp.condition_id, kp.outcome): kp
        for kp in db.query(KnownPosition).filter_by(wallet_id=wallet.id).all()
    }

    now = datetime.now(timezone.utc)
    today_str = now.strftime("%Y-%m-%d")
    new_alerts = []

    for pos in positions:
        cid = pos.get("conditionId", "")
        outcome = pos.get("outcome", "")
        size = float(pos.get("size", 0))
        key = (cid, outcome)

        existing = known.get(key)

        is_new = existing is None
        is_increased = existing and size >= existing.size * 2 and size - existing.size > MIN_POSITION_SIZE

        if is_new:
            kp = KnownPosition(
                wallet_id=wallet.id,
                condition_id=cid,
                outcome=outcome,
                size=size,
                last_checked=now,
            )
            db.add(kp)
        else:
            existing.size = size
            existing.last_checked = now

        if not (is_new or is_increased) or size < MIN_POSITION_SIZE:
            continue

        title = pos.get("title", "")
        slug = pos.get("slug", "")
        event_slug = pos.get("eventSlug", "")

        parsed = parse_market(title, slug=slug, event_slug=event_slug)
        if not parsed:
            continue

        game_date = parsed.get("game_date")
        if game_date and game_date < today_str:
            continue

        e7_data = e7.find_matching_odds(
            league=parsed["league"],
            team_a=parsed.get("team_a"),
            team_b=parsed.get("team_b"),
            feed=feed,
            game_date=game_date,
            prop_type=parsed.get("prop_type"),
            line=parsed.get("line"),
        )

        if not e7_data:
            continue

        alert = Alert(
            wallet_id=wallet.id,
            condition_id=cid,
            title=title,
            outcome=outcome,
            size=size,
            price=float(pos.get("avgPrice", 0)),
            detected_at=now,
            sport=parsed["league"],
            eternity7_match=json.dumps(e7_data),
        )
        db.add(alert)
        new_alerts.append((alert, e7_data))

    db.commit()

    if new_alerts:
        log.info(
            "Wallet %s (%s): %d new alert(s)",
            wallet.label or wallet.address[:10],
            wallet.address[:10],
            len(new_alerts),
        )
        for alert, e7_data in new_alerts:
            await discord_notify.send_alert(alert, wallet, e7_data)


async def _run_loop():
    log.info("Poller started (interval=%ds)", POLL_INTERVAL_SECONDS)
    while True:
        try:
            await _poll_once()
        except Exception as exc:
            log.error("Poll cycle failed: %s", exc)
        await asyncio.sleep(POLL_INTERVAL_SECONDS)


def start():
    global _task
    if _task is None or _task.done():
        _task = asyncio.create_task(_run_loop())
        log.info("Poller task created")


def stop():
    global _task
    if _task and not _task.done():
        _task.cancel()
        log.info("Poller task cancelled")
        _task = None
