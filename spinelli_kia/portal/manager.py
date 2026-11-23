"""Sales manager portal (UC5 status updates, UC2 schedule and blocked periods, UC6 escalations, UC3 reports)
and admin portal (UC3 automation rules and reports)."""
from datetime import date, datetime, timedelta

from django.shortcuts import redirect, render

import models
from models import AutomationRule, SalesAppointment, StatusUpdate

from .common import commit, flash, need, parse_datetime, world
from .staff import _profile_ctx, schedule_ctx

MGR_MENU = [("My Customers", "/manager/customers/", "customers"), ("Schedule", "/manager/schedule/", "schedule"),
            ("Messages", "/manager/messages/", "messages"), ("Reports", "/manager/reports/", "reports")]
ADMIN_MENU = [("Automation Rules", "/admin-portal/rules/", "rules"), ("Reports", "/admin-portal/reports/", "reports")]


def mpage(request, tpl, active, **ctx):
    return render(request, f"portal/{tpl}", {"portal": "staff", "menu": MGR_MENU, "active": active,
                                             "staff_title": "Sales Manager", "home_url": "/manager/customers/", **ctx})


def apage(request, tpl, active, **ctx):
    return render(request, f"portal/{tpl}", {"portal": "staff", "menu": ADMIN_MENU, "active": active,
                                             "staff_title": "Admin", "home_url": "/admin-portal/rules/", **ctx})


# ------------------------------------------------------------------ UC5: customers and status updates
@need("manager")
def my_customers(request):
    me = request.user_obj
    rows = sorted(me.get_customers(), key=lambda c: c.name)
    return mpage(request, "manager_customers.html", "customers", rows=rows)


@need("manager")
def manager_customer(request, cid):
    me = request.user_obj
    c = world().customers.get(cid)
    if c is None or c not in me.customers:
        return redirect("/manager/customers/")
    error, d = None, {"stage": "", "note": ""}
    if request.method == "POST":
        d = {k: request.POST.get(k, "").strip() for k in d}
        if d["stage"] not in StatusUpdate.STAGES:
            error = "Choose the new stage."
        elif not d["note"]:
            error = "Add a short note for the history (what happened)."
        else:
            c.add_status_update(d["stage"], d["note"])           # UC5 S-2 (M4 Figure 18): customer notified
            commit()
            told = "The customer was notified." if c.messaging_consent else \
                "The customer did not agree to messages, so no notification was sent."
            flash(request, "ok", f"Status updated to {d['stage']}", told)
            return redirect(f"/manager/customers/{cid}/")
    return mpage(request, "manager_customer.html", "customers", **_profile_ctx(c), stages=StatusUpdate.STAGES,
                 error=error, d=d)


# ------------------------------------------------------------------ UC2: schedule and blocked periods (S-3)
@need("manager")
def manager_schedule(request):
    me, w = request.user_obj, world()
    errors, d = {}, {"date": "", "time": "", "hours": "2", "reason": ""}
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "block":
            d = {k: request.POST.get(k, "").strip() for k in d}
            when = parse_datetime(d["date"], d["time"])
            hours = d["hours"] if d["hours"] in ("1", "2", "3", "4", "8") else ""
            if when is None:
                errors["when"] = "Choose a date and a start time."
            elif when <= datetime.now():
                errors["when"] = "Choose a future date and time."
            if not hours:
                errors["hours"] = "Choose how long you are unavailable."
            if not errors:
                block = SalesAppointment(booking_id=models.new_id("SA-"), scheduled_date_time=when,
                                         duration_minutes=int(hours) * 60, purpose="Unavailable", sales_manager=me)
                if not block.is_manager_available():                  # S-1a: conflicts with an appointment
                    me.appointments.remove(block)
                    errors["when"] = "You already have an appointment in that period. Move it first."
                else:
                    block.status = "Confirmed"
                    w.appointments[block.booking_id] = block
                    commit()
                    flash(request, "ok", "Period blocked", f"Nobody can book you on {when:%a %b %d} from {when:%H:%M} "
                          f"for {hours} hour(s).")
                    return redirect(f"/manager/schedule/?from={when.date()}")
        elif action == "unblock":
            a = w.appointments.get(request.POST.get("id", ""))
            if a and a.sales_manager is me and a.customer is None and a.status in ("Booked", "Confirmed"):
                a.cancel()
                commit()
                flash(request, "ok", "Blocked period removed")
            return redirect(request.get_full_path())
    ctx = schedule_ctx(w, request, me.person_id)
    return mpage(request, "manager_schedule.html", "schedule", **ctx, d=d, errors=errors, now=datetime.now())


