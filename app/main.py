from fastapi import FastAPI, Depends, Form, Request
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy.orm import Session

from app.db import Base, engine, get_db
from app.models import User, Bike, Part, BikePart
from app.auth import hash_password, verify_password, get_current_user, NotAuthenticated
from app.geometry import fit_metrics

app = FastAPI(title="Bike Garage")
app.add_middleware(
    SessionMiddleware,
    secret_key="change-me-in-prod-but-fine-for-learning",
    session_cookie="bg_session",
)
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)


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
@app.get("/")
def index(
    request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    bikes = db.query(Bike).filter(Bike.user_id == user.id).all()
    return templates.TemplateResponse(request, "bikes/list.html", {"bikes": bikes})


@app.post("/bikes")
def create_bike(
    request: Request, brand: str = Form(...), model: str = Form(...),
    year: int | None = Form(None), frame_size: str | None = Form(None),
    stack: float | None = Form(None), reach: float | None = Form(None),
    head_tube_angle: float | None = Form(None),   # <-- now accepted + forwarded
    seat_tube_angle: float | None = Form(None),   # <-- now accepted + forwarded
    seat_tube_length: float | None = Form(None),
    saddle_height: float | None = Form(None),
    total_weight: float | None = Form(None),       # renamed from frame_weight, stored as entered
    user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    bike = Bike(
        user_id=user.id, brand=brand, model=model, year=year, frame_size=frame_size,
        stack=stack, reach=reach, head_tube_angle=head_tube_angle, seat_tube_angle=seat_tube_angle,
        seat_tube_length=seat_tube_length, saddle_height=saddle_height, total_weight=total_weight,
    )
    db.add(bike); db.commit(); db.refresh(bike)
    return RedirectResponse(url=f"/bikes/{bike.id}", status_code=302)


@app.get("/bikes/{bike_id}")
def bike_detail(
    bike_id: int, request: Request,
    user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    bike = db.query(Bike).filter(Bike.id == bike_id, Bike.user_id == user.id).first()
    if not bike:
        return RedirectResponse(url="/", status_code=302)
    m = fit_metrics(bike, list(bike.installed_parts))
    return templates.TemplateResponse(request, "bike_detail.html", {"bike": bike, "m": m})


@app.post("/bikes/{bike_id}/parts")
def add_part_to_bike(
    bike_id: int, name: str = Form(...), ptype: str = Form(...),
    length: float | None = Form(None), angle: float | None = Form(None),
    setback: float | None = Form(None), weight_g: float | None = Form(None),   # optional now
    user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    bike = db.query(Bike).filter(Bike.id == bike_id, Bike.user_id == user.id).first()
    if not bike:
        return RedirectResponse(url="/", status_code=302)
    part = Part(
        user_id=user.id, name=name, ptype=ptype,
        length=length, angle=angle, setback=setback, weight_g=weight_g,
    )
    db.add(part); db.commit(); db.refresh(part)
    db.add(BikePart(bike_id=bike.id, part_id=part.id, quantity=1))
    db.commit()
    return RedirectResponse(url=f"/bikes/{bike_id}", status_code=302)


@app.post("/parts/{part_id}/remove")
def remove_part(
    part_id: int, bike_id: int = Form(...),
    user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    bp = db.query(BikePart).filter(BikePart.part_id == part_id, BikePart.bike_id == bike_id).first()
    if bp:
        db.delete(bp); db.commit()
    return RedirectResponse(url=f"/bikes/{bike_id}", status_code=302)