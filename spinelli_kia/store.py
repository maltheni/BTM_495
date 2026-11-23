"""Data management layer (Milestone 7: <<DM Layer>> data access classes).

Saves the problem-domain objects of models.py to the SQLite tables of schema.sql and
loads them back, so the web pages (HCI layer) never write SQL themselves.

    world = load_world()      # every object, with all its links rebuilt
    ...call domain methods...
    save_world(world)         # write everything back in one transaction
"""
from __future__ import annotations

import itertools
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Dict, List

import db
import models
from models import (Admin, AutomationRule, Conversation, Customer, DealerPlate, Message, Receptionist, Report,
                    SalesAppointment, SalesManager, ServiceRequest, StatusUpdate, TestDrive, Vehicle)

SENT = ("Sent", "Delivered", "Read")      # messages that are part of the conversation thread


@dataclass
class World:
    """Every object of the system, by ID."""
    admins: Dict[str, Admin] = field(default_factory=dict)
    managers: Dict[str, SalesManager] = field(default_factory=dict)
    receptionists: Dict[str, Receptionist] = field(default_factory=dict)
    customers: Dict[str, Customer] = field(default_factory=dict)
    vehicles: Dict[str, Vehicle] = field(default_factory=dict)
    plates: Dict[str, DealerPlate] = field(default_factory=dict)
    appointments: Dict[str, SalesAppointment] = field(default_factory=dict)
    test_drives: Dict[str, TestDrive] = field(default_factory=dict)
    conversations: Dict[str, Conversation] = field(default_factory=dict)
    service_requests: Dict[str, ServiceRequest] = field(default_factory=dict)
    rules: Dict[str, AutomationRule] = field(default_factory=dict)
    reports: Dict[str, Report] = field(default_factory=dict)

    # objects created by domain methods are reachable from the ones already known,
    # so they are collected again before saving
    def refresh(self) -> None:
        for c in list(self.customers.values()):
            for conv in c.conversations:
                self.conversations.setdefault(conv.conversation_id, conv)
            for r in c.service_requests:
                self.service_requests.setdefault(r.request_id, r)
            for a in c.sales_appointments:
                self.appointments.setdefault(a.booking_id, a)
            for t in c.test_drives:
                self.test_drives.setdefault(t.booking_id, t)
        for m in self.managers.values():
            for a in m.appointments:
                self.appointments.setdefault(a.booking_id, a)
            for r in m.reports:
                self.reports.setdefault(r.report_id, r)
        for rule in self.rules.values():
            for r in rule.reports:
                self.reports.setdefault(r.report_id, r)


# ------------------------------------------------------------------ helpers
def _s(v):
    if v is None:
        return None
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, (datetime, date)):
        return v.isoformat(sep=" ") if isinstance(v, datetime) else v.isoformat()
    return v


def _dt(v):
    return datetime.fromisoformat(v) if v else None


def _d(v):
    return date.fromisoformat(v[:10]) if v else None


def _all_messages(world: World) -> List[Message]:
    seen, out = set(), []
    sources = [c.messages for c in world.conversations.values()]
    sources += [b.messages for b in list(world.appointments.values()) + list(world.test_drives.values())]
    for lst in sources:
        for m in lst:
            if id(m) not in seen and m.conversation is not None:
                seen.add(id(m))
                out.append(m)
    return out


def _bump_id_counter(world: World) -> None:
    """New IDs (models.new_id) must not reuse a number already in the database."""
    biggest = 0
    ids = [k for d in (world.customers, world.appointments, world.test_drives, world.conversations,
                       world.service_requests, world.rules, world.reports) for k in d]
    ids += [m.message_id for m in _all_messages(world)]
    ids += [s.update_id for c in world.customers.values() for s in c.status_updates]
    for i in ids:
        nums = re.findall(r"\d+", i)
        if nums:
            biggest = max(biggest, int(nums[-1]))
    models._ids = itertools.count(max(biggest + 1, 1100))


