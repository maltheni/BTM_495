"""Staff portal for the receptionist: UC4 (review requests), UC1 (profiles), UC2 (schedule),
UC6 (messages) and UC7 (service requests). Also the staff sign-in page."""
from datetime import date, datetime, timedelta

from django.shortcuts import redirect, render

import models
from models import Customer, Message, SalesAppointment, StatusUpdate, TestDrive

from .common import (LOCK, WINDOWS, car_name, check_email, check_phone, commit, current_user, flash, need,
                     parse_datetime, td_label, unread_customer_msgs, world)

REC_MENU = [("Test Drive Requests", "/staff/requests/", "requests"), ("Customers", "/staff/customers/", "customers"),
            ("Schedule", "/staff/schedule/", "schedule"), ("Messages", "/staff/messages/", "messages")]


def page(request, tpl, active, **ctx):
    return render(request, f"portal/{tpl}", {"portal": "staff", "menu": REC_MENU, "active": active,
                                             "staff_title": "Receptionist", "home_url": "/staff/requests/",
                                             "SOURCES": {"walk-in": "Walk-in", "phone": "Phone", "online": "Online"},
                                             "LANGS": ["English", "French"], **ctx})


# ------------------------------------------------------------------ sign-in (Entra ID in the final system)
def staff_signin(request):
    w = world()
    if request.method == "POST":
        pid = request.POST.get("person", "")
        for role, table, home in (("receptionist", w.receptionists, "/staff/requests/"),
                                  ("manager", w.managers, "/manager/customers/"), ("admin", w.admins, "/admin-portal/rules/")):
            if pid in table:
                request.session["role"], request.session["uid"] = role, pid
                return redirect(home)
    staff = [("Receptionist", p) for p in w.receptionists.values()] + \
            [("Sales Manager", p) for p in w.managers.values()] + [("Admin", p) for p in w.admins.values()]
    return render(request, "portal/staff_signin.html", {"staff": staff, "portal": "plain"})


def staff_signout(request):
    request.session.pop("role", None)
    request.session.pop("uid", None)
    return redirect("/staff/signin/")


# ------------------------------------------------------------------ UC4 test drive requests (R1 to R4)
@need("receptionist")
def requests_list(request):
    tab = request.GET.get("show", "Pending")
    drives = sorted(world().test_drives.values(), key=lambda t: t.scheduled_date_time)
    rows = [t for t in drives if td_label(t) == tab or (tab == "Confirmed" and t.status == "Rescheduled")]
    counts = {k: sum(1 for t in drives if td_label(t) == k) for k in ("Pending", "Confirmed", "Denied", "Completed")}
    return page(request, "requests.html", "requests", rows=rows, tab=tab, counts=counts, label=td_label,
                car=car_name, windows=WINDOWS)


@need("receptionist")
def request_review(request, tid):
    w, rec = world(), request.user_obj
    t = w.test_drives.get(tid)
    if t is None:
        return redirect("/staff/requests/")
    error = None
    if request.method == "POST":
        action = request.POST.get("action")
        try:
            if action == "confirm":
                if request.POST.get("license_ok") != "on":      # combination check: available AND license verified
                    raise ValueError("Check the driver's license and tick License verified before confirming.")
                if not t.is_vehicle_available():                # subflow 4s.2
                    raise ValueError("The vehicle is not available at the requested time.")
                if t.receptionist is None:
                    t.receptionist = rec
                    rec.test_drives.append(t)
                t.confirm()                                     # steps 11 to 16: confirmation and reminder
                if t.customer.get_current_stage() in ("Unavailable", "Lead"):
                    t.customer.add_status_update("Contacted", "Test drive confirmed by reception")
                commit()
                flash(request, "ok", f"Test drive {t.booking_id} confirmed",
                      f"{t.customer.name} was sent the confirmation and a reminder is scheduled for the day before.")
                return redirect("/staff/requests/?show=Confirmed")
            if action == "plate":
                plate = w.plates.get(request.POST.get("plate", ""))
                if plate is None:
                    raise ValueError("Choose a dealer plate.")
                t.assign_plate(plate)
                commit()
                flash(request, "ok", f"Plate {plate.plate_number} given out", "The customer can leave for the test drive.")
            elif action == "complete":
                t.complete()                                    # method specification 4
                commit()
                flash(request, "ok", "Test drive completed", "The plate is free again and the customer's file moved to Test drive.")
            elif action == "reschedule":
                new = parse_datetime(request.POST.get("date"), request.POST.get("time"))
                if new is None or new <= datetime.now():
                    raise ValueError("Choose a future date and time.")
                t.reschedule(new)                               # method specification 1
                commit()
                flash(request, "ok", "Test drive moved", f"New time: {new:%a %b %d, %H:%M}. The customer was told.")
            return redirect(f"/staff/requests/{tid}/")
        except ValueError as e:
            error = str(e)
    available = t.is_vehicle_available() if t.status in ("Booked", "Rescheduled", "Confirmed") else None
    history = list(reversed(t.customer.status_updates))
    others = [x for x in t.customer.test_drives if x is not t]
    free_plates = [p for p in w.plates.values() if p.status == "Free"]
    return page(request, "request_review.html", "requests", t=t, label=td_label(t), car=car_name(t.vehicle),
                available=available, history=history, others=others, error=error, plates=free_plates,
                started=t.scheduled_date_time <= datetime.now(), deny=request.GET.get("deny") == "1",
                windows=WINDOWS, reasons=DENY_REASONS)


