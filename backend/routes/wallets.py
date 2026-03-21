from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.db.database import get_db
from backend.db.models import WatchedWallet, WalletSnapshot, Position, Trade
from backend.services import polymarket as pm

router = APIRouter(prefix="/api/wallets", tags=["wallets"])


class AddWalletRequest(BaseModel):
    address: str
    label: str | None = None


@router.get("")
def list_wallets(db: Session = Depends(get_db)):
    wallets = db.query(WatchedWallet).order_by(WatchedWallet.added_at.desc()).all()
    result = []
    for w in wallets:
        snap = (
            db.query(WalletSnapshot)
            .filter_by(wallet_id=w.id)
            .order_by(WalletSnapshot.snapshot_at.desc())
            .first()
        )
        vol = float(w.volume or 0)
        pnl = float(w.pnl or 0)
        roi_pct = round(pnl / vol * 100, 1) if vol else 0.0
        result.append({
            "id": w.id,
            "address": w.address,
            "label": w.label,
            "profile_name": w.profile_name,
            "profile_image": w.profile_image,
            "x_username": w.x_username,
            "added_at": w.added_at.isoformat() if w.added_at else None,
            "last_synced": w.last_synced.isoformat() if w.last_synced else None,
            "portfolio_value": snap.total_value if snap else None,
            "roi_pct": roi_pct,
        })
    return result


@router.post("")
async def add_wallet(body: AddWalletRequest, db: Session = Depends(get_db)):
    address = body.address.strip().lower()
    if not address.startswith("0x") or len(address) != 42:
        raise HTTPException(400, "Invalid wallet address")

    existing = db.query(WatchedWallet).filter_by(address=address).first()
    if existing:
        raise HTTPException(409, "Wallet already watched")

    profile = {}
    try:
        profile = await pm.get_profile(address)
    except Exception:
        pass

    wallet = WatchedWallet(
        address=address,
        label=body.label,
        profile_name=profile.get("name") or profile.get("pseudonym"),
        profile_image=profile.get("profileImage"),
        x_username=profile.get("xUsername"),
    )
    db.add(wallet)
    db.commit()
    db.refresh(wallet)

    try:
        value = await pm.get_portfolio_value(address)
        snap = WalletSnapshot(wallet_id=wallet.id, total_value=value)
        db.add(snap)
    except Exception:
        pass

    try:
        positions = await pm.get_positions(address, limit=500)
        total_bought = sum(float(p.get("totalBought", 0)) for p in positions)
        realized = sum(float(p.get("realizedPnl", 0)) for p in positions)
        wallet.volume = total_bought
        wallet.pnl = realized
    except Exception:
        pass

    db.commit()

    vol = wallet.volume or 0
    pnl = wallet.pnl or 0
    return {
        "id": wallet.id,
        "address": wallet.address,
        "label": wallet.label,
        "profile_name": wallet.profile_name,
        "profile_image": wallet.profile_image,
        "x_username": wallet.x_username,
        "roi_pct": round(pnl / vol * 100, 1) if vol else 0.0,
    }


@router.delete("/{wallet_id}")
def delete_wallet(wallet_id: int, db: Session = Depends(get_db)):
    wallet = db.query(WatchedWallet).get(wallet_id)
    if not wallet:
        raise HTTPException(404, "Wallet not found")
    db.query(Trade).filter_by(wallet_id=wallet_id).delete()
    db.query(Position).filter_by(wallet_id=wallet_id).delete()
    db.query(WalletSnapshot).filter_by(wallet_id=wallet_id).delete()
    db.delete(wallet)
    db.commit()
    return {"ok": True}


@router.get("/{wallet_id}/positions")
async def get_positions(
    wallet_id: int,
    limit: int = Query(100, le=500),
    offset: int = Query(0),
    db: Session = Depends(get_db),
):
    wallet = db.query(WatchedWallet).get(wallet_id)
    if not wallet:
        raise HTTPException(404, "Wallet not found")

    positions = await pm.get_positions(wallet.address, limit=limit, offset=offset)

    db.query(Position).filter_by(wallet_id=wallet_id).delete()
    now = datetime.now(timezone.utc)
    for p in positions:
        db.add(Position(
            wallet_id=wallet_id,
            condition_id=p.get("conditionId", ""),
            title=p.get("title"),
            outcome=p.get("outcome"),
            size=float(p.get("size", 0)),
            avg_price=float(p.get("avgPrice", 0)),
            current_value=float(p.get("currentValue", 0)),
            cash_pnl=float(p.get("cashPnl", 0)),
            percent_pnl=float(p.get("percentPnl", 0)),
            synced_at=now,
        ))
    wallet.last_synced = now
    db.commit()

    return positions


