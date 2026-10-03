"""Read a CSV of factory geometry and upsert rows into BikeModel.
Idempotent: skips rows whose (brand+model+year+frame_size) already exists."""
import csv
from pathlib import Path
from app.db import SessionLocal
from app.models import BikeModel


import re

def _f(v):
    """Parse '110mm', '110 mm', '73', '1.5"' etc -> float."""
    if not v:
        return None
    s = str(v).strip().lower().rstrip('"').replace("mm", "").replace("cm", "").strip()
    m = re.search(r"-?\d+(\.\d+)?", s)
    return float(m.group()) if m else None

def _i(v):  # optional int from CSV cell
    v = (v or "").strip()
    return int(float(v)) if v else None


def seed_bike_models(csv_path: str | Path | None = None) -> int:
    """Seed BikeModel from CSV. Reload-safe: if any rows already exist, do nothing."""
    path = Path(csv_path) if csv_path else Path(__file__).resolve().parent.parent / "seed" / "bike_models.csv"
    if not path.exists():
        return 0

    db = SessionLocal()
    try:
        if db.query(BikeModel).count() > 0:      # already seeded → skip entirely (safe under --reload)
            return 0
        added = 0
        with open(path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                year_val = _i(row.get("year"))
                db.add(BikeModel(
                    brand=row["brand"].strip(),
                    model=row["model"].strip(),
                    year=year_val,
                    frame_size=(row.get("frame_size") or "").strip() or None,
                    head_tube_length=_f(row.get("head_tube_length")),
                    stack=_f(row.get("stack")),
                    reach=_f(row.get("reach")),
                    head_tube_angle=_f(row.get("head_tube_angle")),
                    seat_tube_angle=_f(row.get("seat_tube_angle")),
                    chainstay_length=_f(row.get("chainstay_length")),
                    wheelbase=_f(row.get("wheelbase")),
                    bb_drop=_f(row.get("bb_drop")),
                    wheel_size=_f(row.get("wheel_size")),
                    seat_tube_length=_f(row.get("seat_tube_length")),
                    default_crank_length=_f(row.get("default_crank_length")),
                    fork_length=_f(row.get("fork_length")),        # NEW
                    fork_offset=_f(row.get("fork_offset")),        # NEW
                    speeds=_i(row.get("speeds")),
                    chainring_1=_i(row.get("chainring_1")),
                    chainring_2=_i(row.get("chainring_2")),
                    cassette_low=_i(row.get("cassette_low")),
                    cassette_high=_i(row.get("cassette_high")),
                    source=row.get("source", "").strip() or "csv:seed/bike_models.csv",
                ))
                added += 1
        db.commit()
        return added
    finally:
        db.close()