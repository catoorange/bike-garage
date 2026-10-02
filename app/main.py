import os
from pathlib import Path
from fastapi import FastAPI, Depends, Form, Request, Query, UploadFile, File
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy.orm import Session
from typing import Optional

from app.db import Base, engine, get_db
from app.models import User, Bike, Part, BikePart, BikeModel, Rider, Photo
from app.auth import hash_password, verify_password, get_current_user, NotAuthenticated
from app.geometry import fit_metrics, gearing_table
from app.render import to_svg
from app.render_overlay import render_overlay
import uuid as _uuid
from app.seed import seed_bike_models


app = FastAPI(title="Bike Garage")
app.add_middleware(
    SessionMiddleware,
    secret_key=os.environ["BG_SECRET_KEY"],
    session_cookie="bg_session",
)
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

#gallery --- 10-2
_DB_DEFAULT = Path(__file__).resolve().parent.parent / "bike_garage.db"          # identical to db.py's default
UPLOAD_DIR = Path(os.environ.get("BIKE_GARAGE_UPLOADS",
                  str(Path(os.environ.get("BIKE_GARAGE_DB", _DB_DEFAULT)).parent / "uploads")))
(UPLOAD_DIR / "gallery").mkdir(parents=True, exist_ok=True)
(UPLOAD_DIR / "avatar").mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")
_ALLOWED = {".jpg", ".jpeg", ".png", ".webp", ".gif"}


async def _store(f: UploadFile, kind: str):
    ext = os.path.splitext(f.filename or "")[1].lower()
    if ext not in _ALLOWED: return None
    data = await f.read()
    if len(data) > 5 * 1024 * 1024: return None
    name = f"{_uuid.uuid4().hex}{ext}"
    (UPLOAD_DIR / kind / name).write_bytes(data)
    return name


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)
    seed_bike_models()


@app.exception_handler(NotAuthenticated)
async def not_authenticated_handler(request: Request, exc: NotAuthenticated):
    return RedirectResponse(url="/login", status_code=302)


# --- Auth (Phase 2) ---------------------------------------------------------
@app.get("/register")
def register_form(request: Request):
    return templates.TemplateResponse(request, "register.html")


@app.post("/register")
def do_register(
    request: Request, username: str = Form(...), email: str = Form(...),
    password: str = Form(...), db: Session = Depends(get_db),
):
    if db.query(User).filter(User.email == email).first():
        return templates.TemplateResponse(request, "register.html", {"error": "Email already registered"})
    user = User(username=username, email=email, password_hash=hash_password(password))
    db.add(user); db.commit(); db.refresh(user)
    request.session["user_id"] = user.id
    return RedirectResponse(url="/", status_code=302)


@app.get("/login")
def login_form(request: Request):
    return templates.TemplateResponse(request, "login.html")


