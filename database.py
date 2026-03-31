from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

# ══════════════════════════════════════════════════════════════
#  USER TABLE  — stores both EV drivers and charger hosts
# ══════════════════════════════════════════════════════════════
class User(db.Model):
    __tablename__ = "users"

    id            = db.Column(db.Integer, primary_key=True)
    name          = db.Column(db.String(100), nullable=False)
    email         = db.Column(db.String(150), unique=True, nullable=False)
    phone         = db.Column(db.String(15),  unique=True, nullable=True)
    password_hash = db.Column(db.String(256), nullable=False)
    role          = db.Column(db.String(20),  nullable=False, default="driver")
    # role options:  "driver"  |  "host"  |  "admin"

    is_verified   = db.Column(db.Boolean, default=False)
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at    = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships (will be used in Phase 2)
    chargers      = db.relationship("Charger",  backref="owner",   lazy=True)
    bookings      = db.relationship("Booking",  backref="driver",  lazy=True)

    def to_dict(self):
        """Return safe user data (never return password!)"""
        return {
            "id":          self.id,
            "name":        self.name,
            "email":       self.email,
            "phone":       self.phone,
            "role":        self.role,
            "is_verified": self.is_verified,
            "created_at":  self.created_at.isoformat()
        }

    def __repr__(self):
        return f"<User {self.email} [{self.role}]>"


# ══════════════════════════════════════════════════════════════
#  CHARGER TABLE  — a charger listed by a host
# ══════════════════════════════════════════════════════════════
class Charger(db.Model):
    __tablename__ = "chargers"

    id            = db.Column(db.Integer, primary_key=True)
    owner_id      = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    title         = db.Column(db.String(100), nullable=False)
    description   = db.Column(db.Text, nullable=True)
    address       = db.Column(db.String(300), nullable=False)
    latitude      = db.Column(db.Float, nullable=False)
    longitude     = db.Column(db.Float, nullable=False)

    charger_type  = db.Column(db.String(20), default="AC")  # AC | DC | Fast
    power_kw      = db.Column(db.Float, nullable=True)       # e.g. 7.2 kW
    price_per_unit= db.Column(db.Float, nullable=False, default=0.0)
    is_free       = db.Column(db.Boolean, default=False)
    is_available  = db.Column(db.Boolean, default=True)

    created_at    = db.Column(db.DateTime, default=datetime.utcnow)

    bookings      = db.relationship("Booking", backref="charger", lazy=True)

    def to_dict(self):
        return {
            "id":             self.id,
            "owner_id":       self.owner_id,
            "title":          self.title,
            "address":        self.address,
            "latitude":       self.latitude,
            "longitude":      self.longitude,
            "charger_type":   self.charger_type,
            "power_kw":       self.power_kw,
            "price_per_unit": self.price_per_unit,
            "is_free":        self.is_free,
            "is_available":   self.is_available,
        }


# ══════════════════════════════════════════════════════════════
#  BOOKING TABLE  — a driver books a charger slot
# ══════════════════════════════════════════════════════════════
class Booking(db.Model):
    __tablename__ = "bookings"

    id            = db.Column(db.Integer, primary_key=True)
    driver_id     = db.Column(db.Integer, db.ForeignKey("users.id"),    nullable=False)
    charger_id    = db.Column(db.Integer, db.ForeignKey("chargers.id"), nullable=False)

    start_time    = db.Column(db.DateTime, nullable=False)
    end_time      = db.Column(db.DateTime, nullable=False)
    total_amount  = db.Column(db.Float, default=0.0)
    status        = db.Column(db.String(20), default="pending")
    # status options: pending | confirmed | completed | cancelled

    created_at    = db.Column(db.DateTime, default=datetime.utcnow)

    payment       = db.relationship("Payment", backref="booking", uselist=False, lazy=True)

    def to_dict(self):
        return {
            "id":           self.id,
            "driver_id":    self.driver_id,
            "charger_id":   self.charger_id,
            "start_time":   self.start_time.isoformat(),
            "end_time":     self.end_time.isoformat(),
            "total_amount": self.total_amount,
            "status":       self.status,
        }


# ══════════════════════════════════════════════════════════════
#  PAYMENT TABLE  — payment record for each booking
# ══════════════════════════════════════════════════════════════
class Payment(db.Model):
    __tablename__ = "payments"

    id               = db.Column(db.Integer, primary_key=True)
    booking_id       = db.Column(db.Integer, db.ForeignKey("bookings.id"), nullable=False)

    amount           = db.Column(db.Float, nullable=False)
    currency         = db.Column(db.String(5), default="INR")
    payment_method   = db.Column(db.String(30), nullable=True)   # UPI | card | wallet
    razorpay_order_id= db.Column(db.String(100), nullable=True)
    status           = db.Column(db.String(20), default="pending")
    # status options: pending | paid | failed | refunded

    created_at       = db.Column(db.DateTime, default=datetime.utcnow)


# ══════════════════════════════════════════════════════════════
#  REVIEW TABLE  — rating after a booking session
# ══════════════════════════════════════════════════════════════
class Review(db.Model):
    __tablename__ = "reviews"

    id          = db.Column(db.Integer, primary_key=True)
    charger_id  = db.Column(db.Integer, db.ForeignKey("chargers.id"), nullable=False)
    reviewer_id = db.Column(db.Integer, db.ForeignKey("users.id"),    nullable=False)

    rating      = db.Column(db.Integer, nullable=False)   # 1–5
    comment     = db.Column(db.Text, nullable=True)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)
