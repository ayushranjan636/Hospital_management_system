def user_to_dict(user):
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "role": user.role,
        "is_active": user.is_active,
    }


def _doctor_display_name(doctor):
    raw_name = (doctor.name or doctor.user.username or "").strip()
    pretty_name = raw_name.replace("_", " ").strip()
    lowered = pretty_name.lower()
    if lowered.startswith("dr. "):
        pretty_name = pretty_name[4:].strip()
    elif lowered.startswith("dr "):
        pretty_name = pretty_name[3:].strip()
    return pretty_name.title() if pretty_name else (doctor.user.username or "")


def doctor_to_dict(doctor):
    return {
        "id": doctor.id,
        "user_id": doctor.user_id,
        "name": _doctor_display_name(doctor),
        "username": doctor.user.username,
        "email": doctor.user.email,
        "specialization": doctor.specialization,
        "department": doctor.department.name if doctor.department else None,
        "department_id": doctor.department_id,
        "bio": doctor.bio,
        "charge_per_slot": getattr(doctor, 'charge_per_slot', 150.0),
        "is_active": doctor.user.is_active,
        "availability": [
            {
                "date": a.date.isoformat(),
                "start_time": a.start_time.strftime("%H:%M"),
                "end_time": a.end_time.strftime("%H:%M")
            } for a in doctor.availabilities if a.is_available
        ]
    }

def appointment_to_dict(appointment):
    return {
        "id": appointment.id,
        "doctor_id": appointment.doctor_id,
        "doctor_name": _doctor_display_name(appointment.doctor),
        "patient_id": appointment.patient_id,
        "patient_name": appointment.patient.name or appointment.patient.user.username,
        "date": appointment.date.isoformat(),
        "time": appointment.time.strftime("%H:%M"),
        "status": appointment.status,
        "reason": appointment.reason,
        "patient_report": getattr(appointment, 'patient_report', ''),
        "paid_amount": getattr(appointment, 'paid_amount', 0.0),
        "transaction_id": f"TXN-{appointment.id}-{int(appointment.created_at.timestamp())}" if hasattr(appointment, 'created_at') and appointment.created_at else f"TXN-{appointment.id}",
        "treatment": {
            "diagnosis": appointment.treatment.diagnosis,
            "prescription": appointment.treatment.prescription,
            "notes": appointment.treatment.notes,
            "next_visit_suggestion": appointment.treatment.next_visit_suggestion,
        }
        if appointment.treatment
        else None,
    }
