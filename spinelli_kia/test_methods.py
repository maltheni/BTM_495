"""Tests for every method of the class diagram, grouped by use case.

Run:  python -m unittest test_methods -v
"""
import unittest
from datetime import date, datetime, timedelta

import models
from models import (Admin, AutomationRule, Conversation, Customer, DealerPlate, Message, Receptionist,
                    SalesAppointment, SalesManager, ServiceRequest, TestDrive, Vehicle)

PAST = datetime.now() - timedelta(hours=2)
FUTURE = datetime.now() + timedelta(days=3)


def people():
    cust = Customer(person_id="C1", name="Alex Tremblay", email="alex@example.com",
                    phone_number="514-555-0101", messaging_consent=True, vehicle_interest="Kia Seltos")
    rec = Receptionist(person_id="R1", name="Sam Lee", email="sam@spinellikia.ca")
    mgr = SalesManager(person_id="M1", name="Jordan Roy", email="jordan@spinellikia.ca", sales_team="New cars")
    return cust, rec, mgr


class UC1Profiles(unittest.TestCase):
    def test_update_contact_info_and_preferences(self):
        cust, _, _ = people()
        cust.update_contact_info("alex.t@example.com", "514-555-0199")
        cust.update_preferences("French", True)
        self.assertEqual((cust.email, cust.preferred_language), ("alex.t@example.com", "French"))

    def test_validation_error_6a(self):
        cust, _, _ = people()
        with self.assertRaises(ValueError):
            cust.update_contact_info("not-an-email", "514-555-0199")
        self.assertEqual(cust.email, "alex@example.com")          # nothing saved

    def test_search_and_assign(self):
        cust, _, mgr = people()
        self.assertTrue(cust.matches_search("tremblay"))
        self.assertTrue(cust.matches_search("5145550101"))
        self.assertFalse(cust.matches_search("bob"))
        cust.assign_to(mgr)
        self.assertIs(cust.assigned_to, mgr)
        self.assertIn(cust, mgr.get_customers())

    def test_other_people_update_contact_info(self):
        for p in (Admin(person_id="A1", name="Ana"), Receptionist(person_id="R2", name="Bo"),
                  SalesManager(person_id="M2", name="Cy")):
            p.update_contact_info("x@y.ca", "514-555-0000")
            self.assertEqual(p.email, "x@y.ca")


class UC2Scheduling(unittest.TestCase):
    def setUp(self):
        self.cust, self.rec, self.mgr = people()
        self.appt = SalesAppointment(booking_id="B1", scheduled_date_time=FUTURE, purpose="Pricing",
                                     customer=self.cust, receptionist=self.rec, sales_manager=self.mgr)

    def test_book_and_confirm(self):
        self.assertTrue(self.appt.is_manager_available())
        self.appt.confirm()
        self.assertEqual(self.appt.status, "Confirmed")
        kinds = {m.message_type: m.status for m in self.appt.messages}
        self.assertEqual(kinds, {"Confirmation": "Sent", "Reminder": "Scheduled"})
        self.assertIn(self.appt, self.mgr.get_appointments())

    def test_slot_conflict_s1a(self):
        other = SalesAppointment(booking_id="B2", scheduled_date_time=FUTURE + timedelta(minutes=15),
                                 customer=self.cust, sales_manager=self.mgr)
        self.assertFalse(other.is_manager_available())

    def test_reschedule_moves_reminder(self):
        self.appt.confirm()
        new = FUTURE + timedelta(days=1)
        self.appt.reschedule(new)
        reminder = next(m for m in self.appt.messages if m.message_type == "Reminder")
        self.assertEqual((self.appt.status, self.appt.scheduled_date_time), ("Rescheduled", new))
        self.assertEqual(reminder.scheduled_date_time, new - timedelta(days=1))

    def test_reschedule_to_taken_slot_changes_nothing(self):
        SalesAppointment(booking_id="B3", scheduled_date_time=FUTURE + timedelta(days=2),
                         customer=self.cust, sales_manager=self.mgr)
        with self.assertRaises(ValueError):
            self.appt.reschedule(FUTURE + timedelta(days=2))
        self.assertEqual((self.appt.status, self.appt.scheduled_date_time), ("Booked", FUTURE))

    def test_cancel_cancels_reminder(self):
        self.appt.confirm()
        self.appt.cancel()
        reminder = next(m for m in self.appt.messages if m.message_type == "Reminder")
        self.assertEqual((self.appt.status, reminder.status), ("Cancelled", "Cancelled"))
        with self.assertRaises(ValueError):
            self.appt.reschedule(FUTURE)                           # cancelled cannot be moved

    def test_blocked_period_s3(self):
        SalesAppointment(booking_id="B4", scheduled_date_time=FUTURE + timedelta(days=5), duration_minutes=480,
                         purpose="Unavailable", sales_manager=self.mgr)
        late = SalesAppointment(booking_id="B5", scheduled_date_time=FUTURE + timedelta(days=5, hours=2),
                                customer=self.cust, sales_manager=self.mgr)
        self.assertFalse(late.is_manager_available())

    def test_complete(self):
        past = SalesAppointment(booking_id="B6", scheduled_date_time=PAST, customer=self.cust, sales_manager=self.mgr)
        past.confirm()
        past.complete()
        self.assertEqual(past.status, "Completed")


class UC3Reporting(unittest.TestCase):
    def setUp(self):
        self.cust, _, self.mgr = people()
        self.cust.assign_to(self.mgr)
        self.admin = Admin(person_id="A1", name="Ana Admin")
        self.rule = AutomationRule(rule_id="AR1", name="Weekly leads", frequency="Weekly",
                                   sales_manager=self.mgr)
        self.admin.manage_rule(self.rule)

    def test_run_generates_and_emails(self):
        models.OUTBOX.clear()
        self.rule.run()
        report = self.rule.reports[-1]
        self.assertEqual((report.delivery_status, report.generated_date), ("Sent", date.today()))
        self.assertIn("1 new customer", report.content)
        self.assertTrue(any("Weekly leads" in m for m in models.OUTBOX))
        self.assertIs(self.rule.admin, self.admin)

    def test_no_data_alternate_flow_1(self):
        self.rule.filters = "lead_source=online"                   # Alex is a walk-in
        report = self.rule.generate_report()
        self.assertEqual(report.content, "No data available for the selected filters.")

    def test_activate_deactivate(self):
        self.rule.deactivate()
        self.rule.run()
        self.assertEqual(self.rule.reports, [])
        self.rule.activate()
        self.assertTrue(self.rule.is_active)


class UC4TestDrive(unittest.TestCase):
    def setUp(self):
        self.cust, self.rec, _ = people()
        self.car = Vehicle(stock_number="V1", make="Kia", model="Seltos", year=2026)
        self.plate = DealerPlate(plate_number="DLR-01")
        self.td = TestDrive(booking_id="T1", scheduled_date_time=PAST, driver_license_number="T1234-56789",
                            customer=self.cust, receptionist=self.rec, vehicle=self.car)

    def test_full_test_drive(self):
        self.assertTrue(self.td.is_vehicle_available())
        self.td.confirm()
        self.td.assign_plate(self.plate)
        self.assertEqual(self.plate.status, "Assigned")
        self.td.complete()
        self.assertEqual((self.td.status, self.plate.status), ("Completed", "Free"))
        self.assertIsNotNone(self.td.return_time)
        self.assertEqual(self.cust.get_current_stage(), "Test drive")

    def test_vehicle_busy(self):
        self.td.confirm()
        other = TestDrive(booking_id="T2", scheduled_date_time=PAST, customer=self.cust, vehicle=self.car)
        self.assertFalse(other.is_vehicle_available())
        self.assertFalse(self.car.check_availability(PAST))

    def test_reschedule_test_drive(self):
        future = TestDrive(booking_id="T4", scheduled_date_time=FUTURE, driver_license_number="X",
                           customer=self.cust, vehicle=self.car)
        future.confirm()
        future.reschedule(FUTURE + timedelta(hours=1))           # same car, its own old slot is not a conflict
        self.assertEqual(future.status, "Rescheduled")
        busy = TestDrive(booking_id="T6", scheduled_date_time=FUTURE + timedelta(days=1), driver_license_number="Y",
                         customer=self.cust, vehicle=self.car)
        busy.confirm()
        with self.assertRaises(ValueError):
            future.reschedule(FUTURE + timedelta(days=1))
        self.assertEqual(future.scheduled_date_time, FUTURE + timedelta(hours=1))

    def test_plate_in_use(self):
        self.plate.assign()
        with self.assertRaises(ValueError):
            self.td.assign_plate(self.plate)

    def test_license_not_valid_cancel(self):
        self.td.cancel()
        self.assertEqual(self.td.status, "Cancelled")
        self.assertEqual(self.td.messages[-1].title, "Test drive cancelled")

    def test_cannot_complete_before_it_starts(self):
        future = TestDrive(booking_id="T3", scheduled_date_time=FUTURE, driver_license_number="X",
                           customer=self.cust, vehicle=self.car)
        future.confirm()
        with self.assertRaises(ValueError):
            future.complete()


