"""Customer portal: UC4 (book a test drive), UC5 (track my purchase), UC6 (messages), UC7 (contact us)."""
from datetime import date, datetime, timedelta

from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

import models
from models import Conversation, Customer, Message, ServiceRequest, StatusUpdate, TestDrive

from .common import (CATALOGUE, LOCK, WINDOWS, car_name, check_email, check_license, check_phone, commit,
                     current_user, flash, need, parse_date, settings, td_label, window_of, world)


def page(request, tpl, active, **ctx):
    return render(request, f"portal/{tpl}", {"active": active, **ctx})


def vehicles_on_sale():
    return [v for v in world().vehicles.values() if v.is_available]


# ------------------------------------------------------------------ home and vehicles
def home(request):
    return page(request, "home.html", "", cars=vehicles_on_sale()[:3], cat=CATALOGUE)


def vehicle_list(request):
    return page(request, "vehicles.html", "vehicles", cars=vehicles_on_sale(), cat=CATALOGUE)


def vehicle_detail(request, stock):
    v = world().vehicles.get(stock)
    if v is None or not v.is_available:
        flash(request, "warn", "This vehicle is no longer available", "Choose another vehicle below.")
        return redirect("/vehicles/")
    return page(request, "vehicle_detail.html", "vehicles", v=v, info=CATALOGUE.get(stock, {}), name=car_name(v))


# ------------------------------------------------------------------ sign in
def signin(request):
    w, err, email = world(), None, ""
    nxt = request.GET.get("next") or request.POST.get("next") or "/messages/"
    if request.method == "POST":
        email = request.POST.get("email", "").strip()
        password = request.POST.get("password", "")
        found = [c for c in w.customers.values() if c.email.lower() == email.lower()]
        if not email or not password:
            err = "Enter your email and your password."
        elif not found or password != "spinelli":
            err = "The email or the password is not correct."
        else:
            request.session["role"], request.session["uid"] = "customer", found[0].person_id
            flash(request, "ok", f"Welcome back, {found[0].name.split()[0]}")
            return redirect(nxt if nxt.startswith("/") else "/")
    return page(request, "signin.html", "", err=err, email=email, next=nxt)


def signout(request):
    request.session.pop("role", None)
    request.session.pop("uid", None)
    return redirect("/")


@need("customer")
def account(request):
    return page(request, "account.html", "", c=request.user_obj)


# ------------------------------------------------------------------ UC4 test drive request
def test_drive_form(request):
    w = world()
    role, me = current_user(request)
    stock = request.GET.get("vehicle") or request.POST.get("vehicle", "")
    v = w.vehicles.get(stock)
    data = {"vehicle": stock, "name": "", "email": "", "phone": "", "date": "", "window": "", "license": "", "consent": ""}
    if role == "customer":
        data.update(name=me.name, email=me.email, phone=me.phone_number, consent="on" if me.messaging_consent else "")
    errors, crm_down = {}, False
    if request.method == "POST":
        data = {k: request.POST.get(k, "").strip() for k in data}
        # validation of the form (Milestone 6: existence, data type, range and validity checks)
        if not w.vehicles.get(data["vehicle"]):
            errors["vehicle"] = "Choose a vehicle."
        for k, label in (("name", "full name"), ("email", "email"), ("phone", "phone number"),
                         ("license", "driver's license number")):
            if not data[k]:
                errors[k] = f"Enter your {label}."
        if data["email"] and not errors.get("email"):
            e = check_email(data["email"])
            if e:
                errors["email"] = e
        if data["phone"] and check_phone(data["phone"]):
            errors["phone"] = check_phone(data["phone"])
        d = parse_date(data["date"])
        if not data["date"]:
            errors["date"] = "Choose a date."
        elif d is None or d <= date.today():
            errors["date"] = "Choose a date from tomorrow onward."
        elif d > date.today() + timedelta(days=60):
            errors["date"] = "Choose a date in the next 60 days."
        if data["window"] not in WINDOWS:
            errors["window"] = "Choose a time window."
        if data["license"] and check_license(data["license"]):
            errors["license"] = check_license(data["license"])
        if not errors and not settings()["crm_online"]:
            crm_down = True                                     # M4 Figure 16: nothing is recorded
        if not errors and not crm_down:
            with LOCK:
                t = record_request(w, data, d)
                commit()
            request.session["last_request"] = t.booking_id
            return redirect(f"/test-drive/received/{t.booking_id}/")
        v = w.vehicles.get(data["vehicle"])
    return page(request, "test_drive_form.html", "testdrive", d=data, errors=errors, crm_down=crm_down, v=v,
                info=CATALOGUE.get(v.stock_number, {}) if v else {}, name=car_name(v), windows=WINDOWS,
                cars=vehicles_on_sale(), tomorrow=(date.today() + timedelta(days=1)).isoformat(), n_errors=len(errors))


