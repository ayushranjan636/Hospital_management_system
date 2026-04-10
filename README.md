# Hospital Management System

A full-stack Hospital Management System for managing patients, doctors, appointments, treatments, and admin operations in one place.

## Core Features

- Role-based access for Admin, Doctor, and Patient users.
- Patient registration, login, profile management, and appointment booking.
- Doctor appointment management, availability control, and treatment updates.
- Admin dashboards for users, appointments, platform stats, and quick actions.
- Appointment history with payment and transaction tracking.
- CSV export of patient treatment history.
- Email workflows for daily reminders and monthly doctor activity reports.
- Monthly report delivery in HTML and PDF formats.

## Tech Stack

- Backend: Flask, SQLAlchemy, Flask-JWT-Extended, Flask-Mail, Celery
- Frontend: Vue 3, Axios, Chart.js
- Database: SQLite

## Project Structure

- `backend/`: Flask API, models, routes, tasks, templates
- `frontend/src/`: Vue app UI and static assets

## Quick Start

1. Install backend dependencies:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. Run the application:

```bash
python3 -m flask --app app:create_app run --host=127.0.0.1 --port=5000
```

3. Open in browser:

```text
http://127.0.0.1:5000
```

Default admin login:

- Username: `admin`
- Password: `admin123`

## Optional Background Worker

If you want scheduled/background task execution with Celery:

```bash
cd backend
source .venv/bin/activate
python3 celery_worker.py
```