class UC5Tracking(unittest.TestCase):
    def test_status_unavailable_then_updated(self):
        cust, _, _ = people()
        self.assertEqual(cust.get_current_stage(), "Unavailable")
        cust.add_status_update("Negotiation", "Offer sent")
        self.assertEqual(cust.get_current_stage(), "Negotiation")
        notice = cust.conversations[-1].messages[-1]
        self.assertEqual((notice.message_type, notice.status), ("Notification", "Sent"))

    def test_no_consent_no_notification(self):
        cust, _, _ = people()
        cust.messaging_consent = False
        cust.add_status_update("Lead", "")
        self.assertEqual(cust.conversations, [])

    def test_unknown_stage(self):
        cust, _, _ = people()
        with self.assertRaises(ValueError):
            cust.add_status_update("Flying", "")


class UC6Messaging(unittest.TestCase):
    def setUp(self):
        self.cust, self.rec, self.mgr = people()
        self.conv = Conversation(conversation_id="CV1", subject="Seltos pricing", customer=self.cust)
        self.conv.assign_to(self.rec)

    def test_normal_flow(self):
        inquiry = Message(message_id="MS1", conversation=self.conv, title="Question", content="Price of the Seltos?")
        self.assertTrue(inquiry.validate())
        inquiry.send()
        self.assertEqual(self.conv.count_unread(), 1)
        inquiry.mark_as_delivered()
        inquiry.mark_as_read()
        reply = Message(message_id="MS2", conversation=self.conv, title="Re: Question",
                        content="It starts at $27,000.", sender_role="Receptionist")
        reply.send()
        self.assertEqual([m.message_id for m in self.conv.get_messages()], ["MS1", "MS2"])
        self.assertIn(self.conv, self.rec.get_conversations())
        self.conv.close()
        self.assertEqual(self.conv.status, "Closed")

    def test_invalid_message_is_not_sent(self):
        empty = Message(message_id="MS3", conversation=self.conv, title="", content="hi")
        self.assertFalse(empty.validate())
        with self.assertRaises(ValueError):
            empty.send()
        self.assertEqual(empty.status, "Composed")

    def test_recipient_unreachable_5a(self):
        lonely = Conversation(conversation_id="CV2", subject="No staff yet", customer=self.cust)
        msg = Message(message_id="MS4", conversation=lonely, title="Hello", content="Anyone there?")
        with self.assertRaises(ValueError):
            msg.send()
        self.assertEqual(msg.status, "Failed")
        self.assertEqual(lonely.messages, [])

    def test_escalation_6a(self):
        self.conv.escalate_to(self.mgr)
        self.assertEqual(self.conv.status, "Escalated")
        self.assertIn(self.conv, self.mgr.escalated_conversations)

    def test_schedule_and_cancel(self):
        msg = Message(message_id="MS5", conversation=self.conv, title="Reminder", content="Tomorrow", sender_role="System")
        msg.schedule(FUTURE)
        self.assertEqual(msg.status, "Scheduled")
        msg.cancel()
        self.assertEqual(msg.status, "Cancelled")


class UC7CustomerService(unittest.TestCase):
    def setUp(self):
        self.cust, self.rec, _ = people()

    def test_submit_assign_resolve_close(self):
        req = ServiceRequest(request_id="SR1", subject="Noise", description="Rattling noise from the dashboard",
                             customer=self.cust)
        req.submit()
        self.assertIn(req, self.cust.service_requests)
        req.assign_to(self.rec)
        self.assertEqual(req.status, "In progress")
        req.resolve("Clip replaced")
        req.close()
        self.assertEqual(req.status, "Closed")

    def test_missing_information_a1(self):
        with self.assertRaises(ValueError):
            ServiceRequest(request_id="SR2", subject="", description="Rattling noise", customer=self.cust).submit()

    def test_invalid_information_a2(self):
        with self.assertRaises(ValueError):
            ServiceRequest(request_id="SR3", subject="Noise", description="bad", customer=self.cust).submit()


if __name__ == "__main__":
    unittest.main(verbosity=2)
