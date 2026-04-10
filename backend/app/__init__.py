import os
from pathlib import Path
from flask import Flask, send_from_directory
from flask_cors import CORS

from .config import Config
from .extensions import cache, db, jwt, mail
from .models import Department, User
from .routes.admin import admin_bp
from .routes.auth import auth_bp
from .routes.common import common_bp
from .routes.doctor import doctor_bp
from .routes.patient import patient_bp
from .tasks import init_celery


FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend" / "src"


def _seed_admin_and_departments():
    admin_username = os.getenv("ADMIN_USERNAME", "admin")
    admin_email = os.getenv("ADMIN_EMAIL", "admin@hms.local")
    admin_password = os.getenv("ADMIN_PASSWORD", "admin123")

    admin = User.query.filter_by(role="admin").first()
    if not admin:
        admin = User(username=admin_username, email=admin_email, role="admin")
        admin.set_password(admin_password)
        db.session.add(admin)

    if Department.query.count() == 0:
        defaults = [
            ("Cardiology", "Heart and blood vessel care"),
            ("Neurology", "Brain and nervous system care"),
            ("Orthopedics", "Bone and joint care"),
            ("Pediatrics", "Child healthcare"),
        ]
        for name, desc in defaults:
            db.session.add(Department(name=name, description=desc))

    db.session.commit()


def create_app():
    """Create and configure the Flask application"""
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(Config)

    # Create instance folder if it doesn't exist
    os.makedirs(app.instance_path, exist_ok=True)

    # Initialize extensions
    CORS(app)
    db.init_app(app)
    jwt.init_app(app)
    cache.init_app(app)
    mail.init_app(app)

    # Register API blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(common_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(doctor_bp)
    app.register_blueprint(patient_bp)

    # Setup database and seed base data
    with app.app_context():
        if app.config.get("AUTO_RESET_DB_ON_STARTUP", True):
            db.drop_all()
        db.create_all()
        _seed_admin_and_departments()

    # Initialize Celery for background jobs
    init_celery(app)

    # Serve frontend (Vue app)
    frontend_dir = Path(__file__).resolve().parents[2] / "frontend" / "src"

    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def serve_frontend(path):
        """Serve Vue frontend files"""
        if path.startswith("api"):
            return {"error": "Not found"}, 404
        
        # Serve static files
        if path:
            file_path = frontend_dir / path
            if file_path.exists() and file_path.is_file():
                return send_from_directory(frontend_dir, path)
        
        # Serve index.html for root and non-file paths
        return send_from_directory(frontend_dir, "index.html")

    return app