DENY_REASONS = ["Driver's license not valid", "Driver's license expired", "Vehicle not available", "Incomplete information", "Other"]


@need("receptionist")
def request_deny(request, tid):
    t = world().test_drives.get(tid)
    if t is None or request.method != "POST":
        return redirect("/staff/requests/")
    reason, note = request.POST.get("reason", ""), request.POST.get("note", "").strip()
    if reason not in DENY_REASONS:
        flash(request, "bad", "Choose a reason", "The customer is told why the request is denied, so a reason is required.")
        return redirect(f"/staff/requests/{tid}/?deny=1")
    rec = request.user_obj
    if t.receptionist is None:
        t.receptionist = rec
        rec.test_drives.append(t)
    t.cancel()                                                  # M4 Figure 15: the test drive is refused
    conv = models._booking_conversation(t.customer, rec)
    text = f"Reason: {reason}." + (f"\n{note}" if note else "") + "\nYou can call us at (514) 555-0100 or send a new request."
    why = Message(message_id=models.new_id("MS"), conversation=conv, title="About your test drive request",
                  content=text, sender_role="Receptionist", channel="Email", test_drive=t)
    t.messages.append(why)
    models.try_send(why)
    commit()
    flash(request, "ok", f"Request {t.booking_id} denied", f"{t.customer.name} was told by email why the request was denied.")
    return redirect("/staff/requests/?show=Denied")


# ------------------------------------------------------------------ UC1 customer profiles (S1 to S5)
@need("receptionist")
def customers(request):
    w = world()
    q = request.GET.get("q", "").strip()
    if q:
        rows = [c for c in w.customers.values() if c.matches_search(q)]           # steps 2 and 3
    else:
        rows = list(w.customers.values())
    rows.sort(key=lambda c: (c.status_updates[-1].updated_date if c.status_updates else c.created_date), reverse=True)
    return page(request, "customers.html", "customers", rows=rows, q=q)


def _profile_ctx(c):
    upcoming = sorted([b for b in c.test_drives + c.sales_appointments
                       if b.status in ("Booked", "Confirmed", "Rescheduled")], key=lambda b: b.scheduled_date_time)
    return {"c": c, "history": list(reversed(c.status_updates)), "upcoming": upcoming,
            "label": lambda b: td_label(b) if isinstance(b, TestDrive) else b.status,
            "kind": lambda b: "Test drive" if isinstance(b, TestDrive) else "Sales appointment",
            "what": lambda b: car_name(b.vehicle) if isinstance(b, TestDrive) else b.purpose}


@need("receptionist")
def customer_profile(request, cid):
    c = world().customers.get(cid)
    if c is None:
        return redirect("/staff/customers/")
    return page(request, "customer_profile.html", "customers", **_profile_ctx(c))


