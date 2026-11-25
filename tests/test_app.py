import tempfile
import unittest
from pathlib import Path

import backend.app as hospital


class HospitalApiTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        hospital.DATABASE = Path(self.temp_dir.name) / "test-hospital.db"
        hospital.initialize_database()
        hospital.app.config.update(TESTING=True)
        self.client = hospital.app.test_client()
        response = self.client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
        self.assertEqual(response.status_code, 200)
        self.csrf = response.get_json()["csrf_token"]
        self.headers = {"X-CSRF-Token": self.csrf}

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_authentication_and_patient_crud(self):
        anonymous = hospital.app.test_client()
        self.assertEqual(anonymous.get("/api/patients").status_code, 401)
        created = self.client.post("/api/patients", headers=self.headers, json={
            "full_name": "Jamie Example", "age": 28, "gender": "Other", "phone": "555-0199",
        })
        self.assertEqual(created.status_code, 201)
        record_id = created.get_json()["id"]
        patient = self.client.get(f"/api/patients/{record_id}").get_json()
        self.assertEqual(patient["patient_code"], "P-00004")
        self.assertEqual(patient["full_name"], "Jamie Example")
        updated = self.client.put(f"/api/patients/{record_id}", headers=self.headers, json={"phone": "555-0100"})
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(self.client.get("/api/patients?search=0100").get_json()[0]["phone"], "555-0100")
        self.assertEqual(self.client.delete(f"/api/patients/{record_id}", headers=self.headers).status_code, 200)

    def test_doctor_crud_and_appointment_conflict(self):
        doctor = self.client.post("/api/doctors", headers=self.headers, json={
            "full_name": "Sam Clinician", "specialization": "Neurology",
            "phone": "555-0188", "department_id": 1, "consultation_fee": 100,
        })
        self.assertEqual(doctor.status_code, 201)
        doctor_id = doctor.get_json()["id"]
        appointment = {
            "patient_id": 1, "doctor_id": doctor_id, "appointment_date": "2099-04-03",
            "appointment_time": "10:30", "reason": "Routine consultation",
        }
        self.assertEqual(self.client.post("/api/appointments", headers=self.headers, json=appointment).status_code, 201)
        conflict = self.client.post("/api/appointments", headers=self.headers, json=appointment)
        self.assertEqual(conflict.status_code, 409)
        self.assertIn("already has an appointment", conflict.get_json()["error"])
        appointment_id = self.client.get("/api/appointments").get_json()[0]["id"]
        self.assertEqual(self.client.put(f"/api/appointments/{appointment_id}", headers=self.headers, json={"status": "Cancelled"}).status_code, 200)
        self.assertEqual(self.client.post("/api/appointments", headers=self.headers, json=appointment).status_code, 201)
        self.assertEqual(self.client.put(f"/api/doctors/{doctor_id}", headers=self.headers, json={"consultation_fee": 125}).status_code, 200)
        another_doctor = self.client.post("/api/doctors", headers=self.headers, json={
            "full_name": "Avery Clinician", "specialization": "Dermatology",
            "phone": "555-0189", "department_id": 2,
        })
        self.assertEqual(another_doctor.status_code, 201)
        self.assertEqual(self.client.delete(f"/api/doctors/{another_doctor.get_json()['id']}", headers=self.headers).status_code, 200)
        department = self.client.post("/api/departments", headers=self.headers, json={"name": "Neurology", "location": "West Wing"})
        self.assertEqual(department.status_code, 201)
        department_id = department.get_json()["id"]
        self.assertEqual(self.client.put(f"/api/departments/{department_id}", headers=self.headers, json={"description": "Brain and nerve care"}).status_code, 200)
        self.assertEqual(self.client.delete(f"/api/departments/{department_id}", headers=self.headers).status_code, 200)

    def test_medical_records_invoices_payments_and_dashboard(self):
        record = self.client.post("/api/medical-records", headers=self.headers, json={
            "patient_id": 1, "doctor_id": 1, "record_date": "2026-03-04",
            "diagnosis": "Seasonal allergies", "treatment": "Antihistamine",
        })
        self.assertEqual(record.status_code, 201)
        invoice = self.client.post("/api/invoices", headers=self.headers, json={
            "patient_id": 1, "invoice_date": "2026-03-04",
            "items": [{"description": "Consultation", "quantity": 1, "unit_price": 120}],
        })
        self.assertEqual(invoice.status_code, 201)
        invoice_id = invoice.get_json()["id"]
        payment = self.client.post(f"/api/invoices/{invoice_id}/payments", headers=self.headers, json={
            "amount": 50, "method": "Card", "payment_date": "2026-03-04",
        })
        self.assertEqual(payment.status_code, 201)
        self.assertEqual(self.client.get(f"/api/invoices/{invoice_id}").get_json()["status"], "Partially paid")
        self.assertEqual(self.client.post(f"/api/invoices/{invoice_id}/items", headers=self.headers, json={
            "description": "Lab service", "quantity": 1, "unit_price": 20,
        }).status_code, 201)
        overpayment = self.client.post(f"/api/invoices/{invoice_id}/payments", headers=self.headers, json={"amount": 91})
        self.assertEqual(overpayment.status_code, 400)
        self.assertEqual(self.client.post(f"/api/invoices/{invoice_id}/payments", headers=self.headers, json={"amount": 90, "method": "Cash"}).status_code, 201)
        invoice_data = self.client.get(f"/api/invoices/{invoice_id}").get_json()
        self.assertEqual(invoice_data["status"], "Paid")
        self.assertEqual(invoice_data["total"], 140)
        dashboard = self.client.get("/api/dashboard").get_json()
        self.assertEqual(dashboard["patients"], 3)
        self.assertEqual(dashboard["doctors"], 3)
        self.assertEqual(dashboard["departments"], 3)
        self.assertEqual(len(self.client.get(f"/api/invoices/{invoice_id}/payments").get_json()), 2)

    def test_session_and_database_persist_across_clients(self):
        self.client.post("/api/patients", headers=self.headers, json={
            "full_name": "Persistent Example", "age": 40, "gender": "Female", "phone": "555-0177",
        })
        another_client = hospital.app.test_client()
        self.assertEqual(another_client.get("/api/patients").status_code, 401)
        login = another_client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
        self.assertEqual(login.status_code, 200)
        hospital.initialize_database()
        matches = another_client.get("/api/patients?search=Persistent").get_json()
        self.assertEqual(matches[0]["full_name"], "Persistent Example")
        self.assertEqual(another_client.post("/api/auth/logout", headers={"X-CSRF-Token": login.get_json()["csrf_token"]}).status_code, 200)
        self.assertEqual(another_client.get("/api/patients").status_code, 401)


if __name__ == "__main__":
    unittest.main()
