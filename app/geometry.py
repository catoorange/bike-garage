"""Pure geometry: frame numbers + installed parts -> fit/weight metrics. BB at origin, +x fwd, +y up."""
import math


def _by_type(installed, ptype):
    return [bp for bp in installed if getattr(bp, "part", None) and bp.part.ptype == ptype]


def spacer_height(installed) -> float:
    """Total rise added by installed spacer sets under the stem."""
    return sum(bp.part.length * bp.quantity for bp in _by_type(installed, "spacer_set")
               if bp.part.length is not None)


def steerer_top(bike, installed) -> tuple[float, float]:
    """Top of the steerer = top of head tube raised ALONG the steering axis by spacer stack.
    This is what spacers change: more spacers -> bar clamp sits higher up the steerer."""
    hta = math.radians(bike.head_tube_angle or 72.0)
    hx, hy = (bike.reach or 0.0), (bike.stack or 0.0)
    sh = spacer_height(installed)
    # move up-and-back along the head-tube axis by the spacer stack height (vertical component)
    return (hx - sh * math.cos(hta), hy + sh * math.sin(hta))


def bar_center(bike, installed) -> tuple[float, float]:
    """Handlebar center: steerer-top (stack+spacers) + stem vector (forward)."""
    sx, sy = steerer_top(bike, installed)
    stem = next((bp.part for bp in _by_type(installed, "stem") if bp.part.length is not None), None)
    if not stem or stem.angle is None:
        return (sx, sy)                       # no stem modeled -> bars at steerer top
    rad = math.radians(stem.angle)
    dx = stem.length * math.cos(rad)           # forward (+x) toward the front wheel
    dy = stem.length * math.sin(rad)           # + rise / - drop
    return (sx + dx, sy + dy)


def crank_length(bike, installed) -> float | None:
    c = next((bp.part.length for bp in _by_type(installed, "crankset") if bp.part.length is not None), None)
    return c


def fit_metrics(bike, installed) -> dict:
    bx, by = bar_center(bike, installed)
    saddle = bike.saddle_height or 0.0
    crank = crank_length(bike, installed)
    return {
        "bar_y": round(by, 1),
        "cockpit_reach": round(abs(bx), 1),
        "cockpit_drop": (round(saddle - by, 1) if saddle else None),
        "saddle_height": round(saddle, 1) if saddle else None,
        "spacer_height": round(spacer_height(installed), 1) or None,   # NEW: visible number for spacers
        "crank_length": round(crank, 1) if crank else None,
        "pedal_below_bb": round(crank, 1) if crank else None,
        "total_weight": round(bike.total_weight, 0) if bike.total_weight else None,
    }