# ------------------------------------------------------------------ UC6: escalated conversations
@need("manager")
def manager_messages(request):
    me = request.user_obj
    convs = sorted(me.escalated_conversations, key=lambda c: (c.status == "Closed", -c.last_activity_date.toordinal()))
    return mpage(request, "manager_messages.html", "messages", convs=convs)


@need("manager")
def manager_conversation(request, cid):
    me = request.user_obj
    conv = next((c for c in me.escalated_conversations if c.conversation_id == cid), None)
    if conv is None:
        return redirect("/manager/messages/")
    if request.method == "POST" and request.POST.get("action") == "close":
        conv.close()
        commit()
        flash(request, "ok", "Conversation closed", "The concern was handled with the customer.")
        return redirect(f"/manager/messages/{cid}/")
    return mpage(request, "manager_conversation.html", "messages", conv=conv, msgs=conv.get_messages())


@need("manager")
def manager_reports(request):
    me = request.user_obj
    reps = sorted(me.reports, key=lambda r: (r.generated_date or date.min, r.report_id), reverse=True)
    return mpage(request, "reports.html", "reports", reps=reps, admin=False)


# ------------------------------------------------------------------ UC3: automation rules (admin)
FREQ = ("Daily", "Weekly", "Monthly")
SOURCES = {"": "All lead sources", "online": "Online", "walk-in": "Walk-in", "phone": "Phone"}


@need("admin")
def rules(request):
    me, w = request.user_obj, world()
    d, errors = {"name": "", "frequency": "Weekly", "source": "", "manager": ""}, {}
    if request.method == "POST":
        action = request.POST.get("action")
        rule = w.rules.get(request.POST.get("id", ""))
        if action == "create":
            d = {k: request.POST.get(k, "").strip() for k in d}
            if not d["name"]:
                errors["name"] = "Give the rule a name."
            elif any(r.name.lower() == d["name"].lower() for r in w.rules.values()):
                errors["name"] = "A rule with this name already exists."
            if d["frequency"] not in FREQ:
                errors["frequency"] = "Choose how often the report is produced."
            if d["source"] not in SOURCES:
                errors["source"] = "Choose a lead source."
            if d["manager"] and d["manager"] not in w.managers:
                errors["manager"] = "Choose a sales manager."
            if not errors:
                rule = AutomationRule(rule_id=models.new_id("AR-"), name=d["name"], frequency=d["frequency"],
                                      filters=f"lead_source={d['source']}" if d["source"] else "",
                                      sales_manager=w.managers.get(d["manager"]))
                me.manage_rule(rule)
                w.rules[rule.rule_id] = rule
                commit()
                flash(request, "ok", f"Rule {rule.name} created",
                      "It runs automatically at its frequency. Use Run now to produce a report immediately.")
                return redirect("/admin-portal/rules/")
        elif rule and action == "run":
            try:
                rule.generate_report().email_to_manager()      # what the scheduler does when the rule is due
            except ValueError as e:                            # UC3 alternate flow 2: report generation error
                rule.reports.pop()
                flash(request, "bad", "Report generation error", f"{e}. Assign a sales manager to the rule and run it again.")
            else:
                rep = rule.reports[-1]
                if rep.content.startswith("No data"):          # alternate flow 1
                    flash(request, "warn", "Report produced: no data available",
                          f"No records match the filters for {rep.start_date} to {rep.end_date}. "
                          f"The report was still sent to {rep.sales_manager.name}.")
                else:
                    flash(request, "ok", "Report generated and emailed", f"Sent to {rep.sales_manager.name}: {rep.content}")
                commit()
            return redirect("/admin-portal/rules/")
        elif rule and action in ("activate", "deactivate"):
            getattr(rule, action)()
            commit()
            flash(request, "ok", f"Rule {'activated' if action == 'activate' else 'paused'}", rule.name)
            return redirect("/admin-portal/rules/")
    return apage(request, "rules.html", "rules", rules=w.rules.values(), d=d, errors=errors, freq=FREQ,
                 sources=SOURCES, managers=w.managers.values())


@need("admin")
def admin_reports(request):
    reps = sorted(world().reports.values(), key=lambda r: (r.generated_date or date.min, r.report_id), reverse=True)
    return apage(request, "reports.html", "reports", reps=reps, admin=True)
