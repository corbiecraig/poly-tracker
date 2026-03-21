import json

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.db.database import get_db
from backend.db.models import Alert, WatchedWallet

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


@router.get("")
def list_alerts(
    wallet_id: int | None = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    db: Session = Depends(get_db),
):
    q = db.query(Alert, WatchedWallet).join(
        WatchedWallet, Alert.wallet_id == WatchedWallet.id
    )
    if wallet_id:
        q = q.filter(Alert.wallet_id == wallet_id)
    q = q.filter(Alert.dismissed == False).order_by(Alert.detected_at.desc())  # noqa: E712
    rows = q.offset(offset).limit(limit).all()

    results = []
    for a, w in rows:
        vol = float(w.volume or 0)
        pnl = float(w.pnl or 0)
        roi_pct = round(pnl / vol * 100, 1) if vol else 0.0
        results.append({
            "id": a.id,
            "wallet_id": a.wallet_id,
            "wallet_label": w.label or w.profile_name or w.address[:10],
            "wallet_image": w.profile_image,
            "wallet_address": w.address,
            "wallet_roi_pct": roi_pct,
            "wallet_pnl": pnl,
            "condition_id": a.condition_id,
            "title": a.title,
            "outcome": a.outcome,
            "size": a.size,
            "price": a.price,
            "detected_at": a.detected_at.isoformat() if a.detected_at else None,
            "sport": a.sport,
            "eternity7_match": json.loads(a.eternity7_match) if a.eternity7_match else None,
            "dismissed": a.dismissed,
        })
    return results


@router.post("/{alert_id}/dismiss")
def dismiss_alert(alert_id: int, db: Session = Depends(get_db)):
    alert = db.query(Alert).get(alert_id)
    if not alert:
        raise HTTPException(404, "Alert not found")
    alert.dismissed = True
    db.commit()
    return {"ok": True}


@router.get("/count")
def alert_count(db: Session = Depends(get_db)):
    count = db.query(Alert).filter(Alert.dismissed == False).count()  # noqa: E712
    return {"count": count}


@router.post("/poll")
async def trigger_poll():
    from backend.services.poller import _poll_once

    await _poll_once()
    return {"ok": True}
