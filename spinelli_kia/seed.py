"""Demo data for the final prototype: the same people, vehicles and example records as the
Milestone 6 wireframes (Marie Tremblay, the 2026 Kia Sportage EX, Sam Lee, Jordan Roy...).

    python seed.py        # (re)create spinelli_kia.db with fresh demo data

Dates are relative to today, so the demo always shows upcoming test drives and appointments.
"""
from datetime import date, datetime, time, timedelta

import db
import models
import store
from models import (Admin, AutomationRule, Conversation, Customer, DealerPlate, Message, Receptionist,
                    SalesAppointment, SalesManager, ServiceRequest, StatusUpdate, TestDrive, Vehicle)

TODAY = date.today()


def at(days, hour, minute=0):
    return datetime.combine(TODAY + timedelta(days=days), time(hour, minute))


def history(c, *steps):
    """Add past status updates without sending notifications (history before the system went live)."""
    for days_ago, stage, note in steps:
        c.status_updates.append(StatusUpdate(update_id=models.new_id("SU"), stage=stage, note=note,
                                             updated_date=TODAY - timedelta(days=days_ago), customer=c))


def build() -> store.World:
    models._ids = __import__("itertools").count(1000)
    models.OUTBOX.clear()
    w = store.World()

    # ---------------------------------------------------------------- staff
    sam = Receptionist(person_id="R-01", name="Sam Lee", email="sam.lee@spinellikia.ca",
                       phone_number="(514) 555-0100", shift="Morning")
    jordan = SalesManager(person_id="M-01", name="Jordan Roy", email="jordan.roy@spinellikia.ca",
                          phone_number="(514) 555-0110", sales_team="New vehicles")
    nadia = SalesManager(person_id="M-02", name="Nadia Haddad", email="nadia.haddad@spinellikia.ca",
                         phone_number="(514) 555-0111", sales_team="Pre-owned vehicles")
    ana = Admin(person_id="A-01", name="Ana Costa", email="ana.costa@spinellikia.ca",
                phone_number="(514) 555-0120", access_level="Full")
    w.receptionists[sam.person_id] = sam
    w.managers.update({jordan.person_id: jordan, nadia.person_id: nadia})
    w.admins[ana.person_id] = ana

    # ------------------------------------------------------------- vehicles
    cars = [("K260184", "KNDPUCDF6T7184001", "Sportage EX", 2026), ("K260211", "KNDEUCAA2T7211002", "Seltos EX", 2026),
            ("K260157", "KNDC4DLC1T5157003", "EV6 Wind", 2026), ("K260302", "5XYP5DGC4TG302004", "Telluride SX", 2026),
            ("K260245", "5XYRK4JF6TG245005", "Sorento LX", 2026), ("K260090", "KNDNE5H38T6090006", "Carnival EX", 2026),
            ("K260133", "5XXG64J20TG133007", "K5 GT-Line", 2026), ("U240512", "KNDCB3LC5R5512008", "Niro Hybrid EX", 2024)]
    for stock, vin, model, year in cars:
        w.vehicles[stock] = Vehicle(stock_number=stock, vin=vin, make="Kia", model=model, year=year)
    w.vehicles["U240512"].is_available = False            # sold, kept for history
    for p in ("DLR-01", "DLR-02", "DLR-03"):
        w.plates[p] = DealerPlate(plate_number=p)

    # ------------------------------------------------------------ customers
    def customer(cid, name, email, phone, interest, lang, consent, source, days_ago, mgr):
        c = Customer(person_id=cid, name=name, email=email, phone_number=phone, vehicle_interest=interest,
                     preferred_language=lang, messaging_consent=consent, lead_source=source,
                     created_date=TODAY - timedelta(days=days_ago))
        c.assign_to(mgr)
        w.customers[cid] = c
        return c

    marie = customer("C-2041", "Marie Tremblay", "marie.tremblay@mail.com", "(514) 555-0177",
                     "2026 Kia Sportage EX", "English", True, "online", 6, jordan)
    history(marie, (6, "Lead", "Online test drive request for the Sportage EX"),
            (4, "Contacted", "Called back, interested in the EX trim in white"))
    louis = customer("C-1877", "Louis Gagnon", "l.gagnon@mail.com", "(438) 555-0164",
                     "2026 Kia EV6 Wind", "French", True, "walk-in", 21, jordan)
    history(louis, (21, "Lead", "Walk-in, asked about EV range"), (15, "Contacted", "Sent the EV6 brochure"),
            (9, "Test drive", "Drove the EV6 Wind"), (3, "Negotiation", "Offer sent for the EV6 Wind"))
    priya = customer("C-2033", "Priya Nair", "priya.nair@mail.com", "(514) 555-0142",
                     "2026 Kia Seltos EX", "English", True, "online", 3, nadia)
    history(priya, (3, "Lead", "Online inquiry about Seltos financing"))
    jean = customer("C-1650", "Jean Tremblay", "j.tremblay@mail.com", "(450) 555-0132",
                    "2026 Kia Telluride", "French", False, "phone", 40, nadia)
    history(jean, (40, "Lead", "Phone call about the Telluride"))
    olivier = customer("C-2050", "Olivier Martin", "olivier.martin@mail.com", "(514) 555-0188",
                       "2026 Kia Sorento LX", "French", True, "online", 1, jordan)   # no history yet: UC5 "Unavailable"

    # -------------------------------------------------------- test drives
    def td(tid, cust, stock, days, hour, license_no, created_days_ago=1):
        t = TestDrive(booking_id=tid, scheduled_date_time=at(days, hour), driver_license_number=license_no,
                      customer=cust, vehicle=w.vehicles[stock], created_date=TODAY - timedelta(days=created_days_ago))
        t.departure_time = t.scheduled_date_time
        w.test_drives[tid] = t
        return t

    td("TD-1042", marie, "K260184", 5, 9, "T6524-180590-07", 0)          # pending: the M6 scenario
    td("TD-1041", louis, "K260157", 4, 12, "G2541-030385-02")
    td("TD-1039", priya, "K260211", 3, 17, "N3310-221193-05", 2)
    done = td("TD-1030", louis, "K260157", -9, 12, "G2541-030385-02", 12)
    done.receptionist = sam
    sam.test_drives.append(done)
    done.status, done.return_time = "Completed", at(-9, 12, 45)
    confirmed = td("TD-1036", jean, "K260302", 2, 12, "T6510-120478-03", 4)
    confirmed.receptionist = sam
    sam.test_drives.append(confirmed)
    confirmed.status = "Confirmed"

    # ----------------------------------------------- sales appointments (UC2)
    def appt(aid, cust, mgr, days, hour, purpose, status="Confirmed", minutes=30):
        a = SalesAppointment(booking_id=aid, scheduled_date_time=at(days, hour), duration_minutes=minutes,
                             purpose=purpose, customer=cust, receptionist=sam if cust else None, sales_manager=mgr)
        a.status = status
        w.appointments[aid] = a
        return a

    appt("SA-1050", louis, jordan, 1, 10, "Review the EV6 offer")
    appt("SA-1051", marie, jordan, 6, 14, "Pricing and trade-in")
    appt("SA-1052", priya, nadia, 2, 11, "Financing options")
    appt("SA-1053", None, jordan, 3, 9, "Unavailable", minutes=180)       # blocked period (S-3)
    appt("SA-1040", jean, nadia, -5, 15, "Telluride walk-around", status="Completed")

    # ------------------------------------------------------ messages (UC6)
    def thread(cid, cust, subject, days_ago, msgs, status="Open"):
        c = Conversation(conversation_id=cid, subject=subject, customer=cust, status=status,
                         start_date=TODAY - timedelta(days=days_ago), last_activity_date=TODAY - timedelta(days=days_ago))
        c.assign_to(sam)
        for i, (role, title, text, read) in enumerate(msgs):
            m = Message(message_id=models.new_id("MS"), title=title, content=text, sender_role=role,
                        conversation=c, status="Read" if read else "Sent",
                        sent_date_time=datetime.combine(TODAY - timedelta(days=days_ago), time(10 + i, 12)))
            c.messages.append(m)
        w.conversations[cid] = c
        return c

    thread("CV-1020", priya, "Seltos financing", 1,
           [("Customer", "Seltos financing", "Hi, what financing rates do you offer on the 2026 Seltos EX over 60 months?", False)])
    thread("CV-1012", marie, "Winter tires", 12,
           [("Customer", "Winter tires", "Do you install winter tires on new vehicles?", True),
            ("Receptionist", "Re: Winter tires", "Yes, we can install them at delivery. Ask your sales manager for a quote.", True)],
           status="Closed")

    # ---------------------------------------------- service requests (UC7)
    sr = ServiceRequest(request_id="SR-1005", subject="Paperwork for my purchase",
                        description="I have not received the registration papers for my Telluride yet.", customer=jean)
    sr.submit()
    sr.created_date = TODAY - timedelta(days=2)
    w.service_requests[sr.request_id] = sr

    # ----------------------------------------------- automation rules (UC3)
    r1 = AutomationRule(rule_id="AR-1001", name="Weekly online leads", frequency="Weekly",
                        filters="lead_source=online", sales_manager=jordan)
    r2 = AutomationRule(rule_id="AR-1002", name="Monthly walk-in leads", frequency="Monthly",
                        filters="lead_source=walk-in", sales_manager=nadia)
    for r in (r1, r2):
        ana.manage_rule(r)
        w.rules[r.rule_id] = r
    models.OUTBOX.clear()
    w.refresh()
    return w


def reset(path=None) -> store.World:
    path = path or db.DB_PATH
    if path.exists():
        path.unlink()
    world = build()
    store.save_world(world, path)
    return store.load_world(path)


if __name__ == "__main__":
    w = reset()
    print(f"Demo data created in {db.DB_PATH.name}: {len(w.customers)} customers, {len(w.test_drives)} test drives, "
          f"{len(w.appointments)} appointments, {len(w.conversations)} conversations.")
