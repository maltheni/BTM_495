"""End-to-end tests of the web prototype: every page opens, and every normal, alternate and
exceptional flow of the seven use cases works through the web pages.

    python manage.py test portal
"""
import tempfile
from datetime import date, timedelta
from pathlib import Path

from django.test import Client, SimpleTestCase

import db
import models
import seed
import store
from portal import common

TOMORROW = (date.today() + timedelta(days=1)).isoformat()
IN_A_WEEK = (date.today() + timedelta(days=7)).isoformat()


class Base(SimpleTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = db.DB_PATH
        db.DB_PATH = Path(self.tmp.name) / "test.db"
        common._world = None
        common.reset_demo()
        self.c = Client()

    def tearDown(self):
        db.DB_PATH = self.old
        common._world = None
        self.tmp.cleanup()

    @property
    def w(self):
        return common.world()

    def sign_customer(self, email="marie.tremblay@mail.com"):
        r = self.c.post("/signin/", {"email": email, "password": "spinelli", "next": "/messages/"})
        self.assertEqual(r.status_code, 302)

    def sign_staff(self, pid):
        self.c.post("/staff/signin/", {"person": pid})

    def reloaded(self):
        return store.load_world()


class PagesOpen(Base):
    def test_every_page_opens_for_its_user(self):
        for url in ["/", "/vehicles/", "/vehicles/K260184/", "/test-drive/", "/test-drive/?vehicle=K260184", "/signin/",
                    "/staff/signin/", "/demo/", "/lang/FR/?next=/", "/vehicles/", "/lang/EN/?next=/"]:
            self.assertIn(self.c.get(url).status_code, (200, 302), url)
        self.sign_customer()
        for url in ["/messages/", "/messages/new/", "/messages/CV-1012/", "/track/", "/contact/", "/account/"]:
            self.assertEqual(self.c.get(url).status_code, 200, url)
        self.sign_staff("R-01")
        for url in ["/staff/requests/", "/staff/requests/?show=Confirmed", "/staff/requests/TD-1042/",
                    "/staff/requests/TD-1042/?deny=1", "/staff/requests/TD-1036/", "/staff/customers/",
                    "/staff/customers/?q=zzz", "/staff/customers/C-2041/", "/staff/customers/C-2041/edit/",
                    "/staff/customers/new/", "/staff/schedule/", "/staff/messages/", "/staff/messages/?tab=requests",
                    "/staff/messages/CV-1020/", "/staff/service/SR-1005/"]:
            self.assertEqual(self.c.get(url).status_code, 200, url)
        self.sign_staff("M-01")
        for url in ["/manager/customers/", "/manager/customers/C-2041/", "/manager/schedule/", "/manager/messages/",
                    "/manager/reports/"]:
            self.assertEqual(self.c.get(url).status_code, 200, url)
        self.sign_staff("A-01")
        for url in ["/admin-portal/rules/", "/admin-portal/reports/"]:
            self.assertEqual(self.c.get(url).status_code, 200, url)

    def test_pages_need_the_right_user(self):
        self.assertRedirects(self.c.get("/messages/"), "/signin/?next=/messages/", fetch_redirect_response=False)
        self.assertRedirects(self.c.get("/staff/requests/"), "/staff/signin/", fetch_redirect_response=False)
        self.sign_customer()
        self.assertRedirects(self.c.get("/staff/requests/"), "/staff/signin/", fetch_redirect_response=False)

    def test_wrong_password(self):
        r = self.c.post("/signin/", {"email": "marie.tremblay@mail.com", "password": "x"})
        self.assertContains(r, "The email or the password is not correct.")

    def test_french(self):
        self.c.get("/lang/FR/?next=/")
        r = self.c.get("/vehicles/")
        self.assertContains(r, "Véhicules")
        self.assertContains(r, "Réserver un essai routier")


FORM = {"vehicle": "K260184", "name": "Alex Roy", "email": "alex.roy@mail.com", "phone": "(514) 555-0199",
        "date": TOMORROW, "window": "Morning", "license": "R1234-567890-12", "consent": "on"}


class UC4TestDrive(Base):
    def test_validation_errors(self):
        r = self.c.post("/test-drive/", {**FORM, "email": "alex", "phone": "123", "date": date.today().isoformat(),
                                         "license": "12", "window": ""})
        for text in ("Enter a valid email address", "Enter a 10-digit phone number", "Choose a date from tomorrow onward",
                     "Choose a time window", "Enter the full license number", "Please fix the highlighted fields (5)"):
            self.assertContains(r, text)
        self.assertEqual(len(self.w.test_drives), 5)

    def test_new_customer_request(self):
        r = self.c.post("/test-drive/", FORM)
        self.assertEqual(r.status_code, 302)
        tid = r["Location"].rstrip("/").split("/")[-1]
        t = self.reloaded().test_drives[tid]
        self.assertEqual((t.status, t.customer.name, t.customer.lead_source), ("Booked", "Alex Roy", "online"))
        self.assertEqual(t.customer.get_current_stage(), "Lead")
        self.assertContains(self.c.get(r["Location"]), "Pending review")

    def test_existing_customer_no_duplicate(self):
        self.c.post("/test-drive/", {**FORM, "name": "Marie Tremblay", "email": "MARIE.TREMBLAY@mail.com"})
        self.assertEqual(len(self.w.customers), 5)
        self.assertEqual(len(self.w.customers["C-2041"].test_drives), 2)

    def test_crm_lost(self):
        common.save_settings({"crm_online": False, "reception_active": True})
        r = self.c.post("/test-drive/", FORM)
        self.assertContains(r, "Our booking service is not responding right now")
        self.assertContains(r, 'value="Alex Roy"')
        self.assertEqual(len(self.w.test_drives), 5)

    def test_confirm_needs_license_check_then_confirms(self):
        self.sign_staff("R-01")
        r = self.c.post("/staff/requests/TD-1042/", {"action": "confirm"})
        self.assertContains(r, "tick License verified")
        r = self.c.post("/staff/requests/TD-1042/", {"action": "confirm", "license_ok": "on"})
        self.assertEqual(r.status_code, 302)
        t = self.reloaded().test_drives["TD-1042"]
        self.assertEqual(t.status, "Confirmed")
        kinds = sorted((m.message_type, m.status) for m in t.messages)
        self.assertEqual(kinds, [("Confirmation", "Sent"), ("Reminder", "Scheduled")])

    def test_vehicle_not_available(self):
        self.c.post("/test-drive/", {**FORM, "vehicle": "K260302", "date": (date.today() + timedelta(days=2)).isoformat(),
                                     "window": "Afternoon"})        # same car and time as confirmed TD-1036
        tid = max(self.w.test_drives, key=lambda k: self.w.test_drives[k].created_date.isoformat() + k)
        self.sign_staff("R-01")
        r = self.c.get(f"/staff/requests/{tid}/")
        self.assertContains(r, "Not available at that time")
        r = self.c.post(f"/staff/requests/{tid}/", {"action": "confirm", "license_ok": "on"})
        self.assertContains(r, "The vehicle is not available at the requested time.")

    def test_deny(self):
        self.sign_staff("R-01")
        r = self.c.post("/staff/requests/TD-1042/deny/", {"reason": ""})
        self.assertEqual(self.w.test_drives["TD-1042"].status, "Booked")
        self.c.post("/staff/requests/TD-1042/deny/", {"reason": "Driver's license not valid", "note": "Expired."})
        t = self.reloaded().test_drives["TD-1042"]
        self.assertEqual(t.status, "Cancelled")
        self.assertTrue(any("Driver's license not valid" in m.content for m in t.messages))

    def test_plate_and_complete(self):
        self.sign_staff("R-01")
        r = self.c.post("/staff/requests/TD-1036/", {"action": "complete"})
        self.assertContains(r, "A test drive cannot be completed before it starts")
        self.c.post("/staff/requests/TD-1036/", {"action": "plate", "plate": "DLR-01"})
        self.assertEqual(self.reloaded().plates["DLR-01"].status, "Assigned")


class UC1Profiles(Base):
    def setUp(self):
        super().setUp()
        self.sign_staff("R-01")

    def test_search(self):
        self.assertContains(self.c.get("/staff/customers/?q=tremblay"), "Jean Tremblay")
        self.assertContains(self.c.get("/staff/customers/?q=555-0177"), "Marie Tremblay")
        self.assertContains(self.c.get("/staff/customers/?q=nobody"), "No matching customer")

    def test_edit_with_errors_then_save(self):
        url = "/staff/customers/C-2041/edit/"
        base = {"name": "Marie Tremblay", "email": "marie.tremblay@mail.com", "phone": "(514) 555-0177",
                "interest": "2026 Kia Sportage EX", "language": "English", "consent": "on", "manager": "M-01", "note": ""}
        r = self.c.post(url, {**base, "email": "marie", "phone": ""})
        self.assertContains(r, "Please fix the highlighted fields (2)")
        self.c.post(url, {**base, "phone": "(514) 555-0200", "language": "French", "note": "New phone"})
        c = self.reloaded().customers["C-2041"]
        self.assertEqual((c.phone_number, c.preferred_language, c.status_updates[-1].note), ("(514) 555-0200", "French", "New phone"))

    def test_new_customer_duplicate_then_create(self):
        data = {"name": "Louis Gagnon", "email": "l.gagnon@mail.com", "phone": "(438) 555-0199", "interest": "",
                "source": "walk-in", "language": "French", "consent": "", "manager": ""}
        r = self.c.post("/staff/customers/new/", data)
        self.assertContains(r, "Possible duplicate")
        self.assertEqual(len(self.w.customers), 5)
        r = self.c.post("/staff/customers/new/", {**data, "create_anyway": "1"})
        self.assertEqual(len(self.reloaded().customers), 6)


class UC2Schedule(Base):
    def setUp(self):
        super().setUp()
        self.sign_staff("R-01")

    def book(self, d, t):
        return self.c.post("/staff/schedule/", {"action": "book", "customer": "C-2041", "manager": "M-01",
                                                "date": d, "time": t, "duration": "30", "purpose": "Pricing"})

    def test_conflict_with_blocked_period(self):
        d = (date.today() + timedelta(days=3)).isoformat()            # Jordan blocked 9:00 to 12:00
        r = self.book(d, "10:00")
        self.assertContains(r, "already has an appointment or a blocked period")
        self.assertEqual(len(self.reloaded().appointments), 5)

    def test_book_move_cancel(self):
        self.book(IN_A_WEEK, "15:00")
        w = self.reloaded()
        a = [x for x in w.appointments.values() if x.purpose == "Pricing"][0]
        self.assertEqual(a.status, "Confirmed")
        new = (date.today() + timedelta(days=8)).isoformat()
        self.c.post("/staff/schedule/", {"action": "reschedule", "id": a.booking_id, "date": new, "time": "16:00"})
        self.assertEqual(self.reloaded().appointments[a.booking_id].status, "Rescheduled")
        self.c.post("/staff/schedule/", {"action": "cancel", "id": a.booking_id})
        self.assertEqual(self.reloaded().appointments[a.booking_id].status, "Cancelled")

    def test_manager_blocks_period(self):
        self.sign_staff("M-02")
        self.c.post("/manager/schedule/", {"action": "block", "date": IN_A_WEEK, "time": "09:00", "hours": "2"})
        self.assertTrue(any(a.purpose == "Unavailable" and a.customer is None and a.sales_manager.person_id == "M-02"
                            for a in self.reloaded().appointments.values()))


class UC6Messaging(Base):
    def test_full_conversation(self):
        self.sign_customer()
        r = self.c.post("/messages/new/", {"subject": "", "content": ""})
        self.assertContains(r, "Please fix the highlighted fields (2)")
        r = self.c.post("/messages/new/", {"subject": "Sportage availability", "content": "Is it available in white?"})
        cid = r["Location"].rstrip("/").split("/")[-1]
        self.assertContains(self.c.get(r["Location"]), "Message sent")
        self.sign_staff("R-01")
        self.assertContains(self.c.get("/staff/requests/"), "New message from")
        self.c.get(f"/staff/messages/{cid}/")
        self.assertEqual(self.reloaded().conversations[cid].messages[0].status, "Read")       # step 12
        self.c.post(f"/staff/messages/{cid}/", {"action": "reply", "content": "Yes, in Snow White Pearl."})
        self.sign_customer()
        self.assertContains(self.c.get("/messages/"), 'class="badge"')
        self.c.get(f"/messages/{cid}/")
        msgs = self.reloaded().conversations[cid].get_messages()
        self.assertEqual([m.status for m in msgs], ["Read", "Read"])                         # step 19
        self.c.post(f"/messages/{cid}/", {"action": "close"})
        self.assertEqual(self.reloaded().conversations[cid].status, "Closed")                 # step 20

    def test_not_delivered(self):
        common.save_settings({"crm_online": True, "reception_active": False})
        self.sign_customer()
        r = self.c.post("/messages/new/", {"subject": "Hello", "content": "Anyone there?"})
        self.assertContains(r, "Your message could not be delivered")
        self.assertContains(r, "Anyone there?")
        self.assertEqual(len(self.reloaded().customers["C-2041"].conversations), 1)

    def test_escalation(self):
        self.sign_staff("R-01")
        self.c.post("/staff/messages/CV-1020/", {"action": "escalate", "manager": "M-02"})
        conv = self.reloaded().conversations["CV-1020"]
        self.assertEqual((conv.status, conv.sales_manager.person_id), ("Escalated", "M-02"))
        self.sign_staff("M-02")
        self.assertContains(self.c.get("/manager/messages/"), "Seltos financing")


class UC5Tracking(Base):
    def test_status_update_shows_to_customer(self):
        self.sign_staff("M-01")
        r = self.c.post("/manager/customers/C-2041/", {"stage": "", "note": ""})
        self.assertContains(r, "Choose the new stage.")
        self.c.post("/manager/customers/C-2041/", {"stage": "Negotiation", "note": "Offer sent"})
        self.assertTrue(any("Negotiation" in n for n in models.OUTBOX))
        self.sign_customer()
        r = self.c.get("/track/")
        self.assertContains(r, "Offer sent")
        self.assertContains(r, 'class="now">Negotiation')

    def test_status_unavailable(self):
        self.sign_customer("olivier.martin@mail.com")
        self.assertContains(self.c.get("/track/"), "Your status is not available yet")


class UC7Service(Base):
    def test_request_lifecycle(self):
        self.sign_customer()
        self.assertContains(self.c.post("/contact/", {"subject": "", "description": ""}), "Some required information is missing")
        self.assertContains(self.c.post("/contact/", {"subject": "Keys", "description": "short"}), "Some information is not valid")
        self.c.post("/contact/", {"subject": "Second key", "description": "I need a second key for my car."})
        rid = [r for r in self.reloaded().service_requests.values() if r.subject == "Second key"][0].request_id
        self.sign_staff("R-01")
        self.c.post(f"/staff/service/{rid}/", {"action": "assign"})
        self.assertContains(self.c.post(f"/staff/service/{rid}/", {"action": "resolve", "resolution": ""}),
                            "Describe how the request was resolved.")
        self.c.post(f"/staff/service/{rid}/", {"action": "resolve", "resolution": "Key ordered"})
        self.c.post(f"/staff/service/{rid}/", {"action": "close"})
        self.assertEqual(self.reloaded().service_requests[rid].status, "Closed")


class UC3Reports(Base):
    def setUp(self):
        super().setUp()
        self.sign_staff("A-01")

    def test_run_rule_and_alternate_flows(self):
        self.c.post("/admin-portal/rules/", {"action": "run", "id": "AR-1001"})
        rep = [r for r in self.reloaded().reports.values() if r.automation_rule.rule_id == "AR-1001"][-1]
        self.assertEqual(rep.delivery_status, "Sent")
        self.assertIn("new customer", rep.content)
        self.c.post("/admin-portal/rules/", {"action": "create", "name": "Daily phone leads", "frequency": "Daily",
                                             "source": "phone", "manager": "M-01"})
        rid = [r for r in self.w.rules.values() if r.name == "Daily phone leads"][0].rule_id
        r = self.c.post("/admin-portal/rules/", {"action": "run", "id": rid}, follow=True)
        self.assertContains(r, "no data available")                                         # alternate flow 1
        self.c.post("/admin-portal/rules/", {"action": "create", "name": "Orphan", "frequency": "Weekly",
                                             "source": "", "manager": ""})
        rid = [r for r in self.w.rules.values() if r.name == "Orphan"][0].rule_id
        r = self.c.post("/admin-portal/rules/", {"action": "run", "id": rid}, follow=True)
        self.assertContains(r, "Report generation error")                                   # alternate flow 2
        self.assertEqual(len(self.reloaded().rules[rid].reports), 0)

    def test_rule_validation(self):
        r = self.c.post("/admin-portal/rules/", {"action": "create", "name": "", "frequency": "Hourly", "source": "x"})
        self.assertContains(r, "The rule was not created")
