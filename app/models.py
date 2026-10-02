from datetime import datetime, timezone
from sqlalchemy import String, Float, Integer, DateTime, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db import Base
from typing import Optional


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String, unique=True)
    email: Mapped[str] = mapped_column(String, unique=True)
    password_hash: Mapped[str] = mapped_column(String)
    unit_preference: Mapped[str] = mapped_column(String, default="metric")  # phase 6
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )

    # a user owns many bikes; deleting a user can cascade later (phase 3+)
    bikes: Mapped[list["Bike"]] = relationship(back_populates="owner", order_by="Bike.id")


class Bike(Base):
    __tablename__ = "bikes"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    brand: Mapped[str] = mapped_column(String)
    model: Mapped[str] = mapped_column(String)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    frame_size: Mapped[str | None] = mapped_column(String, nullable=True)
    notes: Mapped[str | None] = mapped_column(String, nullable=True)

    # Frame baseline. Stored here for now; extracted into its own table in phase 3
    # when geometry.py needs it. All numbers are mm / degrees.
    head_tube_length: Mapped[float | None] = mapped_column(Float, nullable=True)
    stack: Mapped[float | None] = mapped_column(Float, nullable=True)
    reach: Mapped[float | None] = mapped_column(Float, nullable=True)
    head_tube_angle: Mapped[float | None] = mapped_column(Float, nullable=True)
    seat_tube_angle: Mapped[float | None] = mapped_column(Float, nullable=True)
    chainstay_length: Mapped[float | None] = mapped_column(Float, nullable=True)
    front_center: Mapped[Optional[float]] = None

    #jon added 09-24
    saddle_height: Mapped[float | None] = mapped_column(Float, nullable=True)   # BB -> top of saddle (rider setting)
    seat_tube_length: Mapped[float | None] = mapped_column(Float, nullable=True) # frame dim (for standover later)
    total_weight: Mapped[float | None] = mapped_column(Float, nullable=True)  # g, overall bike weight
    #

    owner: Mapped["User"] = relationship(back_populates="bikes")
    installed_parts: Mapped[list["BikePart"]] = relationship(
        cascade="all, delete-orphan", back_populates="bike"
    )

    wheel_size: Mapped[Optional[float]]     # ISO rim bead diameter mm (622=700c). blank→622
    bb_drop: Mapped[Optional[float]]        # BB below axle line. blank→70
    wheelbase: Mapped[Optional[float]]      # axle-to-axle. blank→derived from chainstay+reach
    # -- jon added 10-1
    crank_length: Mapped[Optional[float]] = mapped_column(nullable=True)   # mm; blank→172.5
    crank_angle:  Mapped[Optional[float]] = mapped_column(nullable=True)   # deg, 0°=forward/3 o'clock; blank→270 (6 o'clock)
    # --- gallery 10-2
    photos: Mapped[list["Photo"]] = relationship(cascade="all, delete-orphan")


class Part(Base):
    """A generic, user-named component. Type-specific dims are nullable so a stem
    doesn't have to carry a crank's fields. This is your requested 'generic part with
    custom names' model — no external catalog needed."""
    __tablename__ = "parts"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String)          # user's custom label, e.g. "my 80mm -17deg stem"
    ptype: Mapped[str] = mapped_column(String)           # stem | bar | spacer_set | seatpost | saddle ...

    # Dimension fields. Fill only the ones that apply to ptype.
    length: Mapped[float | None] = mapped_column(Float, nullable=True)       # stem length, spacer height each...
    angle: Mapped[float | None] = mapped_column(Float, nullable=True)        # stem rise/drop deg, bar sweep
    setback: Mapped[float | None] = mapped_column(Float, nullable=True)       # seatpost setback
    diameter: Mapped[float | None] = mapped_column(Float, nullable=True)      # clamp / steerer / bar dia
    quantity: Mapped[int] = mapped_column(Integer, default=1)                # spacer count etc.
    extra: Mapped[dict | None] = mapped_column(JSON, nullable=True)            # catch-all for odd dims

    #jon added 09-24
    weight_g: Mapped[float | None] = mapped_column(Float, nullable=True)        # mass of this part


class BikePart(Base):
    """Join table: which part is installed on which bike, where, and how many."""
    __tablename__ = "bike_parts"

    id: Mapped[int] = mapped_column(primary_key=True)
    bike_id: Mapped[int] = mapped_column(ForeignKey("bikes.id"))
    part_id: Mapped[int] = mapped_column(ForeignKey("parts.id"))
    position: Mapped[str | None] = mapped_column(String, nullable=True)   # 'front'/'rear'/'saddle'/...
    quantity: Mapped[int] = mapped_column(Integer, default=1)

    bike: Mapped["Bike"] = relationship(back_populates="installed_parts")
    part: Mapped["Part"] = relationship()


# -- new 09-28
class BikeModel(Base):
    __tablename__ = "bike_models"

    id: Mapped[int] = mapped_column(primary_key=True)
    brand: Mapped[str]
    model: Mapped[str]
    year: Mapped[Optional[int]]
    frame_size: Mapped[Optional[str]]
    head_tube_length: Mapped[Optional[float]]
    stack: Mapped[Optional[float]]
    reach: Mapped[Optional[float]]
    head_tube_angle: Mapped[Optional[float]]
    seat_tube_angle: Mapped[Optional[float]]
    chainstay_length: Mapped[Optional[float]]
    wheelbase: Mapped[Optional[float]]
    bb_drop: Mapped[Optional[float]]
    wheel_size: Mapped[Optional[float]]      # ISO rim bead (622=700c, 584=650b, 559=26")
    seat_tube_length: Mapped[Optional[float]]
    default_crank_length: Mapped[Optional[float]]
    speeds: Mapped[Optional[int]]
    chainring_1: Mapped[Optional[int]]
    chainring_2: Mapped[Optional[int]]        # null → 1x drivetrain
    cassette_low: Mapped[Optional[int]]
    cassette_high: Mapped[Optional[int]]
    fork_length: Mapped[Optional[float]] = None     # axle-to-crown length, mm (real "axle-to-crown" / ~370 road)
    fork_offset: Mapped[Optional[float]] = None     # rake/offset perpendicular to steering axis, mm
    source: Mapped[Optional[str]]             # provenance stamp


# -- added 09-29
class Rider(Base):
    __tablename__ = "riders"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)   # 1:1 with User
    height_mm: Mapped[Optional[float]]            # overall height, mm
    inseam_mm: Mapped[Optional[float]]            # inseam, mm
    arm_length_mm: Mapped[Optional[float]]        # shoulder→wrist, mm
    torso_length_mm: Mapped[Optional[float]]      # sit bone → base of neck, mm
    shoulder_width_mm: Mapped[Optional[float]]    # stored now, used by future fit features
    weight_kg: Mapped[Optional[float]]            # kg (body weight, not bike)


# gallery -- 10-2  (FKs corrected to match plural __tablename__s — "user.id"/"bike.id" crashed mappers)
class Photo(Base):
    """Uploaded image: kind='gallery' attached to a bike, or 'avatar' for the user."""
    __tablename__ = "photos"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)          # was "user.id"
    bike_id: Mapped[Optional[int]] = mapped_column(ForeignKey("bikes.id"), nullable=True)   # was "bike.id"
    kind: Mapped[str] = mapped_column(String, default="gallery")     # gallery | avatar
    stored_name: Mapped[str] = mapped_column(String)                  # uuid4hex.ext — NEVER trust original name
    orig_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)   # for display only
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))