@router.get("/{wallet_id}/trades")
async def get_trades(
    wallet_id: int,
    limit: int = Query(100, le=500),
    offset: int = Query(0),
    db: Session = Depends(get_db),
):
    wallet = db.query(WatchedWallet).get(wallet_id)
    if not wallet:
        raise HTTPException(404, "Wallet not found")

    trades = await pm.get_trades(wallet.address, limit=limit, offset=offset)

    db.query(Trade).filter_by(wallet_id=wallet_id).delete()
    for t in trades:
        db.add(Trade(
            wallet_id=wallet_id,
            condition_id=t.get("conditionId", ""),
            title=t.get("title"),
            outcome=t.get("outcome"),
            side=t.get("side", ""),
            size=float(t.get("size", 0)),
            price=float(t.get("price", 0)),
            timestamp=int(t.get("timestamp", 0)),
            tx_hash=t.get("transactionHash"),
        ))
    db.commit()

    return trades


@router.get("/{wallet_id}/pnl")
async def get_pnl(wallet_id: int, db: Session = Depends(get_db)):
    wallet = db.query(WatchedWallet).get(wallet_id)
    if not wallet:
        raise HTTPException(404, "Wallet not found")

    value = await pm.get_portfolio_value(wallet.address)
    snap = WalletSnapshot(wallet_id=wallet_id, total_value=value)
    db.add(snap)
    db.commit()

    snapshots = (
        db.query(WalletSnapshot)
        .filter_by(wallet_id=wallet_id)
        .order_by(WalletSnapshot.snapshot_at.asc())
        .all()
    )

    return {
        "current_value": value,
        "history": [
            {"value": s.total_value, "timestamp": s.snapshot_at.isoformat()}
            for s in snapshots
        ],
    }


@router.post("/{wallet_id}/sync")
async def sync_wallet(wallet_id: int, db: Session = Depends(get_db)):
    wallet = db.query(WatchedWallet).get(wallet_id)
    if not wallet:
        raise HTTPException(404, "Wallet not found")

    profile = {}
    try:
        profile = await pm.get_profile(wallet.address)
        wallet.profile_name = profile.get("name") or profile.get("pseudonym")
        wallet.profile_image = profile.get("profileImage")
        wallet.x_username = profile.get("xUsername")
    except Exception:
        pass

    positions = await pm.get_positions(wallet.address, limit=500)
    db.query(Position).filter_by(wallet_id=wallet_id).delete()
    now = datetime.now(timezone.utc)
    for p in positions:
        db.add(Position(
            wallet_id=wallet_id,
            condition_id=p.get("conditionId", ""),
            title=p.get("title"),
            outcome=p.get("outcome"),
            size=float(p.get("size", 0)),
            avg_price=float(p.get("avgPrice", 0)),
            current_value=float(p.get("currentValue", 0)),
            cash_pnl=float(p.get("cashPnl", 0)),
            percent_pnl=float(p.get("percentPnl", 0)),
            synced_at=now,
        ))

    trades = await pm.get_trades(wallet.address, limit=500)
    db.query(Trade).filter_by(wallet_id=wallet_id).delete()
    for t in trades:
        db.add(Trade(
            wallet_id=wallet_id,
            condition_id=t.get("conditionId", ""),
            title=t.get("title"),
            outcome=t.get("outcome"),
            side=t.get("side", ""),
            size=float(t.get("size", 0)),
            price=float(t.get("price", 0)),
            timestamp=int(t.get("timestamp", 0)),
            tx_hash=t.get("transactionHash"),
        ))

    value = await pm.get_portfolio_value(wallet.address)
    db.add(WalletSnapshot(wallet_id=wallet_id, total_value=value))

    total_bought = sum(float(p.get("totalBought", 0)) for p in positions)
    realized = sum(float(p.get("realizedPnl", 0)) for p in positions)
    wallet.volume = total_bought
    wallet.pnl = realized

    wallet.last_synced = now
    db.commit()

    vol = wallet.volume or 0
    pnl = wallet.pnl or 0
    return {
        "ok": True,
        "positions": len(positions),
        "trades": len(trades),
        "value": value,
        "roi_pct": round(pnl / vol * 100, 1) if vol else 0.0,
    }
