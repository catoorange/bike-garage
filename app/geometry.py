"""Pure geometry: frame numbers + installed parts -> fit/weight metrics.
Origin at bottom bracket (BB). +x = toward front wheel, +y = up. Units mm unless noted."""
import math


def _by_type(installed, ptype):
    return [bp for bp in installed if bp.part.ptype == ptype]


def spacer_height(installed) -> float:
    """Total vertical rise from installed spacer sets under the stem."""
    return sum(bp.part.length * bp.quantity for bp in _by_type(installed, "spacer_set")
               if bp.part.length is not None)


def bar_center(bike, installed) -> tuple[float, float]:
    """Handlebar center: steerer top (stack+spacers) + stem vector."""
    hx = bike.reach or 0.0
    hy = (bike.stack or 0.0) + spacer_height(installed)
    stem = next((bp.part for bp in _by_type(installed, "stem") if bp.part.length is not None), None)
    if not stem or stem.angle is None:
        return (hx, hy)
    rad = math.radians(stem.angle)
    dx = stem.length * math.cos(rad)      # forward away from rider
    dy = stem.length * math.sin(rad)       # + rise / - drop
    return (hx + dx, hy + dy)


def crank_length(bike, installed) -> float | None:
    c = next((bp.part.length for bp in _by_type(installed, "crankset") if bp.part.length is not None), None)
    return c


def fit_metrics(bike, installed) -> dict:
    bx, by = bar_center(bike, installed)
    saddle = bike.saddle_height or 0.0          # real rider setting now
    crank = crank_length(bike, installed)
    return {
        "bar_y": round(by, 1),
        "cockpit_reach": round(abs(bx), 1),
        "cockpit_drop": (round(saddle - by, 1) if saddle else None),   # positive when saddle above bars
        "saddle_height": round(saddle, 1) if saddle else None,
        "crank_length": round(crank, 1) if crank else None,
        "pedal_below_bb": round(crank, 1) if crank else None,
        "total_weight": round(bike.total_weight, 0) if bike.total_weight else None,   # stored on the bike, not summed
    }