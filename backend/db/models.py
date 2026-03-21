from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, Text, ForeignKey, UniqueConstraint

from backend.db.database import Base


def _utcnow():
    return datetime.now(timezone.utc)


class WatchedWallet(Base):
    __tablename__ = "watched_wallets"

    id = Column(Integer, primary_key=True)
    address = Column(String(42), unique=True, nullable=False, index=True)
    label = Column(String, nullable=True)
    profile_name = Column(String, nullable=True)
    profile_image = Column(String, nullable=True)
    x_username = Column(String, nullable=True)
    pnl = Column(Float, default=0.0)
    volume = Column(Float, default=0.0)
    added_at = Column(DateTime, default=_utcnow)
    last_synced = Column(DateTime, nullable=True)


class WalletSnapshot(Base):
    __tablename__ = "wallet_snapshots"

    id = Column(Integer, primary_key=True)
    wallet_id = Column(Integer, ForeignKey("watched_wallets.id", ondelete="CASCADE"), nullable=False, index=True)
    total_value = Column(Float, default=0.0)
    snapshot_at = Column(DateTime, default=_utcnow)


class Position(Base):
    __tablename__ = "positions"

    id = Column(Integer, primary_key=True)
    wallet_id = Column(Integer, ForeignKey("watched_wallets.id", ondelete="CASCADE"), nullable=False, index=True)
    condition_id = Column(String, nullable=False)
    title = Column(String, nullable=True)
    outcome = Column(String, nullable=True)
    size = Column(Float, default=0.0)
    avg_price = Column(Float, default=0.0)
    current_value = Column(Float, default=0.0)
    cash_pnl = Column(Float, default=0.0)
    percent_pnl = Column(Float, default=0.0)
    synced_at = Column(DateTime, default=_utcnow)


class Trade(Base):
    __tablename__ = "trades"

    id = Column(Integer, primary_key=True)
    wallet_id = Column(Integer, ForeignKey("watched_wallets.id", ondelete="CASCADE"), nullable=False, index=True)
    condition_id = Column(String, nullable=False)
    title = Column(String, nullable=True)
    outcome = Column(String, nullable=True)
    side = Column(String, nullable=False)
    size = Column(Float, default=0.0)
    price = Column(Float, default=0.0)
    timestamp = Column(Integer, nullable=False)
    tx_hash = Column(String, nullable=True)


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True)
    wallet_id = Column(Integer, ForeignKey("watched_wallets.id", ondelete="CASCADE"), nullable=False, index=True)
    condition_id = Column(String, nullable=False)
    title = Column(String, nullable=True)
    outcome = Column(String, nullable=True)
    size = Column(Float, default=0.0)
    price = Column(Float, default=0.0)
    detected_at = Column(DateTime, default=_utcnow, index=True)
    sport = Column(String, nullable=True)
    eternity7_match = Column(Text, nullable=True)
    dismissed = Column(Boolean, default=False)


class KnownPosition(Base):
    __tablename__ = "known_positions"
    __table_args__ = (
        UniqueConstraint("wallet_id", "condition_id", "outcome", name="uq_known_pos"),
    )

    id = Column(Integer, primary_key=True)
    wallet_id = Column(Integer, ForeignKey("watched_wallets.id", ondelete="CASCADE"), nullable=False, index=True)
    condition_id = Column(String, nullable=False)
    outcome = Column(String, nullable=True)
    size = Column(Float, default=0.0)
    last_checked = Column(DateTime, default=_utcnow)
