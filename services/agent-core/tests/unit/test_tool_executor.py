from __future__ import annotations

from decimal import Decimal
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.tools.executor import _coerce_int  # noqa: E402


def test_coerce_int_accepts_postgres_numeric_values() -> None:
    assert _coerce_int(Decimal("2900000.00")) == 2900000
    assert _coerce_int("425000.00") == 425000
    assert _coerce_int("1,395,000.00") == 1395000