def record_request(w, data, d) -> TestDrive:
    """UC4 steps 1 to 6 (M4 Figures 13 and 14): find or create the customer, then record the request."""
    existing = [c for c in w.customers.values() if c.email.lower() == data["email"].lower()]
    if existing:                                              # Figure 14: existing profile, no duplicate
        c = existing[0]
        if data["consent"] and not c.messaging_consent:
            c.update_preferences(c.preferred_language, True)
    else:                                                     # Figure 13 steps 2 to 5: new customer
        c = Customer(person_id=models.new_id("C-"), name=data["name"], email=data["email"], phone_number=data["phone"],
                     vehicle_interest=car_name(w.vehicles[data["vehicle"]]), lead_source="online",
                     messaging_consent=bool(data["consent"]))
        w.customers[c.person_id] = c
        manager = min(w.managers.values(), key=lambda m: len(m.customers))
        c.assign_to(manager)
        c.add_status_update("Lead", "Online test drive request")
    start = datetime.combine(d, datetime.min.time()).replace(hour=WINDOWS[data["window"]][0])
    t = TestDrive(booking_id=models.new_id("TD-"), scheduled_date_time=start,
                  driver_license_number=data["license"].upper(), customer=c, vehicle=w.vehicles[data["vehicle"]])
    t.departure_time = start
    w.test_drives[t.booking_id] = t
    return t


def test_drive_received(request, tid):
    t = world().test_drives.get(tid)
    if t is None:
        return redirect("/test-drive/")
    w = window_of(t.scheduled_date_time)
    return page(request, "test_drive_received.html", "testdrive", t=t, name=car_name(t.vehicle),
                window=f"{w} ({WINDOWS[w][1]})" if w else f"{t.scheduled_date_time:%H:%M}")


# ------------------------------------------------------------------ UC5 track my purchase
STAGE_INFO = {"Lead": "We received your request.", "Contacted": "A sales manager contacted you.",
              "Test drive": "You test drove a vehicle.", "Negotiation": "An offer is being prepared or discussed.",
              "Closed": "Your purchase is complete."}


@need("customer")
def track(request):
    c = request.user_obj
    stage = c.get_current_stage()                             # UC5 S-1, or "Unavailable" (A-1)
    idx = StatusUpdate.STAGES.index(stage) if stage in StatusUpdate.STAGES else -1
    bookings = sorted([b for b in c.test_drives + c.sales_appointments if b.status != "Cancelled"],
                      key=lambda b: b.scheduled_date_time, reverse=True)
    return page(request, "track.html", "track", c=c, stage=stage, idx=idx, stages=StatusUpdate.STAGES,
                info=STAGE_INFO, history=list(reversed(c.status_updates)),
                bookings=[(b, ("Pending review" if b.status == "Booked" else td_label(b)) if isinstance(b, TestDrive) else b.status)
                          for b in bookings])


# ------------------------------------------------------------------ UC6 messages
@need("customer")
def messages_list(request):
    c = request.user_obj
    convs = sorted(c.conversations, key=lambda v: (v.status == "Closed", -(v.last_activity_date.toordinal())))
    rows = [(v, v.get_messages()[-1] if v.messages else None,
             sum(1 for m in v.messages if m.sender_role != "Customer" and m.status in ("Sent", "Delivered"))) for v in convs]
    return page(request, "messages.html", "messages", rows=rows)


