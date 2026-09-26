"""Pure: draw N configs on ONE shared coordinate system; show bar-dot deltas between them."""
import math
from app.render import frame_points
from app.geometry import bar_center

PALETTE = ["#c8102e", "#2563eb", "#d97706"]
GREY = "#888"


def _bg_style(bg):
    return {
        "light": ("#fafafa", 1.0, None),
        "dark":  ("#16181d", 0.95, None),
        "grid":  ("#ffffff", 1.0, "#e3e6ea"),
    }.get(bg, ("#fafafa", 1.0, None))


def _bbox(configs):
    xs, ys = [0.0], [0.0]
    for c in configs:
        pts = frame_points(c["bike"], c["parts"]); bx, by = bar_center(c["bike"], c["parts"])
        for p in pts.values():
            if p: xs.append(p[0]); ys.append(p[1])
        xs.append(bx); ys.append(by)
    return min(xs) - 40, max(xs) + 40, min(ys) - 40, max(ys) + 40


def render_overlay(configs, *, w=680, h=440, bg="light") -> str:
    x0, x1, y0, y1 = _bbox(configs)
    s = min(w / (x1 - x0 or 1), h / (y1 - y0 or 1))
    fill, opac, grid = _bg_style(bg)
    axis_txt = "#bbb" if bg == "dark" else "#888"

    def P(p): return (f"{(p[0]-x0)*s:.1f},{(y1-p[1])*s:.1f}")
    def seg(a, b, col, sw, dash=""):
        ax, ay = P(a).split(","); bx_, by_ = P(b).split(",")
        d = f' stroke-dasharray="{dash}"' if dash else ""
        return (f'<line x1="{ax}" y1="{ay}" x2="{bx_}" y2="{by_}" '
                f'stroke="{col}" stroke-width="{sw}" opacity="0.85"{d}/>')

    gridlines = ""
    if grid:
        gl = []
        gx = math.ceil(x0/50)*50
        while gx <= x1: gl.append(f'<line x1="{P((gx,y0)).split(",")[0]}" y1="0" x2="{P((gx,y1)).split(",")[0]}" y2="{h}" stroke="{grid}"/>'); gx += 50
        gy = math.ceil(y0/50)*50
        while gy <= y1: gl.append(f'<line x1="0" y1="{P((x0,gy)).split(",")[1]}" x2="{w}" y2="{P((x1,gy)).split(",")[1]}" stroke="{grid}"/>'); gy += 50
        gridlines = "".join(gl)

    ref_bx, ref_by = bar_center(configs[0]["bike"], configs[0]["parts"]) if configs else (0.0, 0.0)

    # arrowhead marker for the delta connector
    defs = ('<defs><marker id="arw" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">'
            '<path d="M0,0 L6,3 L0,6 Z" fill="#d97706"/></marker></defs>')

    out, labels, conns = [], [], []
    for i, c in enumerate(configs):
        col = c.get("color") or PALETTE[i % len(PALETTE)]
        pts = frame_points(c["bike"], c["parts"]); bx, by = bar_center(c["bike"], c["parts"])
        st, sa = pts["seat_top"], pts["saddle"]

        out.append(seg(pts["ht_bot"], pts["ht_top"], col, 2.5))      # head tube
        out.append(seg((0, 0), st, col, 2.5))                         # seat tube
        out.append(seg(pts["ht_top"], (bx, by), GREY, 1.6))           # stem
        if sa:
            out.append(seg(st, sa, GREY, 1.6))                        # seatpost

        bxpx, bypx = P((bx, by)).split(",")
        out.append(f'<circle cx="{bxpx}" cy="{bypx}" r="4.5" fill="#2563eb"><title>bar</title></circle>')
        if sa:
            sx, sy = P(sa).split(",")
            out.append(f'<circle cx="{sx}" cy="{sy}" r="5" fill="#16a34a"><title>saddle</title></circle>')

        # --- visual delta connector: dashed arrow from ref bar -> this config's bar (skip the ref itself) ---
        if i > 0 and len(configs) > 1:
            mx, my = ((ref_bx + bx) / 2), ((ref_by + by) / 2)   # midpoint for the distance label
            dist = math.hypot(bx - ref_bx, by - ref_by)          # straight-line distance in mm
            mpx, mpy = P((mx, my)).split(",")
            conns.append(seg((ref_bx, ref_by), (bx, by), "#d97706", 1.4, dash="4 3")
                         .replace('opacity="0.85"', 'marker-end="url(#arw)" opacity="0.9"'))
            out.append(f'<text x="{float(mpx)+6:.0f}" y="{float(mpy)-6:.0f}" font-size="10" fill="#d97706">'
                       f'{dist:.0f}mm</text>')

        # text labels (name + bar coords + dx/dy) on the right, as before
        dx = bx - ref_bx; dy = by - ref_by
        ly = 16 + i * 30
        line1 = f'<text x="{w-8}" y="{ly}" text-anchor="end" font-size="11" font-weight="700" fill="{col}">{c.get("label", f"config {i+1}")}</text>'
        coords = f'<text x="{w-8}" y="{ly+12}" text-anchor="end" font-size="10" fill="{axis_txt}">bar ({bx:.0f}, {by:.0f})</text>'
        delta = ""
        if i > 0 and len(configs) > 1:
            sx_ = "+" if dx >= 0 else "\u2212"; sy_ = "+" if dy >= 0 else "\u2212"
            delta = (f'<text x="{w-8}" y="{ly+24}" text-anchor="end" font-size="10" fill="#d97706">'
                     f'Δ {sx_}{abs(dx):.0f}mm reach · {sy_}{abs(dy):.0f}mm vert</text>')
        labels.append(line1 + coords + delta)

    axis = (f'<text x="8" y="{h-6}" font-size="10" fill="{axis_txt}">'
            f'bb=origin · +x fwd +y up · shared scale (mm→px schematic)</text>')
    return (f'<svg viewBox="0 0 {w} {h}" style="border:1px solid #e3e6ea;border-radius:8px">'
            f'{defs}<rect width="{w}" height="{h}" fill="{fill}"/>{gridlines}'
            f'{"".join(conns)}{"".join(out)}{"".join(labels)}{axis}</svg>')