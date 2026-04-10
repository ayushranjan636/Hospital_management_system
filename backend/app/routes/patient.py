from datetime import date, datetime, timedelta
import os
from celery.result import AsyncResult

from flask import Blueprint, jsonify, request, send_file
from sqlalchemy import or_

from ..auth_utils import current_user, role_required
from ..extensions import cache, db
from ..models import Appointment, DoctorAvailability, DoctorProfile, User
from ..serializers import appointment_to_dict, doctor_to_dict

patient_bp = Blueprint("patient", __name__, url_prefix="/api/patient")


def _patient_profile_or_404(user):
    return user.patient_profile


@patient_bp.get("/dashboard")
@role_required("patient")
def dashboard():
    user = current_user()
    patient = _patient_profile_or_404(user)
    today = date.today()

    upcoming = (
        Appointment.query.filter(
            Appointment.patient_id == patient.id,
            Appointment.date >= today,
            Appointment.status != "Completed"
        )
        .order_by(Appointment.date.asc(), Appointment.time.asc())
        .all()
    )
    history = (
        Appointment.query.filter(
            Appointment.patient_id == patient.id,
            or_(Appointment.date < today, Appointment.status == "Completed")
        )
        .order_by(Appointment.date.desc(), Appointment.time.desc())
        .all()
    )

    return jsonify(
        {
            "upcoming": [appointment_to_dict(a) for a in upcoming],
            "history": [appointment_to_dict(a) for a in history],
        }
    )


@patient_bp.get("/doctors")
@role_required("patient")
@cache.cached(timeout=90, query_string=True)
def search_doctors():
    specialization = request.args.get("specialization", "")
    query = DoctorProfile.query.join(User, DoctorProfile.user_id == User.id).filter(User.is_active.is_(True))
    if specialization:
        query = query.filter(DoctorProfile.specialization.ilike(f"%{specialization}%"))

    doctors = query.order_by(DoctorProfile.id.desc()).all()
    return jsonify([doctor_to_dict(d) for d in doctors])


@patient_bp.post("/appointments")
@role_required("patient")
def book_appointment():
    user = current_user()
    patient = _patient_profile_or_404(user)
    data = request.get_json() or {}

    try:
        slot_date = datetime.strptime(data["date"], "%Y-%m-%d").date()
        slot_time = datetime.strptime(data["time"], "%H:%M").time()
    except (KeyError, ValueError):
        return jsonify({"error": "Invalid date or time"}), 400

    doctor_id = data.get("doctor_id")
    doctor = DoctorProfile.query.get(doctor_id)
    if not doctor or not doctor.user.is_active:
        return jsonify({"error": "Doctor unavailable"}), 404

    # Check if slot is already booked
    if Appointment.query.filter_by(doctor_id=doctor_id, date=slot_date, time=slot_time).first():
        return jsonify({"error": "Slot already booked"}), 409

    appt = Appointment(
        patient_id=patient.id,
        doctor_id=doctor_id,
        date=slot_date,
        time=slot_time,
        status="Booked",
        reason=data.get("reason", ""),
        patient_report=data.get("patient_report", ""),
        paid_amount=doctor.charge_per_slot,
    )
    # Add to doctor wallet
    doctor.wallet_balance += doctor.charge_per_slot
    
    db.session.add(appt)
    db.session.commit()
    
    return jsonify({
        **appointment_to_dict(appt),
        "transaction_id": f"TXN-{appt.id}-{int(datetime.utcnow().timestamp())}",
        "paid_amount": doctor.charge_per_slot
    }), 201


