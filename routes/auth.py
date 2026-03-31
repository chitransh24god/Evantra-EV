from flask import Blueprint, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from database import db, User

auth_bp = Blueprint("auth", __name__)


# ──────────────────────────────────────────────────────────────
#  POST /api/auth/register
#  Creates a new user account (driver or host)
# ──────────────────────────────────────────────────────────────
@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json()

    # 1. Validate required fields
    required = ["name", "email", "password", "role"]
    for field in required:
        if not data.get(field):
            return jsonify({"error": f"'{field}' is required"}), 400

    # 2. Check if email already exists
    if User.query.filter_by(email=data["email"]).first():
        return jsonify({"error": "Email already registered. Please login."}), 409

    # 3. Validate role
    if data["role"] not in ["driver", "host"]:
        return jsonify({"error": "Role must be 'driver' or 'host'"}), 400

    # 4. Hash password (never store plain text!)
    hashed_password = generate_password_hash(data["password"])

    # 5. Create and save user
    new_user = User(
        name=data["name"],
        email=data["email"],
        phone=data.get("phone") or None,        # optional
        password_hash=hashed_password,
        role=data["role"]
    )
    db.session.add(new_user)
    db.session.commit()

    # 6. Generate JWT token so user is logged in immediately after register
    access_token = create_access_token(identity=str(new_user.id))

    return jsonify({
        "message": "Account created successfully! Welcome to Evantra ⚡",
        "token":   access_token,
        "user":    new_user.to_dict()
    }), 201


# ──────────────────────────────────────────────────────────────
#  POST /api/auth/login
#  Returns a JWT token if credentials are valid
# ──────────────────────────────────────────────────────────────
@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json()

    # 1. Validate fields
    if not data.get("email") or not data.get("password"):
        return jsonify({"error": "Email and password are required"}), 400

    # 2. Find user by email
    user = User.query.filter_by(email=data["email"]).first()
    if not user:
        return jsonify({"error": "No account found with this email"}), 404

    # 3. Check password
    if not check_password_hash(user.password_hash, data["password"]):
        return jsonify({"error": "Incorrect password"}), 401

    # 4. Generate token
    access_token = create_access_token(identity=str(user.id))

    return jsonify({
        "message": f"Welcome back, {user.name}! ⚡",
        "token":   access_token,
        "user":    user.to_dict()
    }), 200


# ──────────────────────────────────────────────────────────────
#  GET /api/auth/me
#  Returns logged-in user's profile (requires token)
# ──────────────────────────────────────────────────────────────
@auth_bp.route("/me", methods=["GET"])
@jwt_required()
def get_me():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
    return jsonify({"user": user.to_dict()}), 200


# ──────────────────────────────────────────────────────────────
#  POST /api/auth/change-password
#  Allows logged-in user to change password
# ──────────────────────────────────────────────────────────────
@auth_bp.route("/change-password", methods=["POST"])
@jwt_required()
def change_password():
    data    = request.get_json()
    user_id = get_jwt_identity()
    user    = User.query.get(user_id)

    if not check_password_hash(user.password_hash, data.get("old_password", "")):
        return jsonify({"error": "Current password is incorrect"}), 401

    user.password_hash = generate_password_hash(data["new_password"])
    db.session.commit()
    return jsonify({"message": "Password updated successfully"}), 200
