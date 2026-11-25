# CarePoint Hospital Management System

A locally hosted hospital administration system built with Flask, SQLite, HTML, CSS, and vanilla JavaScript. The database is created automatically at `backend/database/hospital.db` and persists between application restarts.

## Requirements

- Python 3.9 or newer
- pip

## Install and run

From the project directory:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python backend\app.py
```

Open [http://127.0.0.1:5000](http://127.0.0.1:5000). For the local demo, sign in with **admin** / **admin123**. Change the initial password by setting `HOSPITAL_ADMIN_PASSWORD` before the first run; set `HOSPITAL_SECRET_KEY` to a private random value for deployments. The demo account is created only when the database is initialized.

The database location can be changed with `HOSPITAL_DATABASE`. All management APIs require an authenticated session. The included sample patient and clinician records are fictional.

## Features

- Dashboard statistics, department chart, recent patients, and upcoming visits
- Patient, doctor, department, appointment, and medical-record management
- Appointment conflict checks for a doctor's date and time (cancelled slots can be reused)
- Invoices with service line items, balances, and payment history
- Server-side validation, parameterized SQLite queries, foreign-key constraints, hashed account passwords, and CSRF-protected session requests

## Tests

Run the API integration tests with:

```powershell
python -m unittest discover -s tests -v
```
