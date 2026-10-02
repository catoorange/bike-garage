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


def _ghost(bike, pts):
    """Build front hub from real fork numbers: crown + ACL along axis + offset perp."""
    ht_top, ht_bot, seat_top = pts["ht_top"], pts["ht_bot"], pts["seat_top"]

    ws = bike.wheel_size if getattr(bike, "wheel_size", None) else 622.0
    tire = getattr(bike, "tire_allowance", None) or 15.0
    r = ws / 2 + tire

    axx, axy = ht_bot[0] - ht_top[0], ht_bot[1] - ht_top[1]      # head-tube direction (top→bottom)
    ulen = math.hypot(axx, axy) or 1.0
    ux, uy = axx/ulen, axy/ulen                                   # down the fork leg
    px, py = -uy, ux                                              # perpendicular; sign → +x forward

    acl = bike.fork_length if getattr(bike, "fork_length", None) is not None else 370.0   # axle-to-crown
    offset = bike.fork_offset if getattr(bike, "fork_offset", None) is not None else 50.0  # rake/offset

    front = (ht_bot[0] + ux*acl + px*offset, ht_bot[1] + uy*acl + py*offset)   # true hub position

    drop = bike.bb_drop if getattr(bike, "bb_drop", None) is not None else 73.0
    rc = math.sqrt(max((bike.chainstay_length or 425.0)**2 - drop*drop, 1.0))
    rear = (-rc, front[1])      # rear axle same height as front → level wheels

    return {
        "top_tube":  (ht_top, seat_top),
        "down_tube": (ht_bot, (0.0, 0.0)),
        "fork":      (ht_bot, front),     # short stub — not the full 370
        "chainstay": ((0.0, 0.0), rear),
        "seatstay":  (seat_top, rear),
        "rear_axle": rear, "front_axle": front, "wheel_r": r,
    }


def _bg_style(bg):
    """Return (fill_color, line_opacity, grid_stroke). grid_stroke None = no grid."""
    return {
        "light": ("#fafafa", 1.0, None),
        "dark":  ("#16181d", 0.95, None),
        "grid":  ("#ffffff", 1.0, "#e3e6ea"),   # light + visible gridlines
    }.get(bg, ("#fafafa", 1.0, None))