def _profile_form(request, d, w, c=None):
    """Field checks shared by S3 (edit) and S5 (new customer)."""
    errors = {}
    if not d["name"]:
        errors["name"] = "Enter the customer's full name."
    if not d["email"]:
        errors["email"] = "Enter an email address."
    elif check_email(d["email"]):
        errors["email"] = check_email(d["email"])
    if not d["phone"]:
        errors["phone"] = "Enter a phone number."
    elif check_phone(d["phone"]):
        errors["phone"] = check_phone(d["phone"])
    if d["language"] not in ("English", "French"):
        errors["language"] = "Choose English or French."
    if "source" in d and d["source"] not in ("walk-in", "phone", "online"):
        errors["source"] = "Choose how the customer reached us."
    if d.get("manager") and d["manager"] not in w.managers:
        errors["manager"] = "Choose a sales manager."
    return errors


@need("receptionist")
def customer_edit(request, cid):
    w = world()
    c = w.customers.get(cid)
    if c is None:
        return redirect("/staff/customers/")
    d = {"name": c.name, "email": c.email, "phone": c.phone_number, "interest": c.vehicle_interest,
         "language": c.preferred_language, "consent": "on" if c.messaging_consent else "",
         "manager": c.assigned_to.person_id if c.assigned_to else "", "note": ""}
    errors = {}
    if request.method == "POST":
        d = {k: request.POST.get(k, "").strip() for k in d}
        errors = _profile_form(request, d, w, c)
        if not errors:
            c.name = d["name"]
            c.update_contact_info(d["email"], d["phone"])          # steps 4 to 11
            c.update_preferences(d["language"], d["consent"] == "on")
            c.vehicle_interest = d["interest"]
            if d["manager"] and (c.assigned_to is None or c.assigned_to.person_id != d["manager"]):
                c.assign_to(w.managers[d["manager"]])
            stage = c.get_current_stage() if c.status_updates else "Lead"
            c.status_updates.append(StatusUpdate(update_id=models.new_id("SU"), stage=stage, customer=c,
                                                 note=d["note"] or f"Profile updated by {request.user_obj.name}"))
            commit()
            flash(request, "ok", "Profile updated", f"The changes to {c.name}'s profile were saved and added to the history.")
            return redirect(f"/staff/customers/{cid}/")
    return page(request, "customer_form.html", "customers", d=d, errors=errors, c=c, managers=w.managers.values(),
                n_errors=len(errors), mode="edit")


@need("receptionist")
def customer_new(request):
    w = world()
    d = {"name": request.GET.get("q", ""), "email": "", "phone": "", "interest": "", "source": "walk-in",
         "language": "English", "consent": "", "manager": ""}
    if "@" in d["name"]:
        d["email"], d["name"] = d["name"], ""
    errors, dup = {}, None
    if request.method == "POST":
        d = {k: request.POST.get(k, "").strip() for k in d}
        errors = _profile_form(request, d, w)
        if not errors:
            phone = "".join(ch for ch in d["phone"] if ch.isdigit())[-10:]
            matches = [c for c in w.customers.values()
                       if c.email.lower() == d["email"].lower()
                       or "".join(ch for ch in c.phone_number if ch.isdigit())[-10:] == phone]
            if matches and request.POST.get("create_anyway") != "1":
                dup = matches[0]                                     # flow 3b: possible duplicate
            else:
                c = Customer(person_id=models.new_id("C-"), name=d["name"], vehicle_interest=d["interest"],
                             lead_source=d["source"])
                c.update_contact_info(d["email"], d["phone"])
                c.update_preferences(d["language"], d["consent"] == "on")
                manager = w.managers.get(d["manager"]) or min(w.managers.values(), key=lambda m: len(m.customers))
                c.assign_to(manager)
                w.customers[c.person_id] = c
                c.add_status_update("Lead", f"Profile created by {request.user_obj.name} ({d['source']})")
                commit()
                flash(request, "ok", "Customer profile created", f"{c.name} was given the customer ID {c.person_id}.")
                return redirect(f"/staff/customers/{c.person_id}/")
    return page(request, "customer_form.html", "customers", d=d, errors=errors, dup=dup, managers=w.managers.values(),
                n_errors=len(errors), mode="new")


