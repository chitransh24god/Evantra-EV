from flask import Flask
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from database import db
from routes.auth import auth_bp
from routes.charger import charger_bp
from routes.booking import booking_bp
from routes.payment import payment_bp

app = Flask(__name__)

app.config["SQLALCHEMY_DATABASE_URI"] = "postgresql+psycopg2://postgres:24#November#2004@localhost:5432/evantra_db"
app.config["JWT_SECRET_KEY"] = "evantra-super-secret-key-2024-production-ready"
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = False
app.config["JWT_SECRET_KEY"] = "evantra-super-secret-key-2024-production-ready"

db.init_app(app)
CORS(app)
jwt = JWTManager(app)

app.register_blueprint(auth_bp,     url_prefix="/api/auth")
app.register_blueprint(charger_bp,  url_prefix="/api/chargers")
app.register_blueprint(booking_bp,  url_prefix="/api/bookings")
app.register_blueprint(payment_bp,  url_prefix="/api/payments")

with app.app_context():
    db.create_all()
    print("✅ Database tables created successfully!")

@app.route("/")
def home():
    return {"message": "Evantra API is running! 🚗⚡", "version": "3.0"}

if __name__ == "__main__":
    app.run(debug=True, port=5000)