# ------------------------------------------------------------------ save
def save_world(world: World, path=None) -> None:
    path = path or db.DB_PATH
    world.refresh()
    db.init_db(path)
    with db.connect(path) as conn:
        for t in ("report", "automation_rule", "message", "conversation", "test_drive", "sales_appointment",
                  "booking", "service_request", "status_update", "customer", "receptionist", "sales_manager",
                  "admin", "person", "vehicle", "dealer_plate"):
            conn.execute(f"DELETE FROM {t}")
        people = list(world.admins.values()) + list(world.managers.values()) + \
            list(world.receptionists.values()) + list(world.customers.values())
        for p in people:
            conn.execute("INSERT INTO person VALUES (?,?,?,?)", (p.person_id, p.name, p.email, p.phone_number))
        for a in world.admins.values():
            conn.execute("INSERT INTO admin VALUES (?,?)", (a.person_id, a.access_level))
        for m in world.managers.values():
            conn.execute("INSERT INTO sales_manager VALUES (?,?)", (m.person_id, m.sales_team))
        for r in world.receptionists.values():
            conn.execute("INSERT INTO receptionist VALUES (?,?)", (r.person_id, r.shift))
        for c in world.customers.values():
            conn.execute("INSERT INTO customer VALUES (?,?,?,?,?,?,?)",
                         (c.person_id, c.vehicle_interest, c.preferred_language, int(c.messaging_consent),
                          _s(c.created_date), c.lead_source, c.assigned_to.person_id if c.assigned_to else None))
            for s in c.status_updates:
                conn.execute("INSERT INTO status_update VALUES (?,?,?,?,?)",
                             (s.update_id, c.person_id, s.stage, _s(s.updated_date), s.note))
        for v in world.vehicles.values():
            conn.execute("INSERT INTO vehicle VALUES (?,?,?,?,?,?)",
                         (v.stock_number, v.vin, v.make, v.model, v.year, int(v.is_available)))
        for p in world.plates.values():
            conn.execute("INSERT INTO dealer_plate VALUES (?,?)", (p.plate_number, p.status))
        for b in list(world.appointments.values()) + list(world.test_drives.values()):
            kind = "SalesAppointment" if isinstance(b, SalesAppointment) else "TestDrive"
            conn.execute("INSERT INTO booking VALUES (?,?,?,?,?,?,?,?)",
                         (b.booking_id, b.customer.person_id if b.customer else None,
                          b.receptionist.person_id if b.receptionist else None, _s(b.scheduled_date_time),
                          b.duration_minutes, b.status, _s(b.created_date), kind))
            if kind == "SalesAppointment":
                conn.execute("INSERT INTO sales_appointment VALUES (?,?,?)",
                             (b.booking_id, b.sales_manager.person_id, b.purpose))
            else:
                conn.execute("INSERT INTO test_drive VALUES (?,?,?,?,?,?)",
                             (b.booking_id, b.vehicle.stock_number, b.plate.plate_number if b.plate else None,
                              b.driver_license_number, _s(b.departure_time), _s(b.return_time)))
        for c in world.conversations.values():
            conn.execute("INSERT INTO conversation VALUES (?,?,?,?,?,?,?,?)",
                         (c.conversation_id, c.customer.person_id, c.receptionist.person_id if c.receptionist else None,
                          c.sales_manager.person_id if c.sales_manager else None, c.subject, c.status,
                          _s(c.start_date), _s(c.last_activity_date)))
        for m in _all_messages(world):
            about = m.sales_appointment or m.test_drive
            conn.execute("INSERT INTO message VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                         (m.message_id, m.conversation.conversation_id, about.booking_id if about else None, m.title,
                          m.content, _s(m.sent_date_time), m.status, m.channel, m.sender_role, m.message_type,
                          _s(m.scheduled_date_time)))
        for r in world.service_requests.values():
            conn.execute("INSERT INTO service_request VALUES (?,?,?,?,?,?,?,?)",
                         (r.request_id, r.customer.person_id, r.receptionist.person_id if r.receptionist else None,
                          r.subject, r.description, r.status, _s(r.created_date), r.resolution))
        for rule in world.rules.values():
            conn.execute("INSERT INTO automation_rule VALUES (?,?,?,?,?,?,?)",
                         (rule.rule_id, rule.admin.person_id, rule.sales_manager.person_id if rule.sales_manager else None,
                          rule.name, rule.frequency, rule.filters, int(rule.is_active)))
        for rp in world.reports.values():
            if rp.sales_manager is None:          # a report that failed to generate is not kept (UC3 alt. flow 2)
                continue
            conn.execute("INSERT INTO report VALUES (?,?,?,?,?,?,?,?,?)",
                         (rp.report_id, rp.automation_rule.rule_id, rp.sales_manager.person_id,
                          rp.report_type, _s(rp.start_date), _s(rp.end_date), _s(rp.generated_date),
                          rp.delivery_status or None, rp.content))


