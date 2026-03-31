from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from database import db, Payment, Booking
import hmac, hashlib, os

payment_bp = Blueprint("payment", __name__)

RAZORPAY_KEY_ID     = os.getenv("RAZORPAY_KEY_ID",     "rzp_test_SXPzoDYuSC6B4R")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET",  "ZTD3TUV6Fet7aQnPemFX9iZX")


# ──────────────────────────────────────────────────────────────
#  POST /api/payments/create-order
#  Creates a Razorpay order for a booking
# ──────────────────────────────────────────────────────────────
@payment_bp.route("/create-order", methods=["POST"])
@jwt_required()
def create_order():
    user_id = get_jwt_identity()
    data    = request.get_json()

    booking_id = data.get("booking_id")
    if not booking_id:
        return jsonify({"error": "booking_id is required"}), 400

    booking = Booking.query.get(booking_id)
    if not booking:
        return jsonify({"error": "Booking not found"}), 404

    if str(booking.driver_id) != str(user_id):
        return jsonify({"error": "Not your booking"}), 403

    # Check if already paid
    if booking.payment and booking.payment.status == "paid":
        return jsonify({"error": "This booking is already paid"}), 400

    amount_paise = int(booking.total_amount * 100)  # Razorpay uses paise

    try:
        import razorpay
        client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))
        order  = client.order.create({
            "amount":   amount_paise,
            "currency": "INR",
            "receipt":  f"booking_{booking_id}",
            "notes":    {"booking_id": str(booking_id)}
        })

        # Save payment record
        payment = Payment(
            booking_id       = booking_id,
            amount           = booking.total_amount,
            currency         = "INR",
            razorpay_order_id= order["id"],
            status           = "pending"
        )
        db.session.add(payment)
        db.session.commit()

        return jsonify({
            "order_id":   order["id"],
            "amount":     amount_paise,
            "currency":   "INR",
            "key_id":     RAZORPAY_KEY_ID,
            "booking_id": booking_id
        }), 200

    except ImportError:
        # Razorpay not installed — return mock order for testing
        import uuid
        mock_order_id = "order_" + str(uuid.uuid4().hex[:16])

        payment = Payment(
            booking_id       = booking_id,
            amount           = booking.total_amount,
            currency         = "INR",
            razorpay_order_id= mock_order_id,
            status           = "pending"
        )
        db.session.add(payment)
        db.session.commit()

        return jsonify({
            "order_id":   mock_order_id,
            "amount":     amount_paise,
            "currency":   "INR",
            "key_id":     RAZORPAY_KEY_ID,
            "booking_id": booking_id,
            "mock":       True   # tells frontend this is test mode
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ──────────────────────────────────────────────────────────────
#  POST /api/payments/verify
#  Verifies Razorpay payment signature and marks as paid
# ──────────────────────────────────────────────────────────────
@payment_bp.route("/verify", methods=["POST"])
@jwt_required()
def verify_payment():
    data = request.get_json()

    razorpay_order_id   = data.get("razorpay_order_id")
    razorpay_payment_id = data.get("razorpay_payment_id")
    razorpay_signature  = data.get("razorpay_signature")
    booking_id          = data.get("booking_id")
    mock                = data.get("mock", False)

    payment = Payment.query.filter_by(razorpay_order_id=razorpay_order_id).first()
    if not payment:
        return jsonify({"error": "Payment record not found"}), 404

    if mock:
        # Test mode — skip signature verification
        payment.status           = "paid"
        payment.payment_method   = "mock_upi"
        booking = Booking.query.get(booking_id)
        if booking:
            booking.status = "confirmed"
        db.session.commit()
        return jsonify({"message": "Payment successful (test mode)! ⚡", "status": "paid"}), 200

    # Real Razorpay signature verification
    msg       = f"{razorpay_order_id}|{razorpay_payment_id}"
    signature = hmac.new(
        RAZORPAY_KEY_SECRET.encode(),
        msg.encode(),
        hashlib.sha256
    ).hexdigest()

    if signature != razorpay_signature:
        payment.status = "failed"
        db.session.commit()
        return jsonify({"error": "Payment verification failed"}), 400

    payment.status           = "paid"
    payment.payment_method   = "razorpay"
    booking = Booking.query.get(booking_id)
    if booking:
        booking.status = "confirmed"
    db.session.commit()

    return jsonify({"message": "Payment verified successfully! ⚡", "status": "paid"}), 200


# ──────────────────────────────────────────────────────────────
#  GET /api/payments/history
#  Returns payment history for the logged-in user
# ──────────────────────────────────────────────────────────────
@payment_bp.route("/history", methods=["GET"])
@jwt_required()
def payment_history():
    user_id  = get_jwt_identity()
    bookings = Booking.query.filter_by(driver_id=int(user_id)).all()

    result = []
    for b in bookings:
        if b.payment:
            result.append({
                "booking_id":     b.id,
                "charger_title":  b.charger.title if b.charger else "N/A",
                "amount":         b.payment.amount,
                "currency":       b.payment.currency,
                "status":         b.payment.status,
                "payment_method": b.payment.payment_method,
                "created_at":     b.payment.created_at.isoformat()
            })

    return jsonify({"payments": result}), 200
