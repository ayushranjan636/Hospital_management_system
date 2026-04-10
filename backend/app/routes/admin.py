from datetime import date

from flask import Blueprint, jsonify, request
from sqlalchemy import or_

from ..auth_utils import role_required
from ..extensions import db
from ..models import Appointment, Department, DoctorProfile, PatientProfile, User
from ..serializers import appointment_to_dict, doctor_to_dict

admin_bp = Blueprint("admin", __name__, url_prefix="/api/admin")


@admin_bp.get("/dashboard")
@role_required("admin")
def dashboard():
    total_revenue = db.session.query(db.func.sum(Appointment.paid_amount)).scalar() or 0.0
    return jsonify(
        {
            "total_doctors": User.query.filter_by(role="doctor").count(),
            "total_patients": User.query.filter_by(role="patient").count(),
            "total_appointments": Appointment.query.count(),
            "upcoming_appointments": Appointment.query.filter(
                Appointment.date >= date.today(), Appointment.status == "Booked"
            ).count(),
            "total_revenue": total_revenue
        }
    )


@admin_bp.get("/doctors")
@role_required("admin")
def list_doctors():
    doctors = DoctorProfile.query.order_by(DoctorProfile.id.desc()).all()
    return jsonify([doctor_to_dict(d) for d in doctors])


@admin_bp.post("/doctors")
@role_required("admin")
def create_doctor():
    data = request.get_json() or {}
    required = ["username", "email", "password", "specialization", "department_name"]
    if any(not data.get(k) for k in required):
        return jsonify({"error": "missing required fields"}), 400

    if User.query.filter(or_(User.username == data["username"], User.email == data["email"])).first():
        return jsonify({"error": "username/email already exists"}), 409

    dept = Department.query.filter_by(name=data["department_name"]).first()
    if not dept:
        dept = Department(name=data["department_name"], description=data.get("department_description", ""))
        db.session.add(dept)
        db.session.flush()

    user = User(username=data["username"], email=data["email"], role="doctor")
    user.set_password(data["password"])
    doctor = DoctorProfile(
        user=user,
        name=(data.get("name") or data["username"]).strip(),
        department_id=dept.id,
        specialization=data["specialization"],
        bio=data.get("bio", ""),
    )

    db.session.add_all([user, doctor])
    db.session.commit()
    return jsonify(doctor_to_dict(doctor)), 201


@admin_bp.put("/doctors/<int:doctor_id>")
@role_required("admin")
def update_doctor(doctor_id):
    doctor = DoctorProfile.query.get_or_404(doctor_id)
    data = request.get_json() or {}

    if data.get("name") is not None:
        clean_name = data["name"].strip()
        doctor.name = clean_name if clean_name else doctor.user.username
    if data.get("specialization"):
        doctor.specialization = data["specialization"]
    if data.get("bio") is not None:
        doctor.bio = data["bio"]
    if data.get("is_active") is not None:
        doctor.user.is_active = bool(data["is_active"])
    if data.get("username"):
        doctor.user.username = data["username"]
        if not (doctor.name or "").strip():
            doctor.name = data["username"]
    if data.get("password") and data["password"].strip():
        doctor.user.set_password(data["password"].strip())

    db.session.commit()
    return jsonify(doctor_to_dict(doctor))


@admin_bp.delete("/doctors/<int:doctor_id>")
@role_required("admin")
def delete_doctor(doctor_id):
    doctor = DoctorProfile.query.get_or_404(doctor_id)
    Appointment.query.filter_by(doctor_id=doctor_id).delete()
    user = doctor.user
    db.session.delete(doctor)
    db.session.delete(user)
    db.session.commit()
    return jsonify({"message": "Doctor deleted totally"})


@admin_bp.post("/trigger-reminders")
@role_required("admin")
def trigger_reminders():
    from ..tasks import send_daily_reminders_sync

    data = request.get_json(silent=True) or {}
    test_mode = bool(data.get("test_mode", True))
    test_recipient = data.get("test_recipient")

    result = send_daily_reminders_sync(test_mode=test_mode, test_recipient=test_recipient)
    return jsonify(
        {
            "message": "Reminders processed",
            "sent": result["sent"],
            "failed": result["failed"],
            "total": result["total"],
            "test_mail_sent": result.get("test_mail_sent", False),
        }
    )


@admin_bp.post("/trigger-monthly-reports")
@role_required("admin")
def trigger_monthly_reports():
    from ..tasks import send_monthly_doctor_reports_sync

    data = request.get_json(silent=True) or {}
    report_format = (data.get("format") or "html").strip().lower()
    if report_format not in {"html", "pdf"}:
        report_format = "html"

    result = send_monthly_doctor_reports_sync(report_format=report_format)
    return jsonify(
        {
            "message": "Monthly reports processed",
            "sent": result["sent"],
            "failed": result["failed"],
            "total": result["total"],
            "format": result.get("format", report_format),
        }
    )


