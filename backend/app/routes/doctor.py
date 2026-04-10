from datetime import date, datetime, timedelta

from flask import Blueprint, jsonify, request

from ..auth_utils import current_user, role_required
from ..extensions import db
from ..models import Appointment, DoctorAvailability, PatientProfile, Treatment
from ..serializers import appointment_to_dict

doctor_bp = Blueprint("doctor", __name__, url_prefix="/api/doctor")


def _doctor_profile_or_404(user):
    return user.doctor_profile


@doctor_bp.get("/dashboard")
@role_required("doctor")
def dashboard():
    user = current_user()
    doctor = _doctor_profile_or_404(user)
    today = date.today()
    week_end = today + timedelta(days=7)

    upcoming = (
        Appointment.query.filter(
            Appointment.doctor_id == doctor.id,
            Appointment.date >= today,
            Appointment.date <= week_end,
        )
        .order_by(Appointment.date.asc(), Appointment.time.asc())
        .all()
    )

    patients = (
        PatientProfile.query.join(Appointment, Appointment.patient_id == PatientProfile.id)
        .filter(Appointment.doctor_id == doctor.id)
        .distinct()
        .all()
    )

    return jsonify(
        {
            "charge_per_slot": doctor.charge_per_slot,
            "wallet_balance": doctor.wallet_balance,
            "appointments": [appointment_to_dict(a) for a in upcoming],
            "patients": [
                {
                    "patient_id": p.id,
                    "name": p.user.username,
                    "email": p.user.email,
                    "phone": p.phone,
                }
                for p in patients
            ],
        }
    )


@doctor_bp.put("/availability")
@role_required("doctor")
def update_availability():
    user = current_user()
    doctor = _doctor_profile_or_404(user)
    data = request.get_json() or {}
    slots = data.get("slots", [])

    for slot in slots:
        try:
            slot_date = datetime.strptime(slot["date"], "%Y-%m-%d").date()
            start_time = datetime.strptime(slot["start_time"], "%H:%M").time()
            end_time = datetime.strptime(slot["end_time"], "%H:%M").time()
        except (KeyError, ValueError):
            continue

        record = DoctorAvailability.query.filter_by(doctor_id=doctor.id, date=slot_date).first()
        if not record:
            record = DoctorAvailability(doctor_id=doctor.id, date=slot_date)
            db.session.add(record)

        record.start_time = start_time
        record.end_time = end_time
        record.is_available = bool(slot.get("is_available", True))

    db.session.commit()
    return jsonify({"message": "Availability updated"})


@doctor_bp.post("/appointments/<int:appointment_id>/complete")
@role_required("doctor")
def complete_appointment(appointment_id):
    user = current_user()
    doctor = _doctor_profile_or_404(user)
    appt = Appointment.query.get_or_404(appointment_id)
    if appt.doctor_id != doctor.id:
        return jsonify({"error": "Forbidden"}), 403

    data = request.get_json() or {}
    appt.status = data.get("status", "Completed")

    treatment = appt.treatment or Treatment(appointment=appt)
    treatment.diagnosis = data.get("diagnosis", "")
    treatment.prescription = data.get("prescription", "")
    treatment.notes = data.get("notes", "")
    treatment.next_visit_suggestion = data.get("next_visit_suggestion", "")

    db.session.add(treatment)
    db.session.commit()
    return jsonify(appointment_to_dict(appt))


@doctor_bp.get("/patients/<int:patient_id>/history")
@role_required("doctor")
def patient_history(patient_id):
    user = current_user()
    doctor = _doctor_profile_or_404(user)

    appointments = (
        Appointment.query.filter_by(doctor_id=doctor.id, patient_id=patient_id)
        .order_by(Appointment.date.desc(), Appointment.time.desc())
        .all()
    )
    return jsonify([appointment_to_dict(a) for a in appointments])

@doctor_bp.put("/profile")
@role_required("doctor")
def update_profile():
    user = current_user()
    doctor = _doctor_profile_or_404(user)
    data = request.get_json() or {}
    
    if "charge_per_slot" in data:
        doctor.charge_per_slot = float(data["charge_per_slot"])
        db.session.commit()
    return jsonify({"message": "Profile updated", "charge_per_slot": doctor.charge_per_slot}), 200