@patient_bp.put("/appointments/<int:appointment_id>/reschedule")
@role_required("patient")
def reschedule_appointment(appointment_id):
    user = current_user()
    patient = _patient_profile_or_404(user)
    appt = Appointment.query.get_or_404(appointment_id)
    if appt.patient_id != patient.id:
        return jsonify({"error": "Forbidden"}), 403
    if appt.status != "Booked":
        return jsonify({"error": "Only booked appointments can be rescheduled"}), 400

    data = request.get_json() or {}
    try:
        slot_date = datetime.strptime(data["date"], "%Y-%m-%d").date()
        slot_time = datetime.strptime(data["time"], "%H:%M").time()
    except (KeyError, ValueError):
        return jsonify({"error": "Invalid date or time"}), 400

    if Appointment.query.filter_by(doctor_id=appt.doctor_id, date=slot_date, time=slot_time).first():
        return jsonify({"error": "Slot already booked"}), 409

    appt.date = slot_date
    appt.time = slot_time
    db.session.commit()
    return jsonify(appointment_to_dict(appt))


@patient_bp.delete("/appointments/<int:appointment_id>")
@role_required("patient")
def cancel_appointment(appointment_id):
    user = current_user()
    patient = _patient_profile_or_404(user)
    appt = Appointment.query.get_or_404(appointment_id)
    if appt.patient_id != patient.id:
        return jsonify({"error": "Forbidden"}), 403

    appt.status = "Cancelled"
    db.session.commit()
    return jsonify({"message": "Appointment cancelled"})


@patient_bp.get("/history")
@role_required("patient")
def history():
    user = current_user()
    patient = _patient_profile_or_404(user)
    rows = (
        Appointment.query.filter_by(patient_id=patient.id)
        .order_by(Appointment.date.desc(), Appointment.time.desc())
        .all()
    )
    return jsonify([appointment_to_dict(a) for a in rows])



@patient_bp.get("/profile")
@role_required("patient")
def get_profile():
    user = current_user()
    patient = _patient_profile_or_404(user)
    return jsonify({
        "id": patient.id,
        "username": user.username,
        "email": user.email,
        "phone": patient.phone or "",
        "dob": patient.dob or "",
        "gender": patient.gender or "",
        "address": patient.address or "",
    })


@patient_bp.put("/profile")
@role_required("patient")
def update_profile():
    user = current_user()
    patient = _patient_profile_or_404(user)
    data = request.get_json() or {}
    
    if "phone" in data:
        patient.phone = data["phone"]
    if "dob" in data:
        patient.dob = data["dob"]
    if "gender" in data:
        patient.gender = data["gender"]
    if "address" in data:
        patient.address = data["address"]
    if "email" in data:
        user.email = data["email"]
    
    db.session.commit()
    return jsonify({"message": "Profile updated"})


@patient_bp.get("/doctors/<int:doctor_id>/availability")
@role_required("patient")
def doctor_availability(doctor_id):
    doctor = DoctorProfile.query.get_or_404(doctor_id)
    today = date.today()
    week_end = today + timedelta(days=7)
    
    availabilities = DoctorAvailability.query.filter(
        DoctorAvailability.doctor_id == doctor_id,
        DoctorAvailability.date >= today,
        DoctorAvailability.date <= week_end,
        DoctorAvailability.is_available.is_(True),
    ).order_by(DoctorAvailability.date.asc()).all()
    
    result = []
    for avail in availabilities:
        # Check for existing appointments at this time
        booked = Appointment.query.filter_by(
            doctor_id=doctor_id,
            date=avail.date,
        ).all()
        booked_times = {(b.date, b.time) for b in booked}
        
        result.append({
            "date": avail.date.isoformat(),
            "start_time": avail.start_time.isoformat() if avail.start_time else "09:00",
            "end_time": avail.end_time.isoformat() if avail.end_time else "17:00",
            "booked_times": [t.isoformat() for d, t in booked_times if d == avail.date],
        })
    
    return jsonify(result)