@admin_bp.get("/patients")
@role_required("admin")
def list_patients():
    patients = (
        PatientProfile.query.join(User, PatientProfile.user_id == User.id)
        .order_by(User.id.desc())
        .all()
    )
    result = []
    for p in patients:
        appt_count = Appointment.query.filter_by(patient_id=p.id).count()
        result.append({
            "id": p.id,
            "user_id": p.user_id,
            "username": p.user.username,
            "email": p.user.email,
            "phone": p.phone or "",
            "is_active": p.user.is_active,
            "total_appointments": appt_count,
        })
    return jsonify(result)


@admin_bp.put("/patients/<int:patient_id>")
@role_required("admin")
def update_patient(patient_id):
    patient = PatientProfile.query.get_or_404(patient_id)
    data = request.get_json() or {}
    
    if data.get("is_active") is not None:
        patient.user.is_active = bool(data["is_active"])
    
    db.session.commit()
    return jsonify({"message": "Patient updated"})


@admin_bp.delete("/patients/<int:patient_id>")
@role_required("admin")
def delete_patient(patient_id):
    patient = PatientProfile.query.get_or_404(patient_id)
    # delete their appointments first or let cascade handle it?
    Appointment.query.filter_by(patient_id=patient_id).delete()
    user = patient.user
    db.session.delete(patient)
    db.session.delete(user)
    db.session.commit()
    return jsonify({"message": "Patient deleted totally"})


@admin_bp.get("/appointments")
@role_required("admin")
def all_appointments():
    status = request.args.get("status")
    query = Appointment.query.order_by(Appointment.date.desc(), Appointment.time.desc())
    if status:
        query = query.filter_by(status=status)
    return jsonify([appointment_to_dict(a) for a in query.all()])


@admin_bp.delete("/appointments/<int:appointment_id>")
@role_required("admin")
def delete_appointment(appointment_id):
    appt = Appointment.query.get_or_404(appointment_id)
    db.session.delete(appt)
    db.session.commit()
    return jsonify({"message": "Appointment deleted"})


@admin_bp.get("/search")
@role_required("admin")
def search():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify({"patients": [], "doctors": []})

    doctors = (
        DoctorProfile.query.join(User)
        .filter(or_(User.username.ilike(f"%{q}%"), DoctorProfile.specialization.ilike(f"%{q}%")))
        .all()
    )
    patients = (
        PatientProfile.query.join(User)
        .filter(
            or_(
                User.username.ilike(f"%{q}%"),
                User.email.ilike(f"%{q}%"),
                PatientProfile.phone.ilike(f"%{q}%"),
            )
        )
        .all()
    )

    return jsonify(
        {
            "doctors": [doctor_to_dict(d) for d in doctors],
            "patients": [
                {
                    "patient_id": p.id,
                    "user_id": p.user_id,
                    "name": p.user.username,
                    "email": p.user.email,
                    "phone": p.phone,
                }
                for p in patients
            ],
        }
    )


@admin_bp.get("/doctor/<int:doctor_id>/report")
@role_required("admin")
def doctor_monthly_report(doctor_id):
    from datetime import datetime
    current_month = datetime.now().month
    current_year = datetime.now().year
    
    doctor = DoctorProfile.query.get_or_404(doctor_id)
    appointments = Appointment.query.filter(
        Appointment.doctor_id == doctor_id,
        Appointment.status == "Completed",
        db.func.strftime("%m", Appointment.date) == f"{current_month:02d}",
        db.func.strftime("%Y", Appointment.date) == str(current_year),
    ).all()
    
    total_completed = len(appointments)
    treatments_summary = []
    
    for appt in appointments:
        if appt.treatment:
            treatments_summary.append({
                "patient": appt.patient.user.username,
                "date": appt.date.isoformat(),
                "diagnosis": appt.treatment.diagnosis,
                "prescription": appt.treatment.prescription,
            })

    doctor_display_name = (doctor.name or doctor.user.username or "").replace("_", " ").strip()
    lowered = doctor_display_name.lower()
    if lowered.startswith("dr. "):
        doctor_display_name = doctor_display_name[4:].strip()
    elif lowered.startswith("dr "):
        doctor_display_name = doctor_display_name[3:].strip()
    doctor_display_name = doctor_display_name.title() if doctor_display_name else doctor.user.username
    
    return jsonify({
        "doctor_name": doctor_display_name,
        "month": current_month,
        "year": current_year,
        "total_completed": total_completed,
        "treatments": treatments_summary,
    })
