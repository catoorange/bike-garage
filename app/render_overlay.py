"""Pure: draw N configs on ONE shared coordinate system.
Each config = {"bike": Bike, "parts": [BikePart,...], "label": str, "color": optional}.
Passing the same bike twice with different parts = your 'same bike, different parts' ghosted wireframe.
Passing different bikes = multi-bike compare. Same code path for both."""
from app.render import frame_points
from app.geometry import bar_center

PALETTE = ["#c8102e", "#2563eb", "#d97706"]   # one color per config


def _bbox(configs):
    xs, ys = [0.0], [0.0]                       # BB always at origin
    for c in configs:
        pts = frame_points(c["bike"]); bx, by = bar_center(c["bike"], c["parts"])
        for p in pts.values():
            if p: xs.append(p[0]); ys.append(p[1])
        xs.append(bx); ys.append(by)
    return min(xs) - 40, max(xs) + 40, min(ys) - 40, max(ys) + 40


def render_overlay(configs, *, w=680, h=400) -> str:
    x0, x1, y0, y1 = _bbox(configs)             # ONE shared box for all configs (the whole point)
    s = min(w / (x1 - x0 or 1), h / (y1 - y0 or 1))

    def P(p): return (f"{(p[0]-x0)*s:.1f},{(y1-p[1])*s:.1f}")
    def seg(a, b, col, sw):
        ax, ay = P(a).split(","); bx_, by_ = P(b).split(",")
        return (f'<line x1="{ax}" y1="{ay}" x2="{bx_}" y2="{by_}" '
                f'stroke="{col}" stroke-width="{sw}" opacity="0.75"/>')

    out, labels = [], []
    for i, c in enumerate(configs):
        col = c.get("color") or PALETTE[i % len(PALETTE)]
        pts = frame_points(c["bike"]); bx, by = bar_center(c["bike"], c["parts"])
        st, sa = pts["seat_top"], pts["saddle"]

        # --- frame + component lines (overlap = "ghost" when same bike) ---
        out.append(seg(pts["ht_bot"], pts["ht_top"], col, 2.5))    # head tube
        out.append(seg((0, 0), st, col, 2.5))                      # seat tube
        out.append(seg(pts["ht_top"], (bx, by), col, 1.6))          # stem
        if sa:
            out.append(seg(st, sa, col, 1.6))                       # seatpost

        # --- saddle + bar dots (the part-driven markers that move) ---
        bxpx, bypx = P((bx, by)).split(",")
        out.append(f'<circle cx="{bxpx}" cy="{bypx}" r="4.5" fill="{col}">'
                   f'<title>{c.get("label","config")} bar</title></circle>')
        if sa:
            sx, sy = P(sa).split(",")
            out.append(f'<circle cx="{sx}" cy="{sy}" r="5" fill="{col}" opacity="0.9">'
                       f'<title>{c.get("label","config")} saddle</title></circle>')

        # --- per-config label pinned top-right, color-matched ---
        ly = 16 + i * 14
        labels.append(f'<text x="{w-8}" y="{ly}" text-anchor="end" font-size="11" '
                      f'font-weight="700" fill="{col}">{c.get("label", f"config {i+1}")}</text>')

    axis = (f'<text x="8" y="{h-6}" font-size="10" fill="#888">'
            f'bb=origin · +x fwd +y up · shared scale (mm→px schematic)</text>')
    return (f'<svg viewBox="0 0 {w} {h}" style="background:#fafafa;border:1px solid #e3e6ea;border-radius:8px">'
            f'{"".join(out)}{"".join(labels)}{axis}</svg>')