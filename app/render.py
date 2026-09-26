"""Pure: turn a bike's numbers into named 2D points + a labeled SVG side-view."""
import math


def frame_points(bike, installed=()) -> dict:
    hta = math.radians(bike.head_tube_angle or 72.0)
    hl = getattr(bike, "head_tube_length", None) or 120.0
    sta = math.radians(bike.seat_tube_angle or 73.0)
    stl = bike.seat_tube_length or 520.0

    ht_top = (bike.reach or 0.0, bike.stack or 0.0)
    ht_bot = (ht_top[0] + hl * math.cos(hta), ht_top[1] - hl * math.sin(hta))

    seat_top = (-stl * math.cos(sta), stl * math.sin(sta))
    sh = bike.saddle_height or 0.0
    post_len = max(sh - stl, 0.0)
    px, py = (seat_top[0] - post_len * math.cos(sta), seat_top[1] + post_len * math.sin(sta)) if sh else (None, None)
    setback = next((getattr(bp.part, "setback", None) for bp in installed
                    if getattr(bp, "part", None) and bp.part.ptype == "seatpost" and getattr(bp.part, "setback", None)), 0.0)
    saddle = (px - setback, py) if px is not None else None

    return {"bb": (0.0, 0.0), "ht_bot": ht_bot, "ht_top": ht_top,
            "seat_top": seat_top, "saddle": saddle}


def _bg_style(bg):
    """Return (fill_color, line_opacity, grid_stroke). grid_stroke None = no grid."""
    return {
        "light": ("#fafafa", 1.0, None),
        "dark":  ("#16181d", 0.95, None),
        "grid":  ("#ffffff", 1.0, "#e3e6ea"),   # light + visible gridlines
    }.get(bg, ("#fafafa", 1.0, None))


def to_svg(bike, installed, *, w=560, h=380, color="#c8102e", bg="light") -> str:
    from app.geometry import bar_center, steerer_top
    pts = frame_points(bike, installed)
    bx, by = bar_center(bike, installed)
    st_top = steerer_top(bike, installed)

    fill, opac, grid = _bg_style(bg)
    axis_txt = "#bbb" if bg == "dark" else "#888"

    all_pts = [p for p in pts.values() if p] + [st_top, (bx, by)]
    xs = [p[0] for p in all_pts]; ys = [p[1] for p in all_pts]
    x0, x1, y0, y1 = min(xs) - 40, max(xs) + 40, min(ys) - 40, max(ys) + 40
    s = min(w / (x1 - x0 or 1), h / (y1 - y0 or 1))
    def P(p): return (f"{(p[0]-x0)*s:.1f},{(y1-p[1])*s:.1f}")
    def seg(a, b, c, sw):
        ax, ay = P(a).split(","); bx_, by_ = P(b).split(",")
        return (f'<line x1="{ax}" y1="{ay}" x2="{bx_}" y2="{by_}" stroke="{c}" '
                f'stroke-width="{sw}" opacity="{opac}"/>')

    # optional gridlines every 50mm, only when bg has a grid color
    gridlines = ""
    if grid:
        gl = []
        gx = math.ceil(x0/50)*50
        while gx <= x1: gl.append(f'<line x1="{P((gx,y0)).split(",")[0]}" y1="0" x2="{P((gx,y1)).split(",")[0]}" y2="{h}" stroke="{grid}"/>'); gx += 50
        gy = math.ceil(y0/50)*50
        while gy <= y1: gl.append(f'<line x1="0" y1="{P((x0,gy)).split(",")[1]}" x2="{w}" y2="{P((x1,gy)).split(",")[1]}" stroke="{grid}"/>'); gy += 50
        gridlines = "".join(gl)

    st, sa = pts["seat_top"], pts["saddle"]
    lines = [seg(pts["ht_bot"], pts["ht_top"], color, 3)]   # head tube (frame color)
    lines.append(seg((0, 0), st, color, 3))                  # seat tube (frame color)
    lines.append(seg(pts["ht_top"], st_top, "#888", 2))      # spacers (grey) — grows with spacer count
    lines.append(seg(st_top, (bx, by), "#888", 2))            # stem (grey)
    if sa:
        lines.append(seg(st, sa, "#888", 2))                  # seatpost (grey)

    marks = (f'<circle cx="{P((bx,by)).split(",")[0]}" cy="{P((bx,by)).split(",")[1]}" r="4.5" fill="#2563eb">'
             f'<title>bar center</title></circle>')
    if sa:
        marks += (f'<circle cx="{P(sa).split(",")[0]}" cy="{P(sa).split(",")[1]}" r="5" fill="#16a34a">'
                  f'<title>saddle</title></circle>')

    # LEGEND now on the RIGHT edge, right-aligned, stacked top-down
    legend = (f'<g font-size="10" text-anchor="end">'
              f'<text x="{w-8}" y="16" fill="{color}">■ frame (head+seat tube)</text>'
              f'<text x="{w-8}" y="29" fill="#888">— stem / spacers / seatpost (grey)</text>'
              f'<text x="{w-8}" y="42" fill="#16a34a">● saddle</text>'
              f'<text x="{w-8}" y="55" fill="#2563eb">● handlebar</text></g>')

    return (f'<svg viewBox="0 0 {w} {h}" style="border:1px solid #e3e6ea;border-radius:8px">'
            f'<rect width="{w}" height="{h}" fill="{fill}"/>{gridlines}'
            f'{"".join(lines)}{marks}{legend}</svg>')