@app.post("/login")
def do_login(
    request: Request, email: str = Form(...), password: str = Form(...),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(password, user.password_hash):
        return templates.TemplateResponse(request, "login.html", {"error": "Invalid email or password"})
    request.session["user_id"] = user.id
    return RedirectResponse(url="/", status_code=302)


@app.post("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=302)


# --- Bikes + parts, scoped to current user ---------------------------------
# ---added 09-28 - Landing Page route
@app.get("/", include_in_schema=False)
def home(request: Request, db: Session = Depends(get_db)):
    uid = request.session.get("user_id")
    if uid and db.get(User, uid):            # only bounce for a REAL user
        return RedirectResponse("/bikes", status_code=307)
    return templates.TemplateResponse(request, "home.html")   # guests AND stale-cookie ghosts see the landing


@app.get("/bikes")
def index(
    request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    bikes = db.query(Bike).filter(Bike.user_id == user.id).all()
    return templates.TemplateResponse(request, "bikes/list.html", {"bikes": bikes})


@app.get("/bikes/new")
def new_bike_page(request: Request, q: str = Query(""),
                  db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    query = db.query(BikeModel)
    if q:
        like = f"%{q}%"
        from sqlalchemy import or_
        query = query.filter(or_(BikeModel.brand.ilike(like), BikeModel.model.ilike(like)))
    presets = query.order_by(BikeModel.brand, BikeModel.model).all()
    return templates.TemplateResponse(request, "bikes/new.html", {"presets": presets, "q": q})


# --added 09-28-26 --
@app.post("/bikes/create")
def create_bike(
    mode: str = Form("custom"),             # "preset" or "custom"
    preset_id: str = Form(None),
    brand: str = Form(""), model: str = Form(""), year: str = Form(None),
    frame_size: str = Form(None), head_tube_length: str = Form(None),
    stack: str = Form(None), reach: str = Form(None),
    head_tube_angle: str = Form(None), seat_tube_angle: str = Form(None),
    chainstay_length: str = Form(None), total_weight: str = Form(None),
    db: Session = Depends(get_db), user: User = Depends(get_user_id_shadows = None) if False else Depends(get_current_user),
):
    def num(v):
        v = (v or "").strip()
        return float(v) if v else None

    bike = Bike(user_id=user.id)

    if mode == "preset" and preset_id:
        bm = db.get(BikeModel, int(preset_id))
        if not bm:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="preset not found")
        bike.brand, bike.model = bm.brand, bm.model
        bike.year, bike.frame_size = bm.year, bm.frame_size
        bike.head_tube_length, bike.stack, bike.reach = bm.head_tube_length, bm.stack, bm.reach
        bike.head_tube_angle, bike.seat_tube_angle = bm.head_tube_angle, bm.seat_tube_angle
        bike.chainstay_length = bm.chainstay_length
    else:
        # custom path — fields exactly as before, head_tube_length is new
        bike.brand, bike.model = brand, model
        bike.year = int(year) if year and year.strip() else None
        bike.frame_size = (frame_size or "").strip() or None
        bike.head_tube_length = num(head_tube_length)  # ← was missing in original custom form
        bike.stack = num(stack)
        bike.reach = num(reach)
        bike.head_tube_angle = num(head_tube_angle)
        bike.seat_tube_angle = num(seat_tube_angle)
        bike.chainstay_length = num(chainstay_length)
        bike.total_weight = num(total_weight)

    db.add(bike)
    db.commit()
    return RedirectResponse(f"/bikes/{bike.id}", status_code=303)


@app.get("/bikes/{bike_id}")
def bike_detail(
    bike_id: int,                                   # no default — MUST come first
    request: Request,                               # no default
    bg: str = "dark",                               # default → must come AFTER the two above
    user: User = Depends(get_current_user),         # has default
    db: Session = Depends(get_db),                  # has default
):
    bike = db.query(Bike).filter(Bike.id == bike_id, Bike.user_id == user.id).first()
    if not bike:
        return RedirectResponse(url="/", status_code=302)

    m = fit_metrics(bike, list(bike.installed_parts))
    show_wheels = request.query_params.get("show_wheels") == "1"
    show_rider  = request.query_params.get("show_rider") == "1"     # NEW (same pattern as wheels)
    rider = db.query(Rider).filter(Rider.user_id == user.id).first()

    svg = to_svg(
        bike, list(bike.installed_parts),
        show_wheels=show_wheels,
        show_rider=show_rider,
        rider=rider,
        bg=bg,
    )

    return templates.TemplateResponse(
        request, "bike_detail.html",
        {"bike": bike, "m": m, "svg": svg,
         "show_wheels": show_wheels,
         "show_rider": show_rider,
         "photos": bike.photos},          # gallery section + banner read {{ photos }}
    )


@app.post("/bikes/{bike_id}/delete")
def delete_bike(
    bike_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # filter on user_id too so someone can't delete another user's bike by guessing an id
    bike = db.query(Bike).filter(Bike.id == bike_id, Bike.user_id == user.id).first()
    if bike:
        db.delete(bike)          # cascade removes its BikePart rows automatically
        db.commit()
    return RedirectResponse(url="/", status_code=302)


@app.post("/bikes/{bike_id}/parts")
def add_part_to_bike(
    bike_id: int, name: str = Form(...), ptype: str = Form(...),
    length: float | None = Form(None), angle: float | None = Form(None),
    setback: float | None = Form(None), weight_g: float | None = Form(None),   # optional now
    user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    bike = db.query(Bike).filter(Bike.id == bike_id, Bike.user_id == user.id).first()
    if not bike: return RedirectResponse(url="/bikes", status_code=303)
    for bp in bike.installed_parts:
        if bp.part.ptype == ptype:
            db.delete(bp)
    db.commit()
    part = Part(
        user_id=user.id, name=name, ptype=ptype,
        length=length, angle=angle, setback=setback, weight_g=weight_g,
    )
    db.add(part); db.commit(); db.refresh(part)
    db.add(BikePart(bike_id=bike.id, part_id=part.id, quantity=1))
    db.commit()
    return RedirectResponse(url=f"/bikes/{bike_id}", status_code=302)


@app.post("/bikes/{bike_id}/geometry")
def update_geometry(
    bike_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    stack: str | None = Form(None),
    reach: str | None = Form(None),
    head_tube_angle: str | None = Form(None),
    seat_tube_angle: str | None = Form(None),
    saddle_height: str | None = Form(None),
    total_weight: str | None = Form(None),
    wheel_size: str | None = Form(None),
    bb_drop: str | None = Form(None),
    wheelbase: str | None = Form(None),
    fork_offset: str | None = Form(None),      # FIX D: was model syntax `Mapped[Optional[float]] = None` → silently became a query param
    #-- 10-1 edit
    crank_length: str | None = Form(None),
    crank_angle: str | None = Form(None),
):
    def num(v):
        v = (v or "").strip()
        return float(v) if v else None

    bike = db.query(Bike).filter(Bike.id == bike_id, Bike.user_id == user.id).first()
    if not bike:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="bike not found")

    bike.stack = num(stack)
    bike.reach = num(reach)
    bike.head_tube_angle = num(head_tube_angle)
    bike.seat_tube_angle = num(seat_tube_angle)
    bike.saddle_height = num(saddle_height)
    bike.total_weight = num(total_weight)
    bike.wheel_size = num(wheel_size)
    bike.bb_drop = num(bb_drop)
    bike.wheelbase = num(wheelbase)
    bike.fork_offset = num(fork_offset)
    #-- 10-1 edit
    bike.crank_length = num(crank_length)     # num() blank→None, same as your other cols
    bike.crank_angle = num(crank_angle)
    db.commit()

    bg = request.query_params.get("bg")
    return RedirectResponse(f"/bikes/{bike.id}" + (f"?bg={bg}" if bg else ""), status_code=303)


@app.get("/overlay")
def overlay(
    request: Request,
    bike: list[int] = Query(default=[]),         # ?bike=1&bike=2 (the checked boxes)
    stem_a: str | None = None,                   # "90,-17"
    stem_b: str | None = None,                   # "60,+6"
    bg: str = "dark",
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from types import SimpleNamespace as NS

    all_bikes = db.query(Bike).filter(Bike.user_id == user.id).all()          # every bike, to list as checkboxes
    bikes = [b for b in all_bikes if not bike or b.id in bike]               # only the checked ones get drawn
    selected_ids = {b.id for b in bikes}

    def with_stem(bike_obj, spec, label):
        L, A = (float(x) for x in spec.split(","))
        parts = [bp for bp in bike_obj.installed_parts if bp.part.ptype != "stem"]
        parts.append(NS(part=NS(ptype="stem", length=L, angle=A, weight_g=None), quantity=1))
        return {"bike": bike_obj, "parts": parts, "label": f"{label} ({L}/{A}\u00b0)"}

    configs = []
    if len(bikes) == 1 and (stem_a or stem_b):
        b = bikes[0]                                                           # SAME bike, ghosted twice
        configs.append(with_stem(b, stem_a or "90,-17", "Setup A"))
        if stem_b:
            configs.append(with_stem(b, stem_b, "Setup B"))
    else:
        configs = [{"bike": b, "parts": list(b.installed_parts), "label": f"{b.brand} {b.model}"}
                   for b in bikes]

    svg = render_overlay(configs, bg=bg)         # honors bg
    return templates.TemplateResponse(
        request, "overlay.html",
        {"svg": svg, "all_bikes": all_bikes, "selected_ids": selected_ids},
    )


@app.post("/parts/{part_id}/remove")
def remove_part(
    part_id: int,
    bike_id: int = Form(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    bp = db.query(BikePart).filter(
        BikePart.part_id == part_id, BikePart.bike_id == bike_id
    ).first()
    if bp:
        part = bp.part
        db.delete(bp); db.commit()
        # if no other bike links this part anymore, delete the orphaned Part row too
        still_linked = db.query(BikePart).filter(BikePart.part_id == part.id).count()
        if not still_linked:
            db.delete(part); db.commit()
    return RedirectResponse(url=f"/bikes/{bike_id}", status_code=302)


# -- added 09-29   FIX E: keyword-after-positional was a SyntaxError; one merged dict now
@app.get("/profile")
def profile_page(request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rider = db.query(Rider).filter_by(user_id=user.id).first()
    avatar = db.query(Photo).filter_by(user_id=user.id, kind="avatar").first()
    return templates.TemplateResponse(request, "profile.html", {"r": rider, "avatar": avatar})


@app.post("/profile")
def save_profile(
    height_mm: str = Form(None), inseam_mm: str = Form(None),
    arm_length_mm: str = Form(None), torso_length_mm: str = Form(None),
    shoulder_width_mm: str = Form(None), weight_kg: str = Form(None),
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    def num(v):
        v = (v or "").strip()
        return float(v) if v else None

    rider = db.query(Rider).filter_by(user_id=user.id).first()
    if not rider:                      # create-on-save, no signup-flow change needed
        rider = Rider(user_id=user.id)
        db.add(rider)

    rider.height_mm = num(height_mm)
    rider.inseam_mm = num(inseam_mm)
    rider.arm_length_mm = num(arm_length_mm)
    rider.torso_length_mm = num(torso_length_mm)
    rider.shoulder_width_mm = num(shoulder_width_mm)
    rider.weight_kg = num(weight_kg)
    db.commit()
    return RedirectResponse("/profile", status_code=303)


# gearing page route -- 10-1
@app.get("/gearing")
def gearing(request: Request, user: User = Depends(get_current_user)):
    qp = request.query_params
    front = [float(qp[k]) for k in ("front_1", "front_2")
             if qp.get(k, "").strip().replace(".", "", 1).isdigit()]
    rear = [float(qp[f"cog_{i}"]) for i in range(1, 14)
            if qp.get(f"cog_{i}", "").strip().replace(".", "", 1).isdigit()]
    front = front or [52.0, 36.0]          # only when user entered nothing yet
    rear = rear or [30, 28, 25, 22, 20, 18, 16, 14, 13, 12, 11]
    cadence = float(qp.get("cadence") or 90)
    wheel = float(qp.get("wheel_size") or 622.0)
    rows = gearing_table(front, rear, cadence, wheel)

    unit = qp.get("unit") or (user.unit_preference or "metric")     # display-layer conversion only
    f = 0.621371 if unit == "imperial" else 1.0
    for r in rows:
        r["kmh"] = [round(v * f, 1) for v in r["kmh"]]

    return templates.TemplateResponse(request, "gearing.html",
        {"rows": rows, "front": front, "rear": rear,
         "cadence": cadence, "wheel": wheel, "unit": unit})


# ---------- uploads (ckpt6): gallery + avatar ----------
async def _store_ok(): pass   # placeholder to keep ordering obvious; real _store is above


@app.post("/bikes/{bike_id}/photos")
async def add_bike_photos(bike_id: int, request: Request, files: list[UploadFile] = File(...),
                          user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    bike = db.query(Bike).filter(Bike.id == bike_id, Bike.user_id == user.id).first()
    if not bike: return RedirectResponse(url="/bikes", status_code=303)
    for f in files:
        name = await _store(f, "gallery")
        if name:
            db.add(Photo(user_id=user.id, bike_id=bike.id, kind="gallery", stored_name=name, orig_name=f.filename))
    db.commit()
    return RedirectResponse(url=f"/bikes/{bike_id}?bg={request.query_params.get('bg','dark')}", status_code=303)


@app.post("/profile/avatar")
async def set_avatar(request: Request, file: UploadFile = File(...),
                     user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    name = await _store(file, "avatar")
    if name:
        old = db.query(Photo).filter_by(user_id=user.id, kind="avatar").first()
        if old:   # replace-on-upload like single-slot parts; remove stale file from disk too
            try: (UPLOAD_DIR / "avatar" / old.stored_name).unlink(missing_ok=True)
            except Exception: pass
            db.delete(old); db.flush()
        db.add(Photo(user_id=user.id, bike_id=None, kind="avatar", stored_name=name, orig_name=file.filename))
        db.commit()
    return RedirectResponse(url="/profile", status_code=303)


@app.post("/photos/{photo_id}/delete")
def delete_photo(photo_id: int, request: Request,                       # FIX F: had no request param + phantom helper
                 user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = db.query(Photo).filter(Photo.id == photo_id, Photo.user_id == user.id).first()
    back = request.headers.get("referer", "/bikes")
    if p:
        (UPLOAD_DIR / p.kind / p.stored_name).unlink(missing_ok=True); db.delete(p); db.commit()
    return RedirectResponse(url=back, status_code=303)