def to_svg(bike, installed, *, w=560, h=380, color="#c8102e", bg="light",
           show_wheels=False, show_rider=False, rider=None) -> str:
    from app.geometry import bar_center, steerer_top, rider_points
    pts = frame_points(bike, installed)
    g = _ghost(bike, pts)
    bx, by = bar_center(bike, installed)
    st_top = steerer_top(bike, installed)
    ghost_col = "#bbb" if bg in ("light", "grid") else "#ffffff"   # visible on light/white too

    fill, opac, grid = _bg_style(bg)
    axis_txt = "#bbb" if bg == "dark" else "#888"
    ghost_op = "0.35" if bg in ("light", "grid") else "0.5"
    rider_col = "#7c3aed"   # distinct so the figure reads separately from frame/ghost

    st, sa = pts["seat_top"], pts["saddle"]

    # ---- compute rider points ONCE (points only; SVG built later once Pt/s exist) ----
    #update on 10-1 jon
    rp = None
    if show_rider and rider is not None:
        hip = sa if sa is not None else st
        cl = bike.crank_length if bike.crank_length is not None else 172.5
        ca = math.radians(bike.crank_angle if bike.crank_angle is not None else 270.0)  # default: bottom of stroke
        pedal = (cl*math.cos(ca), cl*math.sin(ca))          # real pedal at that angle
        anchor = {"saddle": hip, "bar_center": (bx, by), "pedal": pedal}
        rp = rider_points(anchor, rider)

    all_pts = [p for p in pts.values() if p] + [st_top, (bx, by)]
    all_pts += [g["rear_axle"], g["front_axle"]]          # so tubes don't clip
    if show_wheels:                                        # include wheel extents
        for ax, ay in (g["rear_axle"], g["front_axle"]):
            all_pts += [(ax - g["wheel_r"], ay), (ax + g["wheel_r"], ay),
                        (ax, ay - g["wheel_r"]), (ax, ay + g["wheel_r"])]
    if rp:                                                 # keep head/limbs/joints in frame
        for seg_pts in rp["polylines"]:
            all_pts += seg_pts
        all_pts += rp.get("joints", [])
        hc = rp["head"]; all_pts += [(hc["cx"] - hc["r"], hc["cy"] + hc["r"])]
    xs = [p[0] for p in all_pts]; ys = [p[1] for p in all_pts]
    x0, x1 = min(xs) - 30, max(xs) + 150   # +150 right gutter so legend never overlaps tubes
    y0, y1 = min(ys) - 90, max(ys) + 40      # extra headroom above bar / below wheels
    s = min(w / (x1 - x0 or 1), h / (y1 - y0 or 1))
    ox = (w - (x1 - x0) * s) / 2          # leftover horizontal space, split left/right
    oy = (h - (y1 - y0) * s) / 2          # leftover vertical → no top-bias

    def P(p): return f"{(p[0]-x0)*s + ox:.1f},{(y1-p[1])*s + oy:.1f}"   # string "x,y" (used by seg/marks)
    def Pt(p): return ((p[0]-x0)*s + ox, (y1-p[1])*s + oy)               # numeric (used for figure paths/head)

    def seg(a, b, c, sw, op=None):
        o = opac if op is None else op
        ax, ay = P(a).split(","); bx_, by_ = P(b).split(",")
        return (f'<line x1="{ax}" y1="{ay}" x2="{bx_}" y2="{by_}" stroke="{c}" '
                f'stroke-width="{sw}" opacity="{o}"/>')

    # optional gridlines every 50mm, only when bg has a grid color
    gridlines = ""
    if grid:
        gl = []
        gx = math.ceil(x0/50)*50
        while gx <= x1: gl.append(f'<line x1="{P((gx,y0)).split(",")[0]}" y1="0" x2="{P((gx,y1)).split(",")[0]}" y2="{h}" stroke="{grid}"/>'); gx += 50
        gy = math.ceil(y0/50)*50
        while gy <= y1: gl.append(f'<line x1="0" y1="{P((x0,gy)).split(",")[1]}" x2="{w}" y2="{P((x1,gy)).split(",")[1]}" stroke="{grid}"/>'); gy += 50
        gridlines = "".join(gl)

    lines = [seg(pts["ht_bot"], pts["ht_top"], color, 3)]   # head tube (frame color)
    lines.append(seg((0, 0), st, color, 3))                  # seat tube (frame color)
    lines.append(seg(pts["ht_top"], st_top, "#888", 2))      # spacers (grey) — grows with spacer count
    lines.append(seg(st_top, (bx, by), "#888", 2))           # stem (grey)
    if sa:
        lines.append(seg(st, sa, "#888", 2))                  # seatpost (grey)

    for key in ("top_tube", "down_tube", "fork", "chainstay", "seatstay"):
        a, b = g[key]
        lines.append(seg(a, b, ghost_col, 1.0, ghost_op))

    wheels = ""
    if show_wheels:
        for (cx, cy), r in ((g["rear_axle"], g["wheel_r"]), (g["front_axle"], g["wheel_r"])):
            cxpx, cypx = P((cx, cy)).split(",")
            wheels += (f'<circle cx="{cxpx}" cy="{cypx}" r="{r*s:.1f}" fill="none" '
                       f'stroke="{ghost_col}" stroke-width="1" opacity="{ghost_op}"/>')  # was stroke={ghost_col} (literal!)

    # ---- rider SVG built HERE, after Pt/s exist: segmented limbs + joint dots + head ----
    rider_svg = ""
    if rp:
        for seg_pts in rp["polylines"]:
            d = " ".join(("M" if i == 0 else "L") + f"{Pt(p)[0]:.1f},{Pt(p)[1]:.1f}"
                         for i, p in enumerate(seg_pts))
            rider_svg += (f'<path d="{d}" fill="none" stroke="{rider_col}" '
                          f'stroke-width="2" stroke-linecap="round" opacity="0.9"/>')
        for jp in rp.get("joints", []):                       # knee/elbow markers
            jx, jy = Pt(jp)
            rider_svg += f'<circle cx="{jx:.1f}" cy="{jy:.1f}" r="3" fill="{rider_col}"/>'
        for hp in rp.get("hands", []):   # hand marker on the bar
            hx, hy = Pt(hp)
            rider_svg += f'<circle cx="{hx:.1f}" cy="{hy:.1f}" r="3.5" fill="none" stroke="{rider_col}" stroke-width="1.5"><title>hand</title></circle>'
        for f in rp.get("feet", []):                   # foot contact marker (mirrors hand ring)
            cx_, cy_ = Pt(f["contact"])
            rider_svg += (f'<circle cx="{cx_:.1f}" cy="{cy_:.1f}" r="3.5" fill="none" '
                          f'stroke="{rider_col}" stroke-width="1.5"><title>foot on pedal</title></circle>')
        hc = rp["head"]; hx, hy = Pt((hc["cx"], hc["cy"]))
        rider_svg += (f'<circle cx="{hx:.1f}" cy="{hy:.1f}" r="{hc["r"]*s:.1f}" '
                    f'fill="none" stroke="{rider_col}" stroke-width="2" opacity="0.9"/>')
        # neck + head, drawn along the actual spine direction
        ns = rp["neck"]                                  # [shoulder, neck_top] both on spine line
        nd = f"M{Pt(ns[0])[0]:.1f},{Pt(ns[0])[1]:.1f} L{Pt(ns[1])[0]:.1f},{Pt(ns[1])[1]:.1f}"
        rider_svg += (f'<path d="{nd}" fill="none" stroke="{rider_col}" '
                      f'stroke-width="2" stroke-linecap="round" opacity="0.9"/>')
        hc = rp["head"]; hx, hy = Pt((hc["cx"], hc["cy"]))
        rider_svg += (f'<circle cx="{hx:.1f}" cy="{hy:.1f}" r="{hc["r"]*s:.1f}" '
                      f'fill="none" stroke="{rider_col}" stroke-width="2" opacity="0.9"/>')
        
    marks = (f'<circle cx="{P((bx,by)).split(",")[0]}" cy="{P((bx,by)).split(",")[1]}" r="4.5" fill="#2563eb">'
             f'<title>bar center</title></circle>')
    if sa:
        marks += (f'<circle cx="{P(sa).split(",")[0]}" cy="{P(sa).split(",")[1]}" r="5" fill="#16a34a">'
                  f'<title>saddle</title></circle>')

    legend_lines = [
        f'<text x="{w-8}" y="16" fill="{color}">■ frame (head+seat tube)</text>',
        f'<text x="{w-8}" y="29" fill="#888">— stem / spacers / seatpost (grey)</text>',
        f'<text x="{w-8}" y="42" fill="#16a34a">● saddle</text>',
        f'<text x="{w-8}" y="55" fill="#2563eb">● handlebar</text>',
    ]
    if rp:
        legend_lines.append(f'<text x="{w-8}" y="68" fill="{rider_col}">◍ rider (proportional)</text>')
    legend = f'<g font-size="10" text-anchor="end">{"".join(legend_lines)}</g>'

    return (f'<svg viewBox="0 0 {w} {h}" style="border:1px solid #e3e6ea;border-radius:8px">'
            f'<rect width="{w}" height="{h}" fill="{fill}"/>{gridlines}'
            f'{wheels}{rider_svg}{"".join(lines)}{marks}{legend}</svg>')


# convenience alias kept for call sites expecting render()/to_svg naming
def render(bike, installed, **kw):
    return to_svg(bike, installed, **kw)