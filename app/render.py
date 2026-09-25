"""Pure: turn a bike's numbers into named 2D points + a labeled SVG side-view."""
import math


def frame_points(bike) -> dict:
    """All angles measured from horizontal (58–74°). Both tubes lean BACK going up.
    Origin at BB; +x forward, +y up."""
    hta = math.radians(bike.head_tube_angle or 72.0)
    hl = getattr(bike, "head_tube_length", None) or 120.0
    sta = math.radians(bike.seat_tube_angle or 73.0)
    stl = bike.seat_tube_length or 520.0

    # head tube: TOP leans back over BB. Match the seat-tube convention (cos=lean, sin=steepness):
    ht_top = (bike.reach or 0.0, bike.stack or 0.0)
    ht_bot = (ht_top[0] + hl * math.cos(hta), ht_top[1] - hl * math.sin(hta))   # <- was sin/cos swapped

    # seat tube: rises from BB leaning BACK (top behind BB); saddle on its extension
    seat_top = (-stl * math.cos(sta), stl * math.sin(sta))
    sh = bike.saddle_height or 0.0
    post_len = max(sh - stl, 0.0)
    post_top = (seat_top[0] - post_len * math.cos(sta), seat_top[1] + post_len * math.sin(sta)) if sh else None

    return {"bb": (0.0, 0.0), "ht_bot": ht_bot, "ht_top": ht_top,
            "seat_top": seat_top, "saddle": post_top}


def to_svg(bike, installed, *, w=560, h=380, color="#c8102e") -> str:
    from app.geometry import bar_center
    pts = frame_points(bike)
    bx, by = bar_center(bike, installed)   # moves only if a stem WITH length+angle is installed

    xs = [p[0] for p in pts.values() if p] + [bx]; ys = [p[1] for p in pts.values() if p] + [by]
    x0, x1, y0, y1 = min(xs)-40, max(xs)+40, min(ys)-40, max(ys)+40
    s = min(w/(x1-x0 or 1), h/(y1-y0 or 1))
    def P(p): return (f"{(p[0]-x0)*s:.1f},{(y1-p[1])*s:.1f}")

    def seg(a, b, c, sw):  # colored line between two points
        return f'<line x1="{P(a).split(",")[0]}" y1="{P(a).split(",")[1]}" x2="{P(b).split(",")[0]}" y2="{P(b).split(",")[1]}" stroke="{c}" stroke-width="{sw}" opacity="{0.5 if c=='#888' else 1}"/>'

    seat_top, saddle = pts["seat_top"], pts["saddle"]
    lines = [seg(pts["ht_bot"], pts["ht_top"], color, 3)]          # head tube (red)
    lines.append(seg((0,0), seat_top, color, 3))                    # seat tube (red)
    lines.append(seg(pts["ht_top"], (bx, by), "#888", 2))           # NEW: stem (gray) — steerer top → bar
    if saddle:
        lines.append(seg(seat_top, saddle, "#888", 2))              # exposed seatpost (gray)

    marks = f'<circle cx="{P((bx,by)).split(",")[0]}" cy="{P((bx,by)).split(",")[1]}" r="4.5" fill="#2563eb"><title>bar center</title></circle>'
    if saddle:
        marks += f'<circle cx="{P(saddle).split(",")[0]}" cy="{P(saddle).split(",")[1]}" r="5" fill="#16a34a"><title>saddle</title></circle>'

    legend = (f'<g font-size="10"><text x="8" y="14" fill="{color}">■ frame (seat+head tube)</text>'
              f'<text x="8" y="27" fill="#888">— seatpost / stem (gray) </text>'
              f'<text x="150" y="27" fill="#16a34a">● saddle</text>'
              f'<text x="230" y="27" fill="#2563eb">● handlebar (moves with stem)</text></g>')

    return (f'<svg viewBox="0 0 {w} {h}" style="background:#fafafa;border:1px solid #e3e6ea;border-radius:8px">'
            f'{"".join(lines)}{marks}{legend}</svg>')