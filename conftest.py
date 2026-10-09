import os, sys, tempfile
from pathlib import Path
_tmp = tempfile.mkdtemp()
os.environ.update({
    "DATABASE_PATH": str(Path(_tmp) / "test.db"),
    "CUREX_PUBLIC_WRITE_ENABLED": "true",
    "CUREX_OPERATOR_NAME": "Test Operator",
    "CUREX_PRIVACY_CONTACT": "privacy@example.org",
    "CUREX_ADMIN_TOKEN": "a" * 40,
    "CUREX_RATE_SALT": "test-salt",
    "CUREX_RATE_REGISTER": "1000", "CUREX_RATE_WRITE": "1000", "CUREX_RATE_READ": "1000",
    "CUREX_TRUSTED_PROXY_HOPS": "1",
    "CUREX_WALLET_COOLDOWN_HOURS": "0",
    "CUREX_MIN_EPOCH_POINTS": "10",
})
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
