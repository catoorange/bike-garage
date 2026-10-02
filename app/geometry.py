"""Pure geometry: frame numbers + installed parts -> fit/weight metrics. BB at origin, +x fwd, +y up."""
import math
from typing import Optional

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


#def crank_length(bike, installed) -> float | None:
 #   c = next((bp.part.length for bp in _by_type(installed, "crankset") if bp.part.length is not None), None)
  #  return c


def fit_metrics(bike, installed) -> dict:
    bx, by = bar_center(bike, installed)
    saddle = bike.saddle_height or 0.0
    cl = bike.crank_length                       # single source of truth (settings form)
    ca = math.radians(bike.crank_angle if bike.crank_angle is not None else 270.0)
    pedal_y = cl * math.sin(ca) if cl is not None else None   # real pedal height at saved angle
    return {
        "bar_y": round(by, 1),
        "cockpit_reach": round(abs(bx), 1),
        "cockpit_drop": (round(saddle - by, 1) if saddle else None),
        "saddle_height": round(saddle, 1) if saddle else None,
        "spacer_height": round(spacer_height(installed), 1) or None,
        "crank_length": round(cl, 1) if cl is not None else None,
        "pedal_below_bb": round(-pedal_y, 1) if pedal_y is not None else None,   # >0 = below BB at saved angle
        "total_weight": round(bike.total_weight, 0) if bike.total_weight else None,
    }

# -- added 09-29
# --- ghost-frame + wheel defaults (schematic; fine to refine later) ---
_DEF_WHEEL = 622.0      # 700c
_DEF_DROP  = 70.0       # BB below axle line, mm
_TIRE      = 15.0       # rim→ground tire allowance, mm

def _ws(bike):   return bike.wheel_size or _DEF_WHEEL
def _drop(bike): return bike.bb_drop if (bike.bb_drop not in (None,)) else _DEF_DROP

def ghost_points(bike):
    """Implied diamond tubes + axle positions in mm (BB origin). Pure."""
    ws, drop = _ws(bike), _drop(bike)
    r   = ws / 2.0 + _TIRE                       # rim center → ground radius
    cs  = bike.chainstay_length or 415.0         # rear chainstay (near horizontal)
    ra_x = math.sqrt(max(cs*cs - drop*drop, 1.0))  # horizontal rear-center
    rear  = (-ra_x, -drop)                          # rear axle (behind + below BB)
    # front axle from wheelbase, else reach-ish default
    wb  = bike.wheelbase or (ra_x + (bike.reach or 415.0))
    front = (wb - ra_x, -drop)                      # front axle = fc forward, same height
    ht_bot = (0.0, 0.0); ht_top = ((bike.reach or 70.0), (bike.stack or 560.0))
    st_top = (-ra_x*0.35, (bike.stack or 560.0) + (bike.head_tube_length or 120.0)*0.0)  # seat-top approx
    return {
        "rear_axle": rear, "front_axle": front, "wheel_r": r,
        "top_tube":  (ht_top, (st_top[0], st_top[1])),
        "down_tube": (ht_bot, ht_bot),           # head-tube bottom ≈ BB origin
        "fork":      ((ht_top[0]*0.55, ht_top[1]), front),
        "chainstay": ((0.0, 0.0), rear),
        "seatstay":  (st_top, rear),
    }

def wheel_specs(bike):
    g = ghost_points(bike)
    return [ (g["rear_axle"], g["wheel_r"]), (g["front_axle"], g["wheel_r"]) ]

#-- added 10-1-26



# ---------- geometry.py : rider stick-figure (checkpoint 4c — true linkage) ----------


def _two_bone(p0, p1, l1, l2, bend_sign):
    """Chain p0->joint->p1 with segment lengths l1,l2. If unreachable, straightens
    (which visually SAYS 'cockpit too far for this rider' — that's a fit signal)."""
    dx, dy = p1[0]-p0[0], p1[1]-p0[1]
    d = math.hypot(dx, dy) or 1e-6
    reach = l1 + l2
    if d > reach:                       # can't reach: straighten along the line
        f = reach / d
        p1 = (p0[0]+dx*f, p0[1]+dy*f); dx, dy = p1[0]-p0[0], p1[1]-p0[1]; d = math.hypot(dx, dy) or 1e-6
    a = (l1*l1 - l2*l2 + d*d) / (2*d)
    h = math.sqrt(max(l1*l1 - a*a, 0.0))
    ux, uy = dx/d, dy/d
    joint = (p0[0] + ux*a - uy*bend_sign*h, p0[1] + uy*a + ux*bend_sign*h)
    return joint, p1


