"""Prototype 2 demo: walks through the seven use cases with the implemented methods,
then saves the objects in the SQLite database and reads them back.

Run:  python main.py
"""
from datetime import datetime, timedelta

import db
import models
from models import (Admin, AutomationRule, Conversation, Customer, DealerPlate, Message, Receptionist,
                    SalesAppointment, SalesManager, ServiceRequest, TestDrive, Vehicle)


def title(text):
    print(f"\n=== {text}")


def show_outbox():
    for line in models.OUTBOX:
        print("   [notification]", line)
    models.OUTBOX.clear()


def main():
    soon = datetime.now().replace(minute=0, second=0, microsecond=0) + timedelta(days=2)

    # ---------------------------------------------------------------- UC1
    title("UC1 Create and manage profiles")
    rec = Receptionist(person_id="R001", name="Sam Lee", email="sam@spinellikia.ca")
    mgr = SalesManager(person_id="M001", name="Jordan Roy", email="jordan@spinellikia.ca", sales_team="New cars")
    admin = Admin(person_id="A001", name="Ana Admin", access_level="Full")
    cust = Customer(person_id="C001", name="Alex Tremblay", email="alex@example.com",
                    phone_number="514-555-0101", vehicle_interest="Kia Seltos", lead_source="online")
    customers = [cust]
    found = [c for c in customers if c.matches_search("tremblay")]
    print("search 'tremblay' ->", found)
    try:
        cust.update_contact_info("alex-at-example", "514-555-0101")
    except ValueError as e:
        print("validation error (6a):", e)
    cust.update_contact_info("alex.tremblay@example.com", "514-555-0101")
    cust.update_preferences("French", True)
    cust.assign_to(mgr)
    cust.add_status_update("Lead", "Online request for a Seltos")
    print("profile:", cust.email, cust.preferred_language, "consent =", cust.messaging_consent,
          "manager =", cust.assigned_to.name)
    show_outbox()

    # ---------------------------------------------------------------- UC2
    title("UC2 Scheduling system")
    appt = SalesAppointment(booking_id="B001", scheduled_date_time=soon, purpose="Pricing",
                            customer=cust, receptionist=rec, sales_manager=mgr)
    print("manager available:", appt.is_manager_available())
    appt.confirm()
    print("status:", appt.status, "| messages:", [(m.message_type, m.status) for m in appt.messages])
    clash = SalesAppointment(booking_id="B002", scheduled_date_time=soon + timedelta(days=1),
                             customer=cust, sales_manager=mgr)
    try:
        appt.reschedule(soon + timedelta(days=1))
    except ValueError as e:
        print("reschedule refused (S-1a):", e)
    clash.cancel()
    appt.reschedule(soon + timedelta(days=1, hours=2))
    print("after reschedule:", appt.status, appt.scheduled_date_time)
    show_outbox()

    # ---------------------------------------------------------------- UC4
    title("UC4 Booking system for test driving")
    car = Vehicle(stock_number="V001", vin="KNDEU2A2XS7000001", make="Kia", model="Seltos", year=2026)
    plate = DealerPlate(plate_number="DLR-01")
    drive = TestDrive(booking_id="T001", scheduled_date_time=datetime.now() - timedelta(hours=1),
                      driver_license_number="T1234-56789-01", customer=cust, receptionist=rec, vehicle=car)
    print("vehicle available:", drive.is_vehicle_available())
    drive.confirm()
    drive.assign_plate(plate)
    print("plate", plate.plate_number, "->", plate.status)
    drive.complete()
    print("after complete:", drive.status, "| plate:", plate.status, "| stage:", cust.get_current_stage())
    show_outbox()

    # ---------------------------------------------------------------- UC5
    title("UC5 Tracking for the customer")
    cust.add_status_update("Negotiation", "Offer sent")
    print("current stage:", cust.get_current_stage(),
          "| history:", [s.stage for s in cust.status_updates])
    show_outbox()

    # ---------------------------------------------------------------- UC6
    title("UC6 Messaging system")
    conv = Conversation(conversation_id="CV001", subject="Seltos pricing", customer=cust)
    conv.assign_to(rec)
    inquiry = Message(message_id="MS001", conversation=conv, title="Question",
                      content="Is the Seltos available in blue?")
    inquiry.send()
    inquiry.mark_as_delivered()
    inquiry.mark_as_read()
    reply = Message(message_id="MS002", conversation=conv, title="Re: Question",
                    content="Yes, we have one in stock.", sender_role="Receptionist")
    reply.send()
    print("unread:", conv.count_unread(), "| thread:", [m.title for m in conv.get_messages()])
    conv.escalate_to(mgr)
    print("conversation status:", conv.status)
    show_outbox()

    # ---------------------------------------------------------------- UC7
    title("UC7 Customer service system")
    req = ServiceRequest(request_id="SR001", subject="Noise", description="", customer=cust)
    try:
        req.submit()
    except ValueError as e:
        print("form refused (A-1):", e)
    req.description = "Rattling noise from the dashboard"
    req.submit()
    req.assign_to(rec)
    req.resolve("Dashboard clip replaced")
    req.close()
    print("service request:", req.status, "-", req.resolution)

    # ---------------------------------------------------------------- UC3
    title("UC3 Automation and reporting")
    rule = AutomationRule(rule_id="AR001", name="Weekly online leads", frequency="Weekly",
                          filters="lead_source=online", sales_manager=mgr)
    admin.manage_rule(rule)
    rule.run()
    report = rule.reports[-1]
    print("report:", report.report_type, report.start_date, "->", report.end_date,
          "| delivery:", report.delivery_status)
    print("content:", report.content)
    show_outbox()

    # ---------------------------------------------------------- database
    title("Database (SQLite)")
    if db.DB_PATH.exists():
        db.DB_PATH.unlink()
    db.init_db()
    with db.connect() as conn:
        for p in (cust, rec, mgr, admin):
            conn.execute("INSERT INTO person VALUES (?,?,?,?)", (p.person_id, p.name, p.email, p.phone_number))
        conn.execute("INSERT INTO receptionist VALUES (?,?)", (rec.person_id, rec.shift))
        conn.execute("INSERT INTO sales_manager VALUES (?,?)", (mgr.person_id, mgr.sales_team))
        conn.execute("INSERT INTO admin VALUES (?,?)", (admin.person_id, admin.access_level))
        conn.execute("""INSERT INTO customer VALUES (?,?,?,?,?,?,?)""",
                     (cust.person_id, cust.vehicle_interest, cust.preferred_language, int(cust.messaging_consent),
                      str(cust.created_date), cust.lead_source, mgr.person_id))
        for s in cust.status_updates:
            conn.execute("INSERT INTO status_update VALUES (?,?,?,?,?)",
                         (s.update_id, cust.person_id, s.stage, str(s.updated_date), s.note))
        for b, kind in ((appt, "SalesAppointment"), (clash, "SalesAppointment"), (drive, "TestDrive")):
            conn.execute("INSERT INTO booking VALUES (?,?,?,?,?,?,?,?)",
                         (b.booking_id, cust.person_id, b.receptionist.person_id if b.receptionist else None,
                          str(b.scheduled_date_time), b.duration_minutes, b.status, str(b.created_date), kind))
        conn.execute("INSERT INTO sales_appointment VALUES (?,?,?)", (appt.booking_id, mgr.person_id, appt.purpose))
        conn.execute("INSERT INTO sales_appointment VALUES (?,?,?)", (clash.booking_id, mgr.person_id, clash.purpose))
        conn.execute("INSERT INTO vehicle VALUES (?,?,?,?,?,?)",
                     (car.stock_number, car.vin, car.make, car.model, car.year, int(car.is_available)))
        conn.execute("INSERT INTO dealer_plate VALUES (?,?)", (plate.plate_number, plate.status))
        conn.execute("INSERT INTO test_drive VALUES (?,?,?,?,?,?)",
                     (drive.booking_id, car.stock_number, plate.plate_number, drive.driver_license_number,
                      str(drive.departure_time), str(drive.return_time)))
        for c in cust.conversations:
            conn.execute("INSERT INTO conversation VALUES (?,?,?,?,?,?,?,?)",
                         (c.conversation_id, cust.person_id, c.receptionist.person_id if c.receptionist else None,
                          c.sales_manager.person_id if c.sales_manager else None, c.subject, c.status,
                          str(c.start_date), str(c.last_activity_date)))
            unsent = [m for b in (appt, clash, drive) for m in b.messages
                      if m.conversation is c and m not in c.messages]       # scheduled reminders
            for m in c.messages + unsent:
                about = m.sales_appointment or m.test_drive
                conn.execute("""INSERT INTO message VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                             (m.message_id, c.conversation_id, about.booking_id if about else None, m.title,
                              m.content, str(m.sent_date_time), m.status, m.channel, m.sender_role,
                              m.message_type, str(m.scheduled_date_time)))
        conn.execute("INSERT INTO service_request VALUES (?,?,?,?,?,?,?,?)",
                     (req.request_id, cust.person_id, rec.person_id, req.subject, req.description, req.status,
                      str(req.created_date), req.resolution))
        conn.execute("INSERT INTO automation_rule VALUES (?,?,?,?,?,?,?)",
                     (rule.rule_id, admin.person_id, mgr.person_id, rule.name, rule.frequency, rule.filters,
                      int(rule.is_active)))
        conn.execute("INSERT INTO report VALUES (?,?,?,?,?,?,?,?,?)",
                     (report.report_id, rule.rule_id, mgr.person_id, report.report_type, str(report.start_date),
                      str(report.end_date), str(report.generated_date), report.delivery_status, report.content))

        for table in ("person", "customer", "status_update", "booking", "test_drive", "conversation",
                      "message", "service_request", "report"):
            n = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            print(f"{table:16} {n} row(s)")
        row = conn.execute("""SELECT b.booking_id, b.status, COUNT(m.message_id) AS messages
                              FROM booking b LEFT JOIN message m USING (booking_id)
                              WHERE b.booking_id = 'B001' GROUP BY b.booking_id""").fetchone()
        print("read back:", dict(row))


if __name__ == "__main__":
    main()
