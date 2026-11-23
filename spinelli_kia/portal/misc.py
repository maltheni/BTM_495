"""Language switch and the demo tools page (notifications sent, simulation switches, reset)."""
from django.shortcuts import redirect, render

import models

from .common import LOCK, flash, reset_demo, save_settings, settings


def set_lang(request, code):
    request.session["lang"] = "FR" if code.upper() == "FR" else "EN"
    nxt = request.GET.get("next", "/")
    return redirect(nxt if nxt.startswith("/") else "/")


def demo(request):
    if request.method == "POST":
        action = request.POST.get("action")
        with LOCK:
            if action == "reset":
                reset_demo()
                flash(request, "ok", "Demo data reset", "Everything is back to the starting data.")
            elif action in ("crm_online", "reception_active"):
                s = settings()
                s[action] = not s[action]
                save_settings(s)
            elif action == "clear":
                models.OUTBOX.clear()
        return redirect("/demo/")
    notes = []
    for line in reversed(models.OUTBOX):
        who, _, text = line.partition(": ")
        notes.append((who.replace("to ", "", 1), text))
    return render(request, "portal/demo.html", {"notes": notes, "active": ""})
