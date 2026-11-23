"""Shared pieces of the web layer: the loaded objects, who is signed in, short messages
(flash banners), demo switches, language, and the data every page header needs."""
from __future__ import annotations

import json
import re
import threading
from datetime import date, datetime, time, timedelta
from functools import wraps
from pathlib import Path

from django.shortcuts import redirect

import db
import models
import seed
import store

from .i18n import tr

LOCK = threading.RLock()
_world: store.World | None = None
DEFAULT_SETTINGS = {"crm_online": True, "reception_active": True}

# Website content shown next to the vehicles (not part of the problem domain, so not in the class diagram)
CATALOGUE = {
    "K260184": {"price": 34995, "body": "Compact SUV", "engine": "2.5 L, AWD", "colour": "Snow White Pearl", "hue": 205},
    "K260211": {"price": 29495, "body": "Subcompact SUV", "engine": "2.0 L, AWD", "colour": "Pluton Blue", "hue": 220},
    "K260157": {"price": 52995, "body": "Electric crossover", "engine": "Electric, 450 km range", "colour": "Yacht Blue", "hue": 195},
    "K260302": {"price": 58995, "body": "3-row SUV", "engine": "3.8 L V6, AWD", "colour": "Wolf Grey", "hue": 230},
    "K260245": {"price": 38995, "body": "Mid-size SUV", "engine": "2.5 L, AWD", "colour": "Gravity Grey", "hue": 210},
    "K260090": {"price": 44995, "body": "Minivan", "engine": "3.5 L V6", "colour": "Astra Blue", "hue": 215},
    "K260133": {"price": 36995, "body": "Sedan", "engine": "1.6 L turbo", "colour": "Wolf Grey", "hue": 0},
    "U240512": {"price": 27995, "body": "Hybrid crossover", "engine": "1.6 L hybrid", "colour": "Cityscape Green", "hue": 140},
}

WINDOWS = {"Morning": (9, "9:00 to 12:00"), "Afternoon": (12, "12:00 to 17:00"), "Evening": (17, "17:00 to 20:00")}


# ------------------------------------------------------------- objects
def world() -> store.World:
    global _world
    with LOCK:
        if _world is None:
            if not Path(db.DB_PATH).exists():
                seed.reset()
            _world = store.load_world()
        return _world


def commit() -> None:
    """Save every object to the database after a change (DM layer)."""
    with LOCK:
        store.save_world(world())


def reset_demo() -> None:
    global _world
    with LOCK:
        _world = seed.reset()
        models.OUTBOX.clear()
        save_settings(dict(DEFAULT_SETTINGS))


def settings_path() -> Path:
    return Path(db.DB_PATH).with_name("demo_settings.json")


def settings() -> dict:
    try:
        return {**DEFAULT_SETTINGS, **json.loads(settings_path().read_text())}
    except (OSError, ValueError):
        return dict(DEFAULT_SETTINGS)


def save_settings(s: dict) -> None:
    settings_path().write_text(json.dumps(s))


# ------------------------------------------------------------- sign-in
def current_user(request):
    role, uid = request.session.get("role"), request.session.get("uid")
    w = world()
    table = {"customer": w.customers, "receptionist": w.receptionists, "manager": w.managers, "admin": w.admins}.get(role)
    return (role, table.get(uid)) if table and uid in table else (None, None)


def need(role):
    """Page decorator: the signed-in user must have this role."""
    def deco(view):
        @wraps(view)
        def wrapped(request, *a, **kw):
            r, user = current_user(request)
            if r != role:
                if role == "customer":
                    flash(request, "info", "Please sign in", "Messages, Track my Purchase and Contact Us need your customer account.")
                    return redirect(f"/signin/?next={request.path}")
                return redirect("/staff/signin/")
            request.user_obj = user
            with LOCK:
                return view(request, *a, **kw)
        return wrapped
    return deco


# ------------------------------------------------------------- banners
def flash(request, kind, title, text=""):
    request.session.setdefault("flash", []).append([kind, title, text])
    request.session.modified = True


# ------------------------------------------------------------- helpers
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[a-z]{2,}$", re.I)


def digits(s: str) -> int:
    return sum(ch.isdigit() for ch in s)


def check_email(v):
    return None if EMAIL_RE.match(v.strip()) else "Enter a valid email address, for example name@example.com."


def check_phone(v):
    return None if digits(v) >= 10 else "Enter a 10-digit phone number, for example (514) 555-0177."


def check_license(v):
    """Quebec driver's licence: one letter and 12 digits (13 characters), dashes and spaces ignored."""
    s = re.sub(r"[\s-]", "", v.upper())
    return None if re.fullmatch(r"[A-Z]\d{12}", s) else "Enter the full license number (13 characters: 1 letter and 12 digits)."


def parse_date(v):
    try:
        return date.fromisoformat(v)
    except (TypeError, ValueError):
        return None


def parse_datetime(d, t):
    try:
        return datetime.combine(date.fromisoformat(d), time.fromisoformat(t))
    except (TypeError, ValueError):
        return None


def unread_for_customer(c) -> int:
    return sum(1 for conv in c.conversations for m in conv.messages
               if m.sender_role != "Customer" and m.status in ("Sent", "Delivered"))


def unread_customer_msgs(conv) -> list:
    return [m for m in conv.messages if m.sender_role == "Customer" and m.status in ("Sent", "Delivered")]


def unread_for_staff(rec) -> int:
    return sum(len(unread_customer_msgs(c)) for c in rec.conversations if c.status != "Closed")


def car_name(v) -> str:
    return f"{v.year} {v.make} {v.model}" if v else ""


def td_label(t) -> str:
    """How the test drive status is shown on screen (Booked = waiting for the receptionist)."""
    return {"Booked": "Pending", "Cancelled": "Denied"}.get(t.status, t.status)


def window_of(dt) -> str:
    for name, (h, label) in WINDOWS.items():
        if dt.hour == h:
            return name
    return ""


# ------------------------------------------------------------- page header data
def chrome(request):
    """Context processor: the data every page header and menu needs."""
    lang = request.session.get("lang", "EN")
    role, user = current_user(request)
    flashes = request.session.pop("flash", []) if hasattr(request, "session") else []
    ctx = {"lang": lang, "role": role, "me": user, "flashes": flashes, "demo": settings(),
           "outbox_count": len(models.OUTBOX)}
    with LOCK:
        if role == "customer":
            ctx["badge"] = unread_for_customer(user)
        elif role == "receptionist":
            ctx["badge"] = unread_for_staff(user)
            seen = set(request.session.get("toasted", []))
            new = [(c, m) for c in user.conversations for m in unread_customer_msgs(c) if m.message_id not in seen]
            if new and not request.path.startswith("/staff/messages/CV"):
                c, m = new[-1]
                ctx["toast"] = {"who": c.customer.name, "subject": c.subject, "url": f"/staff/messages/{c.conversation_id}/"}
                request.session["toasted"] = list(seen | {x.message_id for _, x in new})
        elif role == "manager":
            ctx["badge"] = sum(1 for c in user.escalated_conversations if c.status == "Escalated")
    ctx["T"] = lambda s: tr(lang, s)
    return ctx