@need("customer")
def message_new(request):
    c, w = request.user_obj, world()
    d, errors, failed = {"subject": "", "content": ""}, {}, False
    if request.method == "POST":
        d = {k: request.POST.get(k, "").strip() for k in d}
        if not d["subject"]:
            errors["subject"] = "Enter a subject."
        if not d["content"]:
            errors["content"] = "Write your message."
        elif len(d["content"]) > 2000:
            errors["content"] = "Your message is too long (2,000 characters at most)."
        if not errors:
            conv = Conversation(conversation_id=models.new_id("CV-"), subject=d["subject"], customer=c)   # steps 1 to 3
            if settings()["reception_active"]:
                conv.assign_to(next(iter(w.receptionists.values())))
            msg = Message(message_id=models.new_id("MS"), conversation=conv, title=d["subject"], content=d["content"])
            try:
                msg.send()                                    # steps 4 to 8 (validate, send, addMessage)
            except ValueError:
                failed = True                                 # 5a: markFailed(), nothing is added
                c.conversations.remove(conv)
            else:
                w.conversations[conv.conversation_id] = conv
                commit()
                request.session["just_sent"] = conv.conversation_id
                return redirect(f"/messages/{conv.conversation_id}/")
    return page(request, "message_new.html", "messages", d=d, errors=errors, failed=failed, n_errors=len(errors))


@need("customer")
def conversation(request, cid):
    c = request.user_obj
    conv = next((v for v in c.conversations if v.conversation_id == cid), None)
    if conv is None:
        return redirect("/messages/")
    just_sent = request.session.pop("just_sent", None) == cid
    error, follow = None, ""
    if request.method == "POST":
        if request.POST.get("action") == "close":
            conv.close()                                      # step 20
            commit()
            flash(request, "ok", "Conversation closed",
                  "Thank you. You can start a new conversation at any time from Messages.")
            return redirect(f"/messages/{cid}/")
        follow = request.POST.get("content", "").strip()
        if conv.status == "Closed":
            error = "This conversation is closed. Start a new message instead."
        elif not follow:
            error = "Write your message before sending."
        else:
            msg = Message(message_id=models.new_id("MS"), conversation=conv, title=f"Re: {conv.subject}", content=follow)
            try:
                msg.send()                                    # follow-up: back to step 4
            except ValueError as e:
                error = f"Your message was not delivered: {e}. Your text is kept, try again later."
            else:
                commit()
                flash(request, "ok", "Message sent", "The reception team will answer here.")
                return redirect(f"/messages/{cid}/")
    unread = [m for m in conv.messages if m.sender_role != "Customer" and m.status in ("Sent", "Delivered")]
    for m in unread:
        m.mark_as_read()                                      # step 19
    if unread:
        commit()
    return page(request, "conversation.html", "messages", conv=conv, msgs=conv.get_messages(), just_sent=just_sent,
                error=error, follow=follow, is_system=conv.subject in ("Bookings", "Status updates"))


# ------------------------------------------------------------------ UC7 contact us
@need("customer")
def contact(request):
    c = request.user_obj
    d, errors, invalid = {"subject": "", "description": ""}, {}, None
    if request.method == "POST":
        d = {k: request.POST.get(k, "").strip() for k in d}
        req = ServiceRequest(request_id=models.new_id("SR-"), subject=d["subject"], description=d["description"], customer=c)
        try:
            req.submit()                                      # UC7: validates the form and records the request
        except ValueError as e:
            text = str(e)
            if text.startswith("Missing"):                    # A-1 missing required information
                if not d["subject"]:
                    errors["subject"] = "Enter a subject."
                if not d["description"]:
                    errors["description"] = "Describe your request."
            else:                                             # A-2 invalid information
                errors["description"] = "Give a few more details (at least 10 characters)."
                invalid = text
        else:
            world().service_requests[req.request_id] = req
            commit()
            flash(request, "ok", f"Request {req.request_id} received",
                  "The reception team will contact you. You can follow its status below.")
            return redirect("/contact/")
    mine = sorted(c.service_requests, key=lambda r: r.created_date, reverse=True)
    return page(request, "contact.html", "contact", d=d, errors=errors, invalid=invalid, mine=mine, n_errors=len(errors))