def _intersect(c0, r0, c1, r1):
    """Point at distance r0 from c0 AND r1 from c1 (upper of the two solutions)."""
    dx, dy = c1[0]-c0[0], c1[1]-c0[1]; d = math.hypot(dx, dy) or 1e-6
    ux, uy = dx/d, dy/d
    a = (r0*r0 - r1*r1 + d*d) / (2*d)
    h2 = r0*r0 - a*a
    if h2 < 0:                                  # circles miss → can't perfectly fit this cockpit
        a = min(a, r0); h2 = 0.0                 # spine stays exact torso length, arm reads near-straight
    h = math.sqrt(h2)
    bx, by = c0[0] + ux*a, c0[1] + uy*a
    pA, pB = (bx - uy*h, by + ux*h), (bx + uy*h, by - ux*h)
    return pA if pA[1] >= pB[1] else pB          # shoulder above the hip→bar chord


def _foot(pedal, hip):
    """Foot sits LEVEL on the pedal (sole horizontal, toe +x), independent of crank angle."""
    L = 62.0                                   # foot length; tune or later scale off height
    heel = (pedal[0] - L*0.35, pedal[1])         # same y as pedal = flat sole
    toe  = (pedal[0] + L*0.65, pedal[1])
    return heel, toe, pedal                      # pedal is the ball-of-foot contact point


def rider_points(pts: dict, rider) -> dict:
    hip   = pts["saddle"]
    bar   = pts["bar_center"]
    pedal = pts.get("pedal") or (0.0, 0.0)

    inseam = getattr(rider, "inseam_mm", None) or 830.0
    torso  = getattr(rider, "torso_length_mm", None) or 560.0
    arm    = getattr(rider, "arm_length_mm") or 660.0
    height = getattr(rider, "height_mm", None) or 1750.0

    shoulder = _intersect(hip, torso, bar, arm*0.95)
    thigh, shin     = inseam*0.48, inseam*0.52
    upper_a, fore_a = arm*0.46,   arm*0.54
    knee,  _ = _two_bone(hip,      pedal, thigh,   shin,   bend_sign=+1)
    elbow, _ = _two_bone(shoulder, bar,   upper_a, fore_a, bend_sign=-1)

    heel, toe, contact = _foot(pedal, hip)            # NEW foot assembly
    # HEAD: on-spine, proportional to TORSO (not raw height); short neck so chin sits near shoulders
    spine_x, spine_y = shoulder[0] - hip[0], shoulder[1] - hip[1]
    sl = math.hypot(spine_x, spine_y) or 1.0
    ux_s, uy_s = spine_x / sl, spine_y / sl          # unit up the actual spine axis
    neck   = torso * 0.05                            # short stub ≈ 28mm — chin sits right at shoulders
    head_r = torso * 0.17                            # skull r ≈ 95mm on a 560 torso → reads human-sized
    head_c = (shoulder[0] + ux_s * (neck + head_r),   # still collinear with spine
              shoulder[1] + uy_s * (neck + head_r))
    return {
        "polylines": [
            [hip, knee, pedal],                        # leg
            [toe, contact, heel],                      # foot: toe → ball-of-foot(contact) → heel
            [hip, shoulder],                           # spine
            [shoulder, elbow, bar],                    # arm, hand lands on bar
        ],
        "joints": [knee, elbow],
        "hands":  [bar],
        "feet":   [{"toe": toe, "heel": heel, "contact": contact}],   # NEW foot marker data
        "head": {"cx": head_c[0], "cy": head_c[1], "r": head_r},
        "neck": [shoulder, (shoulder[0] + ux_s*neck, shoulder[1] + uy_s*neck)],
    }
#gearing page 10-1
def gearing_table(front_tc, rear_tc, cadence_rpm, wheel_size=622.0):
    """front_tc/rear_tc = ordered lists of tooth counts (blanks already stripped).
    Rows: one per cog (biggest→smallest), ratio + km/h at cadence."""
    circ_km = (wheel_size * math.pi) / 1e6         # rim bead-seat circumference, km/rev
    return [{"cog": r,
             "ratios": [round(f / r, 2) for f in front_tc],
             "kmh":    [round(cadence_rpm * (f / r) * circ_km * 60, 1) for f in front_tc]}
            for r in sorted(rear_tc, reverse=True)]