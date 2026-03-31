from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from database import db, Charger, User
import math

charger_bp = Blueprint("charger", __name__)


def haversine(lat1, lon1, lat2, lon2):
    """Calculate distance in km between two GPS coordinates."""
    R = 6371
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = math.sin(d_lat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(d_lon/2)**2
    return R * 2 * math.asin(math.sqrt(a))


# ──────────────────────────────────────────────────────────────
#  GET /api/chargers?lat=23.02&lng=72.57&radius=10
#  Returns all chargers within radius km of given location
# ──────────────────────────────────────────────────────────────
@charger_bp.route("/", methods=["GET"])
def get_chargers():
    lat    = request.args.get("lat", type=float)
    lng    = request.args.get("lng", type=float)
    radius = request.args.get("radius", default=10, type=float)

    chargers = Charger.query.filter_by(is_available=True).all()

    result = []
    for c in chargers:
        distance = None
        if lat and lng:
            distance = haversine(lat, lng, c.latitude, c.longitude)
            if distance > radius:
                continue
        d = c.to_dict()
        d["distance_km"] = round(distance, 2) if distance else None
        d["owner_name"]  = c.owner.name if c.owner else "Unknown"
        result.append(d)

    if lat and lng:
        result.sort(key=lambda x: x["distance_km"] or 999)

    return jsonify({"chargers": result, "count": len(result)}), 200


# ──────────────────────────────────────────────────────────────
#  GET /api/chargers/<id>  — single charger detail
# ──────────────────────────────────────────────────────────────
@charger_bp.route("/<int:charger_id>", methods=["GET"])
def get_charger(charger_id):
    c = Charger.query.get_or_404(charger_id)
    d = c.to_dict()
    d["owner_name"] = c.owner.name if c.owner else "Unknown"
    return jsonify({"charger": d}), 200


# ──────────────────────────────────────────────────────────────
#  POST /api/chargers/  — host lists a new charger (needs login)
# ──────────────────────────────────────────────────────────────
@charger_bp.route("/", methods=["POST"])
@jwt_required()
def add_charger():
    user_id = get_jwt_identity()
    user    = User.query.get(user_id)

    if not user or user.role not in ["host", "admin"]:
        return jsonify({"error": "Only charger hosts can list chargers"}), 403

    data = request.get_json()
    required = ["title", "address", "latitude", "longitude", "price_per_unit"]
    for field in required:
        if data.get(field) is None:
            return jsonify({"error": f"'{field}' is required"}), 400

    charger = Charger(
        owner_id      = int(user_id),
        title         = data["title"],
        description   = data.get("description"),
        address       = data["address"],
        latitude      = float(data["latitude"]),
        longitude     = float(data["longitude"]),
        charger_type  = data.get("charger_type", "AC"),
        power_kw      = data.get("power_kw"),
        price_per_unit= float(data["price_per_unit"]),
        is_free       = data.get("is_free", False),
        is_available  = True
    )
    db.session.add(charger)
    db.session.commit()

    return jsonify({
        "message": "Charger listed successfully! ⚡",
        "charger": charger.to_dict()
    }), 201


# ──────────────────────────────────────────────────────────────
#  PUT /api/chargers/<id>  — host updates their charger
# ──────────────────────────────────────────────────────────────
@charger_bp.route("/<int:charger_id>", methods=["PUT"])
@jwt_required()
def update_charger(charger_id):
    user_id = get_jwt_identity()
    charger = Charger.query.get_or_404(charger_id)

    if str(charger.owner_id) != str(user_id):
        return jsonify({"error": "You can only edit your own chargers"}), 403

    data = request.get_json()
    for field in ["title", "description", "address", "charger_type", "power_kw", "price_per_unit", "is_free", "is_available"]:
        if field in data:
            setattr(charger, field, data[field])

    db.session.commit()
    return jsonify({"message": "Charger updated!", "charger": charger.to_dict()}), 200


# ──────────────────────────────────────────────────────────────
#  DELETE /api/chargers/<id>  — host removes their charger
# ──────────────────────────────────────────────────────────────
@charger_bp.route("/<int:charger_id>", methods=["DELETE"])
@jwt_required()
def delete_charger(charger_id):
    user_id = get_jwt_identity()
    charger = Charger.query.get_or_404(charger_id)

    if str(charger.owner_id) != str(user_id):
        return jsonify({"error": "You can only delete your own chargers"}), 403

    db.session.delete(charger)
    db.session.commit()
    return jsonify({"message": "Charger removed"}), 200
