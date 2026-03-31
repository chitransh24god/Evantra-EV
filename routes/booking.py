from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from database import db, Booking, Charger, User
from datetime import datetime

booking_bp = Blueprint("booking", __name__)


# ──────────────────────────────────────────────────────────────
#  POST /api/bookings/  — driver books a charger slot
# ──────────────────────────────────────────────────────────────
@booking_bp.route("/", methods=["POST"])
@jwt_required()
def create_booking():
    user_id = get_jwt_identity()
    data    = request.get_json()

    required = ["charger_id", "start_time", "end_time"]
    for field in required:
        if not data.get(field):
            return jsonify({"error": f"'{field}' is required"}), 400

    charger = Charger.query.get(data["charger_id"])
    if not charger:
        return jsonify({"error": "Charger not found"}), 404
    if not charger.is_available:
        return jsonify({"error": "This charger is not available"}), 400

    try:
        start = datetime.fromisoformat(data["start_time"])
        end   = datetime.fromisoformat(data["end_time"])
    except ValueError:
        return jsonify({"error": "Invalid date format. Use: YYYY-MM-DDTHH:MM:SS"}), 400

    if end <= start:
        return jsonify({"error": "End time must be after start time"}), 400

    # Check for overlapping bookings
    overlap = Booking.query.filter(
        Booking.charger_id == charger.id,
        Booking.status.in_(["pending", "confirmed"]),
        Booking.start_time < end,
        Booking.end_time   > start
    ).first()

    if overlap:
        return jsonify({"error": "This slot is already booked. Please choose another time."}), 409

    # Calculate total amount
    hours        = (end - start).total_seconds() / 3600
    total_amount = round(hours * charger.price_per_unit, 2) if not charger.is_free else 0.0

    booking = Booking(
        driver_id    = int(user_id),
        charger_id   = charger.id,
        start_time   = start,
        end_time     = end,
        total_amount = total_amount,
        status       = "confirmed"
    )
    db.session.add(booking)
    db.session.commit()

    return jsonify({
        "message": "Booking confirmed! ⚡",
        "booking": booking.to_dict(),
        "charger": charger.to_dict(),
        "total_amount": total_amount
    }), 201


# ──────────────────────────────────────────────────────────────
#  GET /api/bookings/my  — driver sees their bookings
# ──────────────────────────────────────────────────────────────
@booking_bp.route("/my", methods=["GET"])
@jwt_required()
def my_bookings():
    user_id  = get_jwt_identity()
    bookings = Booking.query.filter_by(driver_id=int(user_id)).order_by(Booking.created_at.desc()).all()

    result = []
    for b in bookings:
        d = b.to_dict()
        d["charger_title"]   = b.charger.title   if b.charger else "N/A"
        d["charger_address"] = b.charger.address if b.charger else "N/A"
        result.append(d)

    return jsonify({"bookings": result}), 200


# ──────────────────────────────────────────────────────────────
#  GET /api/bookings/host  — host sees bookings on their chargers
# ──────────────────────────────────────────────────────────────
@booking_bp.route("/host", methods=["GET"])
@jwt_required()
def host_bookings():
    user_id  = get_jwt_identity()
    chargers = Charger.query.filter_by(owner_id=int(user_id)).all()
    charger_ids = [c.id for c in chargers]

    bookings = Booking.query.filter(
        Booking.charger_id.in_(charger_ids)
    ).order_by(Booking.created_at.desc()).all()

    result = []
    for b in bookings:
        d = b.to_dict()
        d["driver_name"]     = b.driver.name    if b.driver  else "N/A"
        d["charger_title"]   = b.charger.title  if b.charger else "N/A"
        result.append(d)

    return jsonify({"bookings": result}), 200


# ──────────────────────────────────────────────────────────────
#  PUT /api/bookings/<id>/cancel  — cancel a booking
# ──────────────────────────────────────────────────────────────
@booking_bp.route("/<int:booking_id>/cancel", methods=["PUT"])
@jwt_required()
def cancel_booking(booking_id):
    user_id = get_jwt_identity()
    booking = Booking.query.get_or_404(booking_id)

    if str(booking.driver_id) != str(user_id):
        return jsonify({"error": "You can only cancel your own bookings"}), 403

    if booking.status == "completed":
        return jsonify({"error": "Cannot cancel a completed booking"}), 400

    booking.status = "cancelled"
    db.session.commit()
    return jsonify({"message": "Booking cancelled", "booking": booking.to_dict()}), 200