# ------------------------------------------------------------------ UC2 schedule
def week_days(start):
    return [start + timedelta(days=i) for i in range(7)]


def schedule_ctx(w, request, mgr_id=None):
    mgr_id = mgr_id or request.GET.get("manager") or next(iter(w.managers))
    mgr = w.managers.get(mgr_id) or next(iter(w.managers.values()))
    try:
        start = date.fromisoformat(request.GET.get("from", ""))
    except ValueError:
        start = date.today()
    days = week_days(start)
    appts = [a for a in mgr.get_appointments() if days[0] <= a.scheduled_date_time.date() <= days[-1]]
    by_day = [(d, [a for a in appts if a.scheduled_date_time.date() == d]) for d in days]
    return {"mgr": mgr, "managers": w.managers.values(), "by_day": by_day, "start": start,
            "prev": (start - timedelta(days=7)).isoformat(), "nextw": (start + timedelta(days=7)).isoformat()}


def book_appointment(w, rec, data):
    """UC2 S-1: create the appointment, check the manager is free (S-1a), then confirm it."""
    cust = w.customers.get(data.get("customer", ""))
    mgr = w.managers.get(data.get("manager", ""))
    when = parse_datetime(data.get("date"), data.get("time"))
    errors = {}
    if cust is None:
        errors["customer"] = "Choose a customer."
    if mgr is None:
        errors["manager"] = "Choose a sales manager."
    if when is None:
        errors["when"] = "Choose a date and a time."
    elif when <= datetime.now():
        errors["when"] = "Choose a date and time in the future."
    elif not (9 <= when.hour < 20):
        errors["when"] = "Appointments are between 9:00 and 20:00."
    if not data.get("purpose", "").strip():
        errors["purpose"] = "Enter the purpose of the appointment."
    if errors:
        return None, errors
    a = SalesAppointment(booking_id=models.new_id("SA-"), scheduled_date_time=when, duration_minutes=int(data.get("duration") or 30),
                         purpose=data["purpose"].strip(), customer=cust, receptionist=rec, sales_manager=mgr)
    if not a.is_manager_available():                              # S-1a: the slot conflicts
        for owner, attr in ((cust, "sales_appointments"), (rec, "sales_appointments"), (mgr, "appointments")):
            getattr(owner, attr).remove(a)
        return None, {"when": f"{mgr.name} already has an appointment or a blocked period at that time. Choose another slot."}
    a.confirm()                                                    # confirmation and reminder (specification 2)
    w.appointments[a.booking_id] = a
    return a, {}


@need("receptionist")
def schedule(request):
    w, rec = world(), request.user_obj
    data, errors = {"customer": request.GET.get("customer", ""), "manager": request.GET.get("manager", ""),
                    "date": "", "time": "", "duration": "30", "purpose": ""}, {}
    if request.method == "POST":
        action = request.POST.get("action")
        a = w.appointments.get(request.POST.get("id", ""))
        try:
            if action == "book":
                data = {k: request.POST.get(k, "").strip() for k in data}
                appt, errors = book_appointment(w, rec, data)
                if appt:
                    commit()
                    flash(request, "ok", "Appointment booked and confirmed",
                          f"{appt.customer.name} with {appt.sales_manager.name}, {appt.scheduled_date_time:%a %b %d at %H:%M}. "
                          "The confirmation was sent and a reminder is scheduled.")
                    return redirect(f"/staff/schedule/?manager={appt.sales_manager.person_id}&from={appt.scheduled_date_time.date()}")
            elif a and action == "reschedule":
                new = parse_datetime(request.POST.get("date"), request.POST.get("time"))
                if new is None or new <= datetime.now():
                    raise ValueError("Choose a future date and time.")
                a.reschedule(new)                                  # method specification 1 (S-2)
                commit()
                flash(request, "ok", "Appointment moved", f"New time: {new:%a %b %d at %H:%M}. The customer was told.")
                return redirect(f"/staff/schedule/?manager={a.sales_manager.person_id}&from={new.date()}")
            elif a and action == "cancel":
                a.cancel()                                         # S-2 cancel
                commit()
                flash(request, "ok", "Appointment cancelled", "The customer was told and the reminder was cancelled.")
            elif a and action == "complete":
                a.complete()
                commit()
                flash(request, "ok", "Appointment completed", "The customer's file moved to Contacted.")
            if a:
                return redirect(f"/staff/schedule/?manager={a.sales_manager.person_id}&from={request.POST.get('from', '')}")
        except ValueError as e:
            flash(request, "bad", "This change was not made", str(e))
            return redirect(request.get_full_path())
    ctx = schedule_ctx(w, request, data.get("manager") or None)
    return page(request, "schedule.html", "schedule", **ctx, customers=sorted(w.customers.values(), key=lambda c: c.name),
                d=data, errors=errors, now=datetime.now(), can_book=True)


