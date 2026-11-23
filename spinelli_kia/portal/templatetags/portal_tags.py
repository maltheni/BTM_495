from django import template
from django.utils.safestring import mark_safe

from portal.i18n import tr

register = template.Library()


@register.simple_tag(takes_context=True)
def t(context, text):
    """{% t "Vehicles" %}: the text in the language chosen with the EN/FR switch."""
    return tr(context.get("lang", "EN"), text)


@register.filter
def pill(status):
    s = str(status)
    return mark_safe(f'<span class="pill p-{s.replace(" ", "-")}">{s}</span>')


@register.filter
def when(dt):
    """Sat Nov 28, 9:00"""
    if not dt:
        return ""
    if hasattr(dt, "hour"):
        return f"{dt:%a %b} {dt.day}, {dt.hour}:{dt:%M}"
    return f"{dt:%a %b} {dt.day}"


@register.filter
def day(d):
    return f"{d:%b} {d.day}, {d.year}" if d else ""


@register.filter
def money(v):
    return f"${v:,.0f}"


@register.filter
def get(d, k):
    return d.get(k) if d else None


@register.inclusion_tag("portal/_field.html", takes_context=True)
def field(context, label, name, kind="text", options=None, placeholder="", hint="", attrs=""):
    """One form field with its label and, if any, its error message under it (Milestone 6 style).
    options: a dict {value: label} or a list of values for a drop-down."""
    d = context.get("d") or {}
    errors = context.get("errors") or {}
    if isinstance(options, dict):
        opts = list(options.items())
    elif options:
        opts = [(o, o) for o in options]
    else:
        opts = []
    lang = context.get("lang", "EN")
    return {"label": tr(lang, label), "name": name, "kind": kind, "value": d.get(name, ""), "error": errors.get(name),
            "opts": [(v, tr(lang, str(l))) for v, l in opts], "placeholder": tr(lang, placeholder) if placeholder else "", "hint": tr(lang, hint) if hint else "",
            "attrs": attrs}


@register.filter
def attr_date(update):
    return day(update.updated_date)
