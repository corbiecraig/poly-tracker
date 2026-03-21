import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

_env_file = BASE_DIR / ".env"
if _env_file.exists():
    for line in _env_file.read_text().splitlines():
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())

DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "polymarket.db"
DATABASE_URL = f"sqlite:///{DB_PATH}"

PORT = int(os.environ.get("PORT", 8003))

GAMMA_API_BASE = "https://gamma-api.polymarket.com"
DATA_API_BASE = "https://data-api.polymarket.com"
CLOB_API_BASE = "https://clob.polymarket.com"

ALLOWED_ORIGINS = os.environ.get(
    "ALLOWED_ORIGINS", "http://localhost:8003"
).split(",")

ETERNITY7_URL = "https://api.eternity7.dev/api/dev_internal_feed"
ETERNITY7_TOKEN = os.environ.get(
    "ETERNITY7_TOKEN", "022dac17-0016-4560-a004-9757f9529de6"
)

POLL_INTERVAL_SECONDS = int(os.environ.get("POLL_INTERVAL", 300))
SHARP_PNL_THRESHOLD = 50_000

DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")