# ------------------------------------------------------------------ UC6 messages and UC7 service requests
@need("receptionist")
def staff_messages(request):
    rec, w = request.user_obj, world()
    tab = request.GET.get("tab", "conversations")
    convs = [c for c in rec.get_conversations() if c.subject not in ("Status updates",)]   # getConversations()
    rows = [(c, c.get_messages()[-1] if c.messages else None, len(unread_customer_msgs(c))) for c in convs]
    reqs = sorted(w.service_requests.values(), key=lambda r: (r.status in ("Resolved", "Closed"), r.created_date))
    return page(request, "staff_messages.html", "messages", rows=rows, tab=tab, reqs=reqs,
                open_reqs=sum(1 for r in reqs if r.status in ("Open", "In progress")))


@need("receptionist")
def staff_conversation(request, cid):
    rec, w = request.user_obj, world()
    conv = w.conversations.get(cid)
    if conv is None or conv not in rec.conversations:
        return redirect("/staff/messages/")
    error, reply = None, ""
    if request.method == "POST":
        action = request.POST.get("action")
        try:
            if action == "escalate":
                mgr = w.managers.get(request.POST.get("manager", ""))
                if mgr is None:
                    raise ValueError("Choose the sales manager to escalate to.")
                conv.escalate_to(mgr)                            # alternate flow 6a (M4 Figure 22)
                commit()
                flash(request, "ok", f"Escalated to {mgr.name}", "The sales manager was notified and sees the conversation.")
                return redirect(f"/staff/messages/{cid}/")
            reply = request.POST.get("content", "").strip()
            if conv.status == "Closed":
                raise ValueError("This conversation is closed.")
            if not reply:
                raise ValueError("Write a reply before sending.")
            msg = Message(message_id=models.new_id("MS"), conversation=conv, title=f"Re: {conv.subject}",
                          content=reply, sender_role="Receptionist")
            msg.send()                                           # steps 13 to 17, then notification (18)
            commit()
            flash(request, "ok", "Reply sent", f"{conv.customer.name} was notified.")
            return redirect(f"/staff/messages/{cid}/")
        except ValueError as e:
            error = str(e)
    for m in unread_customer_msgs(conv):
        m.mark_as_read()                                         # step 12
    commit()
    return page(request, "staff_conversation.html", "messages", conv=conv, msgs=conv.get_messages(), error=error,
                reply=reply, managers=w.managers.values())


@need("receptionist")
def service_request(request, rid):
    w, rec = world(), request.user_obj
    r = w.service_requests.get(rid)
    if r is None:
        return redirect("/staff/messages/?tab=requests")
    error = None
    if request.method == "POST":
        action = request.POST.get("action")
        try:
            if action == "assign":
                r.assign_to(rec)
                flash(request, "ok", "Request assigned to you", "Its status is now In progress.")
            elif action == "resolve":
                text = request.POST.get("resolution", "").strip()
                if not text:
                    raise ValueError("Describe how the request was resolved.")
                r.resolve(text)
                flash(request, "ok", "Request resolved", "You can close it once the customer confirms.")
            elif action == "close":
                r.close()
                flash(request, "ok", "Request closed")
            commit()
            return redirect(f"/staff/service/{rid}/")
        except ValueError as e:
            error = str(e)
    return page(request, "service_request.html", "messages", r=r, error=error)
