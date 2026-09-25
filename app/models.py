from datetime import datetime, timezone
from sqlalchemy import String, Float, Integer, DateTime, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db import Base


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

    #jon added 09-24
    saddle_height: Mapped[float | None] = mapped_column(Float, nullable=True)   # BB -> top of saddle (rider setting)
    seat_tube_length: Mapped[float | None] = mapped_column(Float, nullable=True) # frame dim (for standover later)
    total_weight: Mapped[float | None] = mapped_column(Float, nullable=True)  # g, overall bike weight
    #

    owner: Mapped["User"] = relationship(back_populates="bikes")
    installed_parts: Mapped[list["BikePart"]] = relationship(
        cascade="all, delete-orphan", back_populates="bike"
    )


class Part(Base):
    """A generic, user-named component. Type-specific dims are nullable so a stem
    doesn't have to carry a crank's fields. This is your requested 'generic part with
    custom names' model — no external catalog needed."""
    __tablename__ = "parts"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String)          # user's custom label, e.g. "my 80mm -17deg stem"
    ptype: Mapped[str] = mapped_column(String)          # stem | bar | spacer_set | seatpost | crankset | saddle ...

    # Dimension fields. Fill only the ones that apply to ptype.
    length: Mapped[float | None] = mapped_column(Float, nullable=True)      # stem length, spacer height each...
    angle: Mapped[float | None] = mapped_column(Float, nullable=True)       # stem rise/drop deg, bar sweep
    setback: Mapped[float | None] = mapped_column(Float, nullable=True)      # seatpost setback
    diameter: Mapped[float | None] = mapped_column(Float, nullable=True)     # clamp / steerer / bar dia
    quantity: Mapped[int] = mapped_column(Integer, default=1)               # spacer count etc.
    extra: Mapped[dict | None] = mapped_column(JSON, nullable=True)          # catch-all for odd dims

    #jon added 09-24
    weight_g: Mapped[float | None] = mapped_column(Float, nullable=True)        # mass of this part

class BikePart(Base):
    """Join table: which part is installed on which bike, where, and how many."""
    __tablename__ = "bike_parts"

    id: Mapped[int] = mapped_column(primary_key=True)
    bike_id: Mapped[int] = mapped_column(ForeignKey("bikes.id"))
    part_id: Mapped[int] = mapped_column(ForeignKey("parts.id"))
    position: Mapped[str | None] = mapped_column(String, nullable=True)  # 'front'/'rear'/'saddle'/...
    quantity: Mapped[int] = mapped_column(Integer, default=1)

    bike: Mapped["Bike"] = relationship(back_populates="installed_parts")
    part: Mapped["Part"] = relationship()