# ------------------------------------------------------------------ load
def load_world(path=None) -> World:
    path = path or db.DB_PATH
    w = World()
    db.init_db(path)
    with db.connect(path) as conn:
        q = lambda sql: conn.execute(sql).fetchall()
        for r in q("SELECT * FROM person JOIN admin USING (person_id)"):
            w.admins[r["person_id"]] = Admin(person_id=r["person_id"], name=r["name"], email=r["email"] or "",
                                             phone_number=r["phone_number"] or "", access_level=r["access_level"])
        for r in q("SELECT * FROM person JOIN sales_manager USING (person_id)"):
            w.managers[r["person_id"]] = SalesManager(person_id=r["person_id"], name=r["name"], email=r["email"] or "",
                                                      phone_number=r["phone_number"] or "", sales_team=r["sales_team"] or "")
        for r in q("SELECT * FROM person JOIN receptionist USING (person_id)"):
            w.receptionists[r["person_id"]] = Receptionist(person_id=r["person_id"], name=r["name"], email=r["email"] or "",
                                                           phone_number=r["phone_number"] or "", shift=r["shift"])
        for r in q("SELECT * FROM person JOIN customer USING (person_id) ORDER BY person_id"):
            c = Customer(person_id=r["person_id"], name=r["name"], email=r["email"] or "",
                         phone_number=r["phone_number"] or "", vehicle_interest=r["vehicle_interest"] or "",
                         preferred_language=r["preferred_language"] or "English",
                         messaging_consent=bool(r["messaging_consent"]), created_date=_d(r["created_date"]),
                         lead_source=r["lead_source"] or "walk-in")
            w.customers[c.person_id] = c
            if r["sales_manager_id"]:
                c.assign_to(w.managers[r["sales_manager_id"]])
        for r in q("SELECT * FROM status_update ORDER BY updated_date, rowid"):
            c = w.customers[r["customer_id"]]
            c.status_updates.append(StatusUpdate(update_id=r["update_id"], stage=r["stage"],
                                                 updated_date=_d(r["updated_date"]), note=r["note"] or "", customer=c))
        for r in q("SELECT * FROM vehicle"):
            w.vehicles[r["stock_number"]] = Vehicle(stock_number=r["stock_number"], vin=r["vin"] or "", make=r["make"],
                                                    model=r["model"], year=r["year"], is_available=bool(r["is_available"]))
        for r in q("SELECT * FROM dealer_plate"):
            w.plates[r["plate_number"]] = DealerPlate(plate_number=r["plate_number"], status=r["status"])
        for r in q("""SELECT b.*, s.sales_manager_id, s.purpose FROM booking b
                      JOIN sales_appointment s USING (booking_id) ORDER BY b.rowid"""):
            a = SalesAppointment(booking_id=r["booking_id"], scheduled_date_time=_dt(r["scheduled_date_time"]),
                                 duration_minutes=r["duration_minutes"], status=r["status"],
                                 created_date=_d(r["created_date"]), purpose=r["purpose"] or "",
                                 customer=w.customers.get(r["customer_id"]),
                                 receptionist=w.receptionists.get(r["receptionist_id"]),
                                 sales_manager=w.managers[r["sales_manager_id"]])
            w.appointments[a.booking_id] = a
        for r in q("""SELECT b.*, t.vehicle_stock_number, t.plate_number, t.driver_license_number,
                             t.departure_time, t.return_time FROM booking b
                      JOIN test_drive t USING (booking_id) ORDER BY b.rowid"""):
            t = TestDrive(booking_id=r["booking_id"], scheduled_date_time=_dt(r["scheduled_date_time"]),
                          duration_minutes=r["duration_minutes"], status=r["status"],
                          created_date=_d(r["created_date"]), driver_license_number=r["driver_license_number"] or "",
                          departure_time=_dt(r["departure_time"]), return_time=_dt(r["return_time"]),
                          customer=w.customers.get(r["customer_id"]),
                          receptionist=w.receptionists.get(r["receptionist_id"]),
                          vehicle=w.vehicles[r["vehicle_stock_number"]])
            if r["plate_number"]:
                t.plate = w.plates[r["plate_number"]]
                t.plate.test_drives.append(t)
            w.test_drives[t.booking_id] = t
        for r in q("SELECT * FROM conversation ORDER BY rowid"):
            c = Conversation(conversation_id=r["conversation_id"], subject=r["subject"] or "", status=r["status"],
                             start_date=_d(r["start_date"]), last_activity_date=_d(r["last_activity_date"]),
                             customer=w.customers[r["customer_id"]])
            if r["receptionist_id"]:
                c.assign_to(w.receptionists[r["receptionist_id"]])
            if r["sales_manager_id"]:
                c.sales_manager = w.managers[r["sales_manager_id"]]
                c.sales_manager.escalated_conversations.append(c)
            w.conversations[c.conversation_id] = c
        for r in q("SELECT * FROM message ORDER BY rowid"):
            conv = w.conversations[r["conversation_id"]]
            m = Message(message_id=r["message_id"], title=r["title"] or "", content=r["content"],
                        sent_date_time=_dt(r["sent_date_time"]), status=r["status"], channel=r["channel"],
                        sender_role=r["sender_role"], message_type=r["message_type"],
                        scheduled_date_time=_dt(r["scheduled_date_time"]), conversation=conv)
            b = r["booking_id"]
            if b in w.appointments:
                m.sales_appointment = w.appointments[b]
                w.appointments[b].messages.append(m)
            elif b in w.test_drives:
                m.test_drive = w.test_drives[b]
                w.test_drives[b].messages.append(m)
            if m.status in SENT:
                conv.messages.append(m)
        for r in q("SELECT * FROM service_request ORDER BY rowid"):
            s = ServiceRequest(request_id=r["request_id"], subject=r["subject"] or "", description=r["description"] or "",
                               status=r["status"], created_date=_d(r["created_date"]), resolution=r["resolution"] or "",
                               customer=w.customers[r["customer_id"]])
            s.customer.service_requests.append(s)
            if r["receptionist_id"]:
                s.receptionist = w.receptionists[r["receptionist_id"]]
                s.receptionist.service_requests.append(s)
            w.service_requests[s.request_id] = s
        for r in q("SELECT * FROM automation_rule ORDER BY rowid"):
            rule = AutomationRule(rule_id=r["rule_id"], name=r["name"] or "", frequency=r["frequency"],
                                  filters=r["filters"] or "", is_active=bool(r["is_active"]),
                                  sales_manager=w.managers.get(r["sales_manager_id"]))
            w.admins[r["admin_id"]].manage_rule(rule)
            w.rules[rule.rule_id] = rule
        for r in q("SELECT * FROM report ORDER BY rowid"):
            rule = w.rules[r["rule_id"]]
            rp = Report(report_id=r["report_id"], report_type=r["report_type"] or "", start_date=_d(r["start_date"]),
                        end_date=_d(r["end_date"]), generated_date=_d(r["generated_date"]),
                        delivery_status=r["delivery_status"] or "", content=r["content"] or "",
                        automation_rule=rule, sales_manager=w.managers.get(r["sales_manager_id"]))
            rule.reports.append(rp)
            w.reports[rp.report_id] = rp
    _bump_id_counter(w)
    return w
