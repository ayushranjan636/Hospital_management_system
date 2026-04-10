from flask import Blueprint, jsonify

from ..extensions import cache
from ..models import Department

common_bp = Blueprint("common", __name__, url_prefix="/api")


@common_bp.get("/health")
def health():
    return jsonify({"status": "ok"})


@common_bp.get("/test-mail")
def test_mail():
    from ..extensions import mail
    from flask_mail import Message
    try:
        msg = Message(
            subject="Test Mail from HMS",
            recipients=["ayushranjan535@gmail.com"],
            body="If you are receiving this, Flask-Mail and your App Password are fully working!"
        )
        mail.send(msg)
        return jsonify({"status": "success", "message": "Test email sent successfully to ayushranjan535@gmail.com"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@common_bp.get("/departments")
@cache.cached(timeout=180)
def departments():
    rows = Department.query.order_by(Department.name.asc()).all()
    return jsonify(
        [
            {
                "id": d.id,
                "name": d.name,
                "description": d.description,
                "doctors_registered": len(d.doctors),
            }
            for d in rows
        ]
    )
