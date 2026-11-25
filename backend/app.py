import os
import math
import secrets
import sqlite3
from datetime import date, datetime
from functools import wraps
from pathlib import Path

from flask import Flask, g, jsonify, request, send_from_directory, session
from werkzeug.security import check_password_hash, generate_password_hash


ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"
DATABASE = Path(os.environ.get("HOSPITAL_DATABASE", Path(__file__).parent / "database" / "hospital.db"))
DATABASE.parent.mkdir(parents=True, exist_ok=True)

app = Flask(__name__)
app.secret_key = os.environ.get("HOSPITAL_SECRET_KEY") or secrets.token_hex(32)
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax")

RESOURCES = {
    "patients": {
        "table": "patients", "fields": ("full_name", "age", "gender", "phone", "address", "blood_group", "registration_date"),
        "required": ("full_name", "age", "gender", "phone"),
    },
    "doctors": {
        "table": "doctors", "fields": ("full_name", "specialization", "phone", "department_id", "working_days", "consultation_fee"),
        "required": ("full_name", "specialization", "phone", "department_id"),
    },
    "departments": {
        "table": "departments", "fields": ("name", "description", "location"),
        "required": ("name",),
    },
    "appointments": {
        "table": "appointments", "fields": ("patient_id", "doctor_id", "appointment_date", "appointment_time", "reason", "status"),
        "required": ("patient_id", "doctor_id", "appointment_date", "appointment_time"),
    },
    "medical-records": {
        "table": "medical_records", "fields": ("patient_id", "doctor_id", "record_date", "diagnosis", "treatment", "notes"),
        "required": ("patient_id", "doctor_id", "record_date", "diagnosis"),
    },
    "invoices": {
        "table": "invoices", "fields": ("patient_id", "invoice_date", "due_date", "status", "notes"),
        "required": ("patient_id", "invoice_date"),
    },
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS departments (
    id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE,
    description TEXT NOT NULL DEFAULT '', location TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS patients (
    id INTEGER PRIMARY KEY AUTOINCREMENT, patient_code TEXT NOT NULL UNIQUE,
    full_name TEXT NOT NULL, age INTEGER NOT NULL CHECK(age BETWEEN 0 AND 125),
    gender TEXT NOT NULL CHECK(gender IN ('Female','Male','Other')),
    phone TEXT NOT NULL, address TEXT NOT NULL DEFAULT '',
    blood_group TEXT NOT NULL DEFAULT '', registration_date TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS doctors (
    id INTEGER PRIMARY KEY AUTOINCREMENT, full_name TEXT NOT NULL,
    specialization TEXT NOT NULL, phone TEXT NOT NULL,
    department_id INTEGER NOT NULL REFERENCES departments(id) ON DELETE RESTRICT,
    working_days TEXT NOT NULL DEFAULT '', consultation_fee REAL NOT NULL DEFAULT 0 CHECK(consultation_fee >= 0)
);
CREATE TABLE IF NOT EXISTS appointments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id INTEGER NOT NULL REFERENCES patients(id) ON DELETE RESTRICT,
    doctor_id INTEGER NOT NULL REFERENCES doctors(id) ON DELETE RESTRICT,
    appointment_date TEXT NOT NULL, appointment_time TEXT NOT NULL,
    reason TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'Pending' CHECK(status IN ('Pending','Confirmed','Completed','Cancelled')),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS medical_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id INTEGER NOT NULL REFERENCES patients(id) ON DELETE RESTRICT,
    doctor_id INTEGER NOT NULL REFERENCES doctors(id) ON DELETE RESTRICT,
    record_date TEXT NOT NULL, diagnosis TEXT NOT NULL, treatment TEXT NOT NULL DEFAULT '', notes TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS invoices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id INTEGER NOT NULL REFERENCES patients(id) ON DELETE RESTRICT,
    invoice_date TEXT NOT NULL, due_date TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'Unpaid' CHECK(status IN ('Paid','Partially paid','Unpaid')),
    notes TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS invoice_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id INTEGER NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
    description TEXT NOT NULL, quantity INTEGER NOT NULL CHECK(quantity > 0),
    unit_price REAL NOT NULL CHECK(unit_price >= 0)
);
CREATE TABLE IF NOT EXISTS payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id INTEGER NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
    amount REAL NOT NULL CHECK(amount > 0), payment_date TEXT NOT NULL,
    method TEXT NOT NULL DEFAULT 'Cash', notes TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_appointments_date ON appointments(appointment_date);
CREATE UNIQUE INDEX IF NOT EXISTS idx_appointment_doctor_slot
    ON appointments(doctor_id, appointment_date, appointment_time) WHERE status != 'Cancelled';
CREATE INDEX IF NOT EXISTS idx_records_patient ON medical_records(patient_id);
CREATE INDEX IF NOT EXISTS idx_invoice_patient ON invoices(patient_id);
"""


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE, timeout=10)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(_error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def initialize_database():
    connection = sqlite3.connect(DATABASE)
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(SCHEMA)
    connection.execute(
        "INSERT OR IGNORE INTO users (username, password_hash) VALUES (?, ?)",
        ("admin", generate_password_hash(os.environ.get("HOSPITAL_ADMIN_PASSWORD", "admin123"))),
    )
    if connection.execute("SELECT COUNT(*) FROM departments").fetchone()[0] == 0:
        connection.executemany(
            "INSERT INTO departments (name, description, location) VALUES (?, ?, ?)",
            [
                ("Cardiology", "Heart and cardiovascular care", "North Wing"),
                ("Pediatrics", "Care for infants, children, and adolescents", "East Wing"),
                ("Family Medicine", "Primary and preventive care", "Main Building"),
            ],
        )
    if connection.execute("SELECT COUNT(*) FROM doctors").fetchone()[0] == 0:
        connection.executemany(
            "INSERT INTO doctors (full_name,specialization,phone,department_id,working_days,consultation_fee) VALUES (?,?,?,?,?,?)",
            [
                ("Jordan Lee", "Cardiologist", "555-0101", 1, "Mon, Wed, Fri", 120),
                ("Taylor Reed", "Pediatrician", "555-0102", 2, "Tue, Thu, Sat", 90),
                ("Morgan Blake", "Family Physician", "555-0103", 3, "Mon-Fri", 75),
            ],
        )
    if connection.execute("SELECT COUNT(*) FROM patients").fetchone()[0] == 0:
        connection.executemany(
            "INSERT INTO patients (patient_code,full_name,age,gender,phone,address,blood_group,registration_date) VALUES (?,?,?,?,?,?,?,?)",
            [
                ("P-00001", "Casey Parker", 34, "Female", "555-0141", "18 Oak Street", "O+", date.today().isoformat(),),
                ("P-00002", "Riley Bennett", 51, "Male", "555-0142", "42 Cedar Avenue", "A-", date.today().isoformat(),),
                ("P-00003", "Alex Morgan", 12, "Other", "555-0143", "7 Pine Road", "B+", date.today().isoformat(),),
            ],
        )
    connection.commit()
    connection.close()


def login_required(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            return jsonify(error="Please sign in to continue."), 401
        return function(*args, **kwargs)
    return wrapped


@app.before_request
def check_csrf():
    if request.path.startswith("/api/") and request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        if request.path == "/api/auth/login":
            return None
        if session.get("user_id") and request.headers.get("X-CSRF-Token") != session.get("csrf_token"):
            return jsonify(error="Your session token expired. Refresh and try again."), 403
    return None


def row_dict(row):
    return dict(row) if row is not None else None


def clean_payload(fields, required):
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ValueError("Request body must be a JSON object.")
    cleaned = {}
    for field in fields:
        value = data.get(field)
        if isinstance(value, str):
            value = value.strip()
        if field in required and (value is None or value == ""):
            raise ValueError(f"{field.replace('_', ' ').capitalize()} is required.")
        if value is not None:
            if field in {"age", "department_id", "patient_id", "doctor_id"}:
                try:
                    if isinstance(value, bool):
                        raise ValueError()
                    original = value
                    value = int(value)
                    if isinstance(original, float) and not original.is_integer():
                        raise ValueError()
                except (TypeError, ValueError):
                    raise ValueError(f"{field.replace('_', ' ').capitalize()} must be a whole number.")
            elif field == "consultation_fee":
                try:
                    value = float(value)
                    if not math.isfinite(value):
                        raise ValueError()
                except (TypeError, ValueError):
                    raise ValueError("Consultation fee must be a valid number.")
            elif not isinstance(value, str):
                raise ValueError(f"{field.replace('_', ' ').capitalize()} must be text.")
            if isinstance(value, str) and len(value) > 2000:
                raise ValueError(f"{field.replace('_', ' ').capitalize()} is too long.")
            cleaned[field] = value
    return cleaned


def validate_resource(resource, data):
    if resource == "patients":
        if "age" in data and (not str(data["age"]).isdigit() or not 0 <= int(data["age"]) <= 125):
            raise ValueError("Age must be a whole number from 0 to 125.")
        if data.get("gender") not in (None, "Female", "Male", "Other"):
            raise ValueError("Choose a valid gender.")
        if "registration_date" in data and not valid_date(data["registration_date"]):
            raise ValueError("Registration date must use YYYY-MM-DD format.")
    elif resource == "doctors":
        if "consultation_fee" in data and not positive_or_zero(data["consultation_fee"]):
            raise ValueError("Consultation fee must be a non-negative number.")
        if "department_id" in data and not exists("departments", data["department_id"]):
            raise ValueError("Choose an existing department.")
    elif resource == "appointments":
        for field, table in (("patient_id", "patients"), ("doctor_id", "doctors")):
            if field in data and not exists(table, data[field]):
                raise ValueError(f"Choose an existing {field.replace('_id', '')}.")
        if data.get("appointment_date") and not valid_date(data["appointment_date"]):
            raise ValueError("Appointment date must use YYYY-MM-DD format.")
        if data.get("appointment_time") and not valid_time(data["appointment_time"]):
            raise ValueError("Appointment time must use HH:MM format.")
        if data.get("status") and data["status"] not in ("Pending", "Confirmed", "Completed", "Cancelled"):
            raise ValueError("Choose a valid appointment status.")
    elif resource == "medical-records":
        for field, table in (("patient_id", "patients"), ("doctor_id", "doctors")):
            if field in data and not exists(table, data[field]):
                raise ValueError(f"Choose an existing {field.replace('_id', '')}.")
        if data.get("record_date") and not valid_date(data["record_date"]):
            raise ValueError("Record date must use YYYY-MM-DD format.")
    elif resource == "invoices":
        if "patient_id" in data and not exists("patients", data["patient_id"]):
            raise ValueError("Choose an existing patient.")
        for field in ("invoice_date", "due_date"):
            if data.get(field) and not valid_date(data[field]):
                raise ValueError(f"{field.replace('_', ' ').capitalize()} must use YYYY-MM-DD format.")


def valid_date(value):
    try:
        return datetime.strptime(str(value), "%Y-%m-%d").date().isoformat() == str(value)
    except ValueError:
        return False


def valid_time(value):
    try:
        return datetime.strptime(str(value), "%H:%M").strftime("%H:%M") == str(value)
    except ValueError:
        return False


def positive_or_zero(value):
    try:
        return float(value) >= 0
    except (TypeError, ValueError):
        return False


def exists(table, value):
    try:
        return get_db().execute(f"SELECT 1 FROM {table} WHERE id = ?", (int(value),)).fetchone() is not None
    except (TypeError, ValueError):
        return False


def resource_rows(resource, search=""):
    table = RESOURCES[resource]["table"]
    query = f"SELECT * FROM {table}"
    args = []
    if search:
        columns = {
            "patients": ("patient_code", "full_name", "phone"),
            "doctors": ("full_name", "specialization", "phone"),
            "departments": ("name", "location"),
            "appointments": ("reason", "status", "appointment_date"),
            "medical-records": ("diagnosis", "treatment", "record_date"),
            "invoices": ("status", "invoice_date"),
        }[resource]
        query += " WHERE " + " OR ".join(f"{column} LIKE ?" for column in columns)
        args = [f"%{search}%"] * len(columns)
    query += " ORDER BY id DESC"
    if resource == "appointments" and search:
        query += " OR patient_id IN (SELECT id FROM patients WHERE full_name LIKE ?) OR doctor_id IN (SELECT id FROM doctors WHERE full_name LIKE ?)"
        args.extend([f"%{search}%", f"%{search}%"])
    elif resource == "medical-records" and search:
        query += " OR patient_id IN (SELECT id FROM patients WHERE full_name LIKE ?) OR doctor_id IN (SELECT id FROM doctors WHERE full_name LIKE ?)"
        args.extend([f"%{search}%", f"%{search}%"])
    elif resource == "invoices" and search:
        query += " OR patient_id IN (SELECT id FROM patients WHERE full_name LIKE ?)"
        args.append(f"%{search}%")
    rows = [row_dict(row) for row in get_db().execute(query, args).fetchall()]
    if resource == "doctors":
        for row in rows:
            row["department"] = get_db().execute("SELECT name FROM departments WHERE id=?", (row["department_id"],)).fetchone()["name"]
    elif resource == "appointments":
        for row in rows:
            row["patient"] = get_db().execute("SELECT full_name FROM patients WHERE id=?", (row["patient_id"],)).fetchone()["full_name"]
            row["doctor"] = get_db().execute("SELECT full_name FROM doctors WHERE id=?", (row["doctor_id"],)).fetchone()["full_name"]
    elif resource == "medical-records":
        for row in rows:
            row["patient"] = get_db().execute("SELECT full_name FROM patients WHERE id=?", (row["patient_id"],)).fetchone()["full_name"]
            row["doctor"] = get_db().execute("SELECT full_name FROM doctors WHERE id=?", (row["doctor_id"],)).fetchone()["full_name"]
    elif resource == "invoices":
        for row in rows:
            row["patient"] = get_db().execute("SELECT full_name FROM patients WHERE id=?", (row["patient_id"],)).fetchone()["full_name"]
            row["total"] = invoice_total(row["id"])
            row["paid"] = paid_total(row["id"])
    return rows


def invoice_total(invoice_id):
    row = get_db().execute("SELECT COALESCE(SUM(quantity * unit_price),0) AS total FROM invoice_items WHERE invoice_id=?", (invoice_id,)).fetchone()
    return round(row["total"], 2)


def paid_total(invoice_id):
    row = get_db().execute("SELECT COALESCE(SUM(amount),0) AS total FROM payments WHERE invoice_id=?", (invoice_id,)).fetchone()
    return round(row["total"], 2)


@app.get("/")
def home():
    return send_from_directory(FRONTEND, "index.html")


@app.get("/<path:filename>")
def frontend_file(filename):
    if filename.startswith("api/"):
        return jsonify(error="Not found."), 404
    return send_from_directory(FRONTEND, filename)


@app.post("/api/auth/login")
def login():
    data = request.get_json(silent=True) or {}
    username, password = data.get("username", ""), data.get("password", "")
    if not isinstance(username, str) or not isinstance(password, str):
        return jsonify(error="Enter a valid username and password."), 400
    row = get_db().execute("SELECT id, username, password_hash FROM users WHERE username=?", (username,)).fetchone()
    if not row or not check_password_hash(row["password_hash"], password):
        return jsonify(error="Incorrect username or password."), 401
    session.clear()
    session["user_id"] = row["id"]
    session["username"] = row["username"]
    session["csrf_token"] = secrets.token_urlsafe(32)
    return jsonify(username=row["username"], csrf_token=session["csrf_token"])


@app.get("/api/auth/me")
def current_user():
    if not session.get("user_id"):
        return jsonify(authenticated=False), 200
    return jsonify(authenticated=True, username=session["username"], csrf_token=session["csrf_token"])


@app.post("/api/auth/logout")
@login_required
def logout():
    session.clear()
    return jsonify(ok=True)


@app.route("/api/<resource>", methods=["GET", "POST"])
@login_required
def collection(resource):
    if resource not in RESOURCES:
        return jsonify(error="Unknown resource."), 404
    if request.method == "GET":
        return jsonify(resource_rows(resource, request.args.get("search", "").strip()))
    config = RESOURCES[resource]
    try:
        data = clean_payload(config["fields"], config["required"])
        invoice_items = []
        if resource == "invoices":
            raw_items = (request.get_json(silent=True) or {}).get("items", [])
            if not isinstance(raw_items, list):
                raise ValueError("Invoice items must be a list.")
            for item in raw_items:
                if not isinstance(item, dict):
                    raise ValueError("Each invoice item must be an object.")
                description = str(item.get("description", "")).strip()
                try:
                    raw_quantity = item.get("quantity", 1)
                    quantity, unit_price = int(raw_quantity), float(item.get("unit_price"))
                    if (isinstance(raw_quantity, float) and not raw_quantity.is_integer()) or not description or len(description) > 200 or quantity < 1 or unit_price < 0 or not math.isfinite(unit_price):
                        raise ValueError()
                except (ValueError, TypeError):
                    raise ValueError("Enter a description, positive quantity, and non-negative unit price for each service.")
                invoice_items.append((description, quantity, unit_price))
        if resource == "patients" and "registration_date" not in data:
            data["registration_date"] = date.today().isoformat()
        if resource == "appointments" and "status" not in data:
            data["status"] = "Pending"
        if resource == "medical-records" and "record_date" not in data:
            data["record_date"] = date.today().isoformat()
        if resource == "invoices":
            data.setdefault("invoice_date", date.today().isoformat())
            data.setdefault("status", "Unpaid")
        validate_resource(resource, data)
        db = get_db()
        if resource == "patients":
            cursor = db.execute(
                "INSERT INTO patients (patient_code,full_name,age,gender,phone,address,blood_group,registration_date) VALUES (?,?,?,?,?,?,?,?)",
                (next_patient_code(), data["full_name"], int(data["age"]), data["gender"], data["phone"],
                 data.get("address", ""), data.get("blood_group", ""), data["registration_date"]),
            )
        else:
            columns = list(data)
            cursor = db.execute(
                f"INSERT INTO {config['table']} ({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})",
                tuple(data[column] for column in columns),
            )
        if resource == "invoices" and invoice_items:
            db.executemany(
                "INSERT INTO invoice_items (invoice_id,description,quantity,unit_price) VALUES (?,?,?,?)",
                [(cursor.lastrowid, description, quantity, price) for description, quantity, price in invoice_items],
            )
        db.commit()
        return jsonify(id=cursor.lastrowid), 201
    except ValueError as error:
        return jsonify(error=str(error)), 400
    except sqlite3.IntegrityError as error:
        get_db().rollback()
        return jsonify(error=integrity_message(error)), 409


@app.route("/api/<resource>/<int:record_id>", methods=["GET", "PUT", "DELETE"])
@login_required
def item(resource, record_id):
    if resource not in RESOURCES:
        return jsonify(error="Unknown resource."), 404
    config = RESOURCES[resource]
    db = get_db()
    current = db.execute(f"SELECT * FROM {config['table']} WHERE id=?", (record_id,)).fetchone()
    if current is None:
        return jsonify(error="Record not found."), 404
    if request.method == "GET":
        result = row_dict(current)
        if resource == "invoices":
            result["items"] = [row_dict(r) for r in db.execute("SELECT description,quantity,unit_price FROM invoice_items WHERE invoice_id=?", (record_id,))]
            result["total"] = invoice_total(record_id)
            result["paid"] = paid_total(record_id)
        return jsonify(result)
    if request.method == "DELETE":
        try:
            db.execute(f"DELETE FROM {config['table']} WHERE id=?", (record_id,))
            db.commit()
            return jsonify(ok=True)
        except sqlite3.IntegrityError:
            db.rollback()
            return jsonify(error="This record is linked to other records and cannot be deleted."), 409
    try:
        data = clean_payload(config["fields"], ())
        if resource == "patients" and "age" in data:
            data["age"] = int(data["age"])
        validate_resource(resource, data)
        if not data:
            return jsonify(error="No editable fields were provided."), 400
        columns = list(data)
        db.execute(
            f"UPDATE {config['table']} SET {','.join(f'{column}=?' for column in columns)} WHERE id=?",
            tuple(data[column] for column in columns) + (record_id,),
        )
        db.commit()
        return jsonify(ok=True)
    except (ValueError, TypeError) as error:
        return jsonify(error=str(error)), 400
    except sqlite3.IntegrityError as error:
        db.rollback()
        return jsonify(error=integrity_message(error)), 409


def next_patient_code():
    row = get_db().execute("SELECT COALESCE(MAX(id),0)+1 AS next_id FROM patients").fetchone()
    return f"P-{row['next_id']:05d}"


def integrity_message(error):
    message = str(error)
    if "UNIQUE constraint failed: appointments" in message:
        return "That doctor already has an appointment at this date and time."
    if "UNIQUE constraint failed: departments.name" in message:
        return "A department with that name already exists."
    if "UNIQUE constraint failed: patients.patient_code" in message:
        return "Could not generate a unique patient ID. Please try again."
    return "The change conflicts with related data or a database constraint."


@app.get("/api/options")
@login_required
def options():
    db = get_db()
    return jsonify(
        patients=[row_dict(r) for r in db.execute("SELECT id,patient_code,full_name FROM patients ORDER BY full_name")],
        doctors=[row_dict(r) for r in db.execute("SELECT id,full_name,department_id FROM doctors ORDER BY full_name")],
        departments=[row_dict(r) for r in db.execute("SELECT id,name FROM departments ORDER BY name")],
    )


@app.get("/api/dashboard")
@login_required
def dashboard():
    db = get_db()
    today = date.today().isoformat()
    counts = {
        "patients": db.execute("SELECT COUNT(*) FROM patients").fetchone()[0],
        "doctors": db.execute("SELECT COUNT(*) FROM doctors").fetchone()[0],
        "appointments_today": db.execute("SELECT COUNT(*) FROM appointments WHERE appointment_date=? AND status!='Cancelled'", (today,)).fetchone()[0],
        "departments": db.execute("SELECT COUNT(*) FROM departments").fetchone()[0],
    }
    recent = [row_dict(r) for r in db.execute("SELECT id,patient_code,full_name,registration_date FROM patients ORDER BY id DESC LIMIT 5")]
    upcoming = [row_dict(r) for r in db.execute(
        """SELECT a.id,a.appointment_date,a.appointment_time,a.status,p.full_name AS patient,d.full_name AS doctor
        FROM appointments a JOIN patients p ON p.id=a.patient_id JOIN doctors d ON d.id=a.doctor_id
        WHERE a.appointment_date>=? AND a.status!='Cancelled' ORDER BY a.appointment_date,a.appointment_time LIMIT 6""", (today,)
    )]
    distribution = [row_dict(r) for r in db.execute(
        "SELECT d.name,COUNT(DISTINCT p.id) AS patients FROM departments d LEFT JOIN doctors doc ON doc.department_id=d.id LEFT JOIN appointments a ON a.doctor_id=doc.id LEFT JOIN patients p ON p.id=a.patient_id GROUP BY d.id ORDER BY d.name"
    )]
    return jsonify(**counts, recent_patients=recent, upcoming_appointments=upcoming, department_stats=distribution)


@app.post("/api/invoices/<int:invoice_id>/items")
@login_required
def add_invoice_item(invoice_id):
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return jsonify(error="Request body must be a JSON object."), 400
    if not isinstance(data.get("description", ""), str):
        return jsonify(error="Service description must be text."), 400
    description = str(data.get("description", "")).strip()
    quantity, unit_price = data.get("quantity", 1), data.get("unit_price")
    if not exists("invoices", invoice_id):
        return jsonify(error="Invoice not found."), 404
    if not description or len(description) > 200:
        return jsonify(error="Enter a service description (up to 200 characters)."), 400
    try:
        original_quantity = quantity
        quantity, unit_price = int(quantity), float(unit_price)
        if (isinstance(original_quantity, float) and not original_quantity.is_integer()) or quantity < 1 or unit_price < 0 or not math.isfinite(unit_price):
            raise ValueError()
    except (ValueError, TypeError):
        return jsonify(error="Quantity must be positive and price must be non-negative."), 400
    db = get_db()
    db.execute("INSERT INTO invoice_items (invoice_id,description,quantity,unit_price) VALUES (?,?,?,?)", (invoice_id, description, quantity, unit_price))
    db.commit()
    update_invoice_status(invoice_id)
    return jsonify(ok=True), 201


@app.post("/api/invoices/<int:invoice_id>/payments")
@login_required
def add_payment(invoice_id):
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return jsonify(error="Request body must be a JSON object."), 400
    if not exists("invoices", invoice_id):
        return jsonify(error="Invoice not found."), 404
    try:
        amount = float(data.get("amount"))
        if not math.isfinite(amount) or amount <= 0 or amount > invoice_total(invoice_id) - paid_total(invoice_id) + 0.001:
            raise ValueError()
    except (ValueError, TypeError):
        return jsonify(error="Payment must be greater than zero and no more than the remaining balance."), 400
    payment_date = data.get("payment_date") or date.today().isoformat()
    method = str(data.get("method", "Cash")).strip()
    if not valid_date(payment_date) or method not in ("Cash", "Card", "Insurance", "Bank transfer"):
        return jsonify(error="Choose a valid payment date and method."), 400
    db = get_db()
    db.execute("INSERT INTO payments (invoice_id,amount,payment_date,method) VALUES (?,?,?,?)", (invoice_id, amount, payment_date, method))
    db.commit()
    update_invoice_status(invoice_id)
    return jsonify(ok=True), 201


def update_invoice_status(invoice_id):
    total, paid = invoice_total(invoice_id), paid_total(invoice_id)
    status = "Paid" if total > 0 and paid >= total else ("Partially paid" if paid > 0 else "Unpaid")
    get_db().execute("UPDATE invoices SET status=? WHERE id=?", (status, invoice_id))
    get_db().commit()


@app.get("/api/invoices/<int:invoice_id>/payments")
@login_required
def invoice_payments(invoice_id):
    if not exists("invoices", invoice_id):
        return jsonify(error="Invoice not found."), 404
    rows = [row_dict(r) for r in get_db().execute("SELECT id,amount,payment_date,method,notes FROM payments WHERE invoice_id=? ORDER BY id DESC", (invoice_id,))]
    return jsonify(rows)


@app.errorhandler(500)
def internal_error(_error):
    if "db" in g:
        g.db.rollback()
    return jsonify(error="An unexpected server error occurred. Please try again."), 500


initialize_database()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", "5000")), debug=False)
