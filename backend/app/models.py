from datetime import datetime
from werkzeug.security import check_password_hash, generate_password_hash
from .extensions import db


# User model - stores all system users (admin, doctor, patient)
class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # admin, doctor, or patient
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships - link to doctor/patient specific info
    doctor_profile = db.relationship("DoctorProfile", backref="user", uselist=False)
    patient_profile = db.relationship("PatientProfile", backref="user", uselist=False)

    def set_password(self, password):
        """Hash and store password"""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Verify password"""
        return check_password_hash(self.password_hash, password)


# Department model - medical specializations
class Department(db.Model):
    __tablename__ = "departments"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    description = db.Column(db.Text, default="")

    doctors = db.relationship("DoctorProfile", backref="department", lazy=True)


# Doctor-specific information
class DoctorProfile(db.Model):
    __tablename__ = "doctor_profiles"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), unique=True, nullable=False)
    name = db.Column(db.String(120), default="")
    department_id = db.Column(db.Integer, db.ForeignKey("departments.id"), nullable=False)
    specialization = db.Column(db.String(120), nullable=False)
    bio = db.Column(db.Text, default="")
    charge_per_slot = db.Column(db.Float, default=150.0)
    wallet_balance = db.Column(db.Float, default=0.0)
    is_active = db.Column(db.Boolean, default=True)

    # Relationships
    appointments = db.relationship("Appointment", backref="doctor", lazy=True)
    availabilities = db.relationship("DoctorAvailability", backref="doctor", lazy=True, cascade="all, delete-orphan")


# Patient-specific information
class PatientProfile(db.Model):
    __tablename__ = "patient_profiles"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), unique=True, nullable=False)
    name = db.Column(db.String(120), default="")
    phone = db.Column(db.String(20), default="")
    dob = db.Column(db.String(20), default="")
    gender = db.Column(db.String(20), default="")
    address = db.Column(db.String(255), default="")

    appointments = db.relationship("Appointment", backref="patient", lazy=True)


# Doctor availability slots for appointment booking
class DoctorAvailability(db.Model):
    __tablename__ = "doctor_availabilities"

    id = db.Column(db.Integer, primary_key=True)
    doctor_id = db.Column(db.Integer, db.ForeignKey("doctor_profiles.id"), nullable=False)
    date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    is_available = db.Column(db.Boolean, default=True)


# Appointment bookings between patients and doctors
class Appointment(db.Model):
    __tablename__ = "appointments"
    __table_args__ = (
        db.UniqueConstraint("doctor_id", "date", "time", name="unique_doctor_slot"),
    )

    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey("patient_profiles.id"), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey("doctor_profiles.id"), nullable=False)
    date = db.Column(db.Date, nullable=False)
    time = db.Column(db.Time, nullable=False)
    status = db.Column(db.String(20), default="Booked")  # Booked, Completed, Cancelled
    reason = db.Column(db.String(255), default="")
    patient_report = db.Column(db.Text, default="")
    paid_amount = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    treatment = db.relationship("Treatment", backref="appointment", uselist=False, cascade="all, delete-orphan")


# Treatment information for completed appointments
class Treatment(db.Model):
    __tablename__ = "treatments"

    id = db.Column(db.Integer, primary_key=True)
    appointment_id = db.Column(db.Integer, db.ForeignKey("appointments.id"), nullable=False, unique=True)
    diagnosis = db.Column(db.String(255), default="")
    prescription = db.Column(db.String(255), default="")
    notes = db.Column(db.Text, default="")
    next_visit_suggestion = db.Column(db.String(100), default="")
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
