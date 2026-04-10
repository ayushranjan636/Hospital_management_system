from flask import Blueprint, jsonify, request
from flask_jwt_extended import create_access_token, jwt_required

from ..auth_utils import current_user
from ..extensions import db
from ..models import PatientProfile, User
from ..serializers import user_to_dict

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


@auth_bp.post("/register")
def register_patient():
    data = request.get_json() or {}
    required = ["username", "email", "password"]
    if any(not data.get(field) for field in required):
        return jsonify({"error": "username, email and password are required"}), 400

    if User.query.filter((User.username == data["username"]) | (User.email == data["email"])).first():
        return jsonify({"error": "username or email already exists"}), 409

    user = User(username=data["username"], email=data["email"], role="patient")
    user.set_password(data["password"])

    profile = PatientProfile(
        user=user,
        phone=data.get("phone", ""),
        dob=data.get("dob", ""),
        gender=data.get("gender", ""),
        address=data.get("address", ""),
    )
    db.session.add_all([user, profile])
    db.session.commit()

    return jsonify({"message": "Patient registered successfully"}), 201


@auth_bp.post("/login")
def login():
    data = request.get_json() or {}
    username = data.get("username", "")
    password = data.get("password", "")

    user = User.query.filter_by(username=username).first()
    if not user or not user.check_password(password):
        return jsonify({"error": "Invalid credentials"}), 401
    if not user.is_active:
        return jsonify({"error": "Your account is disabled"}), 403

    token = create_access_token(identity=str(user.id), additional_claims={"role": user.role})
    return jsonify({"token": token, "user": user_to_dict(user)})


@auth_bp.get("/me")
@jwt_required()
def me():
    user = current_user()
    if not user:
        return jsonify({"error": "Not found"}), 404
    return jsonify({"user": user_to_dict(user)})