@patient_bp.get("/doctors/<int:doctor_id>/details")
@role_required("patient")
def doctor_details(doctor_id):
    doctor = DoctorProfile.query.get_or_404(doctor_id)
    completed_appts = Appointment.query.filter_by(
        doctor_id=doctor_id,
        status="Completed"
    ).count()
    doctor_display_name = (doctor.name or doctor.user.username or "").replace("_", " ").strip()
    lowered = doctor_display_name.lower()
    if lowered.startswith("dr. "):
        doctor_display_name = doctor_display_name[4:].strip()
    elif lowered.startswith("dr "):
        doctor_display_name = doctor_display_name[3:].strip()
    doctor_display_name = doctor_display_name.title() if doctor_display_name else doctor.user.username
    
    return jsonify({
        "id": doctor.id,
        "name": doctor_display_name,
        "email": doctor.user.email,
        "specialization": doctor.specialization,
        "department": doctor.department.name,
        "bio": doctor.bio or "",
        "completed_appointments": completed_appts,
    })


@patient_bp.post("/export")
@role_required("patient")
def export_treatments():
    """Trigger CSV export of patient's treatment history"""
    import os, csv
    from ..config import Config
    
    user = current_user()
    patient = _patient_profile_or_404(user)
    
    export_dir = os.path.join(Config.INSTANCE_DIR, "exports")
    os.makedirs(export_dir, exist_ok=True)
    
    filepath = os.path.join(export_dir, f"patient_{patient.id}_treatments.csv")
    
    # Get all appointments for patient
    appointments = Appointment.query.filter_by(patient_id=patient.id).all()
    
    # Write CSV
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Date", "Time", "Doctor", "Status", "Diagnosis", "Prescription", "Notes"])
        
        for appt in appointments:
            treatment = appt.treatment if appt.treatment else None
            doctor_display_name = (appt.doctor.name or appt.doctor.user.username or "").replace("_", " ").strip()
            lowered = doctor_display_name.lower()
            if lowered.startswith("dr. "):
                doctor_display_name = doctor_display_name[4:].strip()
            elif lowered.startswith("dr "):
                doctor_display_name = doctor_display_name[3:].strip()
            doctor_display_name = doctor_display_name.title() if doctor_display_name else appt.doctor.user.username
            writer.writerow([
                appt.date,
                appt.time.strftime("%H:%M"),
                doctor_display_name,
                appt.status,
                treatment.diagnosis if treatment else "",
                treatment.prescription if treatment else "",
                treatment.notes if treatment else "",
            ])
    
    return jsonify({
        "task_id": "sync_" + str(patient.id),
        "status": "processing",
        "message": "Your treatment history export is being prepared"
    })


@patient_bp.get("/export/<task_id>")
@role_required("patient")
def download_export(task_id):
    """Download exported CSV file"""
    import os
    from ..config import Config
    
    if task_id.startswith("sync_"):
        patient_id = task_id.split("_")[1]
        export_dir = os.path.join(Config.INSTANCE_DIR, "exports")
        filepath = os.path.join(export_dir, f"patient_{patient_id}_treatments.csv")
        if os.path.exists(filepath):
            filename = os.path.basename(filepath)
            return send_file(
                filepath,
                mimetype='text/csv',
                as_attachment=True,
                download_name=filename
            )
        return jsonify({"status": "error", "message": "File not found"}), 404
        
    result = AsyncResult(task_id)
    
    if result.state == 'PENDING':
        return jsonify({
            "status": "processing",
            "message": "Your export is still being prepared"
        }), 202
    
    if result.state == 'FAILURE':
        return jsonify({
            "status": "error",
            "message": "Export failed"
        }), 500
    
    if result.state == 'SUCCESS':
        filepath = result.result
        if filepath and os.path.exists(filepath):
            filename = os.path.basename(filepath)
            return send_file(
                filepath,
                mimetype='text/csv',
                as_attachment=True,
                download_name=filename
            )
        return jsonify({
            "status": "error",
            "message": "File not found"
        }), 404
    
    return jsonify({
        "status": result.state.lower()
    })
