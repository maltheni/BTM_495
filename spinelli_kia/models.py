"""Problem-domain classes - Prototype 2 (BTM 495, Team 23).

This file follows the Milestone 5 *implementation* class diagram:
  * The abstract classes Person and Booking are gone. Their attributes and methods
    are written out in each child class (Admin, SalesManager, Receptionist, Customer;
    SalesAppointment, TestDrive), exactly as in the diagram.
  * Every association is an attribute that holds the related object(s)
    (for example Customer.status_updates: List[StatusUpdate] and StatusUpdate.customer).
  * Every method in the diagram is implemented.

Names use Python's snake_case: personID -> person_id, addStatusUpdate() -> add_status_update(), ...
The four methods documented in Milestone 5 (reschedule, confirm, send, complete) follow
their method specifications step by step (the step numbers are in the comments).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from itertools import count
from typing import List, Optional

# ----------------------------------------------------------------- helpers
# Small services used by the classes. They are not problem-domain classes, so they
# are not in the class diagram.

OUTBOX: List[str] = []          # stands in for the email / SMS / in-app delivery service
_ids = count(1)


def new_id(prefix: str) -> str:
    """Give every new object a unique ID such as MS7 or SU3."""
    return f"{prefix}{next(_ids)}"


def notify(person, text: str) -> None:
    """Deliver a notification (in the prototype it is stored in OUTBOX and printed)."""
    OUTBOX.append(f"to {person.name}: {text}")


def entity(cls):
    """Dataclass that compares by identity and prints a short name, so objects that
    point to each other (Customer <-> Conversation) do not print forever."""
    cls = dataclass(kw_only=True, eq=False, repr=False)(cls)
    key = next(iter(cls.__dataclass_fields__))
    cls.__repr__ = lambda self: f"{type(self).__name__}({getattr(self, key)})"
    return cls


def try_send(message) -> bool:
    """Send a system notice; if it cannot be sent (no consent, no email...) the booking
    or status change still goes ahead and staff contact the customer another way."""
    try:
        message.send()
        return True
    except ValueError:
        return False


def _check_contact(email: str, phone_number: str) -> None:
    """Validation used by update_contact_info() (UC1 alternate flow 6a)."""
    if email and "@" not in email:
        raise ValueError("Invalid email address")
    if phone_number and sum(c.isdigit() for c in phone_number) < 10:
        raise ValueError("Phone number must have at least 10 digits")


ACTIVE_BOOKING = ("Booked", "Confirmed", "Rescheduled")


def _overlaps(a_start: datetime, a_minutes: int, b_start: datetime, b_minutes: int) -> bool:
    return a_start < b_start + timedelta(minutes=b_minutes) and b_start < a_start + timedelta(minutes=a_minutes)


# =================================================================== people
@entity
class Admin:
    person_id: str
    name: str
    email: str = ""
    phone_number: str = ""
    access_level: str = "Standard"
    automation_rules: List[AutomationRule] = field(default_factory=list)

    def update_contact_info(self, email: str, phone_number: str) -> None:
        _check_contact(email, phone_number)
        self.email, self.phone_number = email, phone_number

    def manage_rule(self, rule: AutomationRule) -> None:
        """Take charge of an automation rule (UC3): the admin now manages it."""
        if rule not in self.automation_rules:
            self.automation_rules.append(rule)
        rule.admin = self


@entity
class SalesManager:
    person_id: str
    name: str
    email: str = ""
    phone_number: str = ""
    sales_team: str = ""
    customers: List[Customer] = field(default_factory=list)
    appointments: List[SalesAppointment] = field(default_factory=list)
    escalated_conversations: List[Conversation] = field(default_factory=list)
    reports: List[Report] = field(default_factory=list)

    def update_contact_info(self, email: str, phone_number: str) -> None:
        _check_contact(email, phone_number)
        self.email, self.phone_number = email, phone_number

    def get_customers(self) -> List[Customer]:
        return list(self.customers)

    def get_appointments(self) -> List[SalesAppointment]:
        """The manager's schedule, in date order (UC2)."""
        return sorted(self.appointments, key=lambda a: a.scheduled_date_time)


@entity
class Receptionist:
    person_id: str
    name: str
    email: str = ""
    phone_number: str = ""
    shift: str = "Morning"                       # Morning / Evening
    conversations: List[Conversation] = field(default_factory=list)
    service_requests: List[ServiceRequest] = field(default_factory=list)
    sales_appointments: List[SalesAppointment] = field(default_factory=list)
    test_drives: List[TestDrive] = field(default_factory=list)

    def update_contact_info(self, email: str, phone_number: str) -> None:
        _check_contact(email, phone_number)
        self.email, self.phone_number = email, phone_number

    def get_conversations(self) -> List[Conversation]:
        """Open and escalated conversations first, most recent activity first (UC6)."""
        return sorted(self.conversations, key=lambda c: (c.status == "Closed", -c.last_activity_date.toordinal()))


@entity
class Customer:
    person_id: str
    name: str
    email: str = ""
    phone_number: str = ""
    vehicle_interest: str = ""
    preferred_language: str = "English"          # English / French
    messaging_consent: bool = False
    created_date: date = field(default_factory=date.today)
    lead_source: str = "walk-in"                 # walk-in / phone / online
    assigned_to: Optional[SalesManager] = None
    status_updates: List[StatusUpdate] = field(default_factory=list)
    conversations: List[Conversation] = field(default_factory=list)
    service_requests: List[ServiceRequest] = field(default_factory=list)
    sales_appointments: List[SalesAppointment] = field(default_factory=list)
    test_drives: List[TestDrive] = field(default_factory=list)

    def update_contact_info(self, email: str, phone_number: str) -> None:
        _check_contact(email, phone_number)
        self.email, self.phone_number = email, phone_number

    def update_preferences(self, language: str, consent: bool) -> None:
        if language not in ("English", "French"):
            raise ValueError("Language must be English or French")
        self.preferred_language, self.messaging_consent = language, consent

    def matches_search(self, text: str) -> bool:
        t = text.strip().lower()
        return bool(t) and (t in self.name.lower() or t in self.email.lower()
                            or t.replace("-", "") in self.phone_number.replace("-", ""))

    def add_status_update(self, stage: str, note: str) -> None:
        """Record a new sales stage in the customer's history and, if the customer agreed
        to be contacted, send them a notification (UC5 S-2, M4 Figure 18)."""
        if stage not in StatusUpdate.STAGES:
            raise ValueError(f"Unknown stage: {stage}")
        update = StatusUpdate(update_id=new_id("SU"), stage=stage, note=note, customer=self)
        self.status_updates.append(update)
        if self.messaging_consent:
            conv = _system_conversation(self, "Status updates")
            notice = Message(message_id=new_id("MS"), conversation=conv, title="Status update",
                    content=f"Your file is now at the stage: {stage}.", sender_role="System",
                    message_type="Notification", channel="Email")
            try_send(notice)

    def get_current_stage(self) -> str:
        """Stage of the latest status update, or "Unavailable" (UC5 S-1 and A-1)."""
        if not self.status_updates:
            return "Unavailable"
        return self.status_updates[-1].stage

    def assign_to(self, manager: SalesManager) -> None:
        if self.assigned_to is not None and self in self.assigned_to.customers:
            self.assigned_to.customers.remove(self)
        self.assigned_to = manager
        manager.customers.append(self)


@entity
class StatusUpdate:
    update_id: str
    stage: str
    updated_date: date = field(default_factory=date.today)
    note: str = ""
    customer: Optional[Customer] = None

    STAGES = ("Lead", "Contacted", "Test drive", "Negotiation", "Closed")


@entity
class ServiceRequest:
    request_id: str
    subject: str = ""
    description: str = ""
    status: str = "Open"                         # Open / In progress / Resolved / Closed
    created_date: date = field(default_factory=date.today)
    resolution: str = ""
    customer: Optional[Customer] = None
    receptionist: Optional[Receptionist] = None

    def submit(self) -> None:
        """Validate the online form and record the request (UC7, M4 Figures 24-26)."""
        missing = [f for f in ("subject", "description") if not getattr(self, f).strip()]
        if missing or self.customer is None:
            raise ValueError(f"Missing required information: {', '.join(missing) or 'customer'}")
        if len(self.description.strip()) < 10:
            raise ValueError("Invalid information: the description is too short")
        self.status, self.created_date = "Open", date.today()
        if self not in self.customer.service_requests:
            self.customer.service_requests.append(self)

    def assign_to(self, staff: Receptionist) -> None:
        self.receptionist = staff
        if self not in staff.service_requests:
            staff.service_requests.append(self)
        if self.status == "Open":
            self.status = "In progress"

    def resolve(self, resolution: str) -> None:
        if self.status in ("Resolved", "Closed"):
            raise ValueError("This request is already resolved")
        self.resolution, self.status = resolution, "Resolved"

    def close(self) -> None:
        if self.status != "Resolved":
            raise ValueError("Only a resolved request can be closed")
        self.status = "Closed"


# =========================================================== bookings
def _booking_conversation(customer: Customer, receptionist: Optional[Receptionist]) -> Conversation:
    """Confirmations and notices about bookings go in one conversation per customer."""
    conv = _system_conversation(customer, "Bookings")
    if conv.receptionist is None and receptionist is not None:
        conv.assign_to(receptionist)
    return conv


def _system_conversation(customer: Customer, subject: str) -> Conversation:
    for conv in customer.conversations:
        if conv.subject == subject and conv.status != "Closed":
            return conv
    return Conversation(conversation_id=new_id("CV"), subject=subject, customer=customer)


def _booking_message(booking, title: str, content: str, message_type: str) -> Message:
    conv = _booking_conversation(booking.customer, booking.receptionist)
    msg = Message(message_id=new_id("MS"), conversation=conv, title=title, content=content,
                  sender_role="System", message_type=message_type, channel="Email")
    if isinstance(booking, SalesAppointment):
        msg.sales_appointment = booking
    else:
        msg.test_drive = booking
    booking.messages.append(msg)
    return msg


@entity
class SalesAppointment:
    booking_id: str
    scheduled_date_time: datetime
    duration_minutes: int = 30
    status: str = "Booked"                       # Booked / Confirmed / Rescheduled / Cancelled / Completed
    created_date: date = field(default_factory=date.today)
    purpose: str = ""
    customer: Optional[Customer] = None
    receptionist: Optional[Receptionist] = None
    sales_manager: Optional[SalesManager] = None
    messages: List[Message] = field(default_factory=list)

    def __post_init__(self):
        if self.duration_minutes <= 0:
            raise ValueError("durationMinutes must be > 0")
        for owner, attr in ((self.customer, "sales_appointments"), (self.receptionist, "sales_appointments"),
                            (self.sales_manager, "appointments")):
            if owner is not None:
                getattr(owner, attr).append(self)

    # -- contract/specification ID 2 ---------------------------------------
    def confirm(self) -> None:
        if self.status not in ("Booked", "Rescheduled"):                    # 1
            raise ValueError("Only a booked or rescheduled appointment can be confirmed")
        self.status = "Confirmed"                                           # 2
        when = self.scheduled_date_time.strftime("%Y-%m-%d %H:%M")
        if self.customer is not None:
            try_send(_booking_message(self, "Appointment confirmed",                 # 3
                             f"Your appointment with {self.sales_manager.name if self.sales_manager else 'our team'} "
                             f"is confirmed for {when}.", "Confirmation"))
            reminder = _booking_message(self, "Appointment reminder",       # 4 (+5: _booking_message
                                        f"Reminder: your appointment is tomorrow at {when}.", "Reminder")  # adds both to messages)
            reminder.schedule(self.scheduled_date_time - timedelta(days=1))

    def cancel(self) -> None:
        if self.status not in ACTIVE_BOOKING:
            raise ValueError("This appointment is already cancelled or completed")
        self.status = "Cancelled"
        for m in self.messages:                                             # cancel scheduled reminders
            if m.status == "Scheduled":
                m.cancel()
        if self.customer is not None:
            try_send(_booking_message(self, "Appointment cancelled",
                             "Your appointment was cancelled.", "Notification"))

    # -- contract/specification ID 1 ---------------------------------------
    def reschedule(self, new_date_time: datetime) -> None:
        if self.status in ("Cancelled", "Completed"):                       # 1
            raise ValueError("A cancelled or completed appointment cannot be moved")
        old_date_time = self.scheduled_date_time                            # 2
        self.scheduled_date_time = new_date_time                            # 3
        if not self.is_manager_available():                                 # 4
            self.scheduled_date_time = old_date_time                        # 5 (UC2 S-1a)
            raise ValueError("The new slot is not free")
        self.status = "Rescheduled"                                         # 6
        for m in self.messages:                                             # 7
            if m.message_type == "Reminder" and m.status == "Scheduled":
                m.schedule(new_date_time - timedelta(days=1))
        if self.customer is not None:                                       # 8
            try_send(_booking_message(self, "Your appointment was moved",
                             f"New date and time: {new_date_time:%Y-%m-%d %H:%M}.", "Notification"))

    def complete(self) -> None:
        if self.status not in ("Confirmed", "Rescheduled"):
            raise ValueError("Only a confirmed appointment can be completed")
        if self.scheduled_date_time > datetime.now():
            raise ValueError("The appointment has not happened yet")
        self.status = "Completed"
        if self.customer is not None:
            self.customer.add_status_update("Contacted", f"Sales appointment completed on {date.today()}")

    def is_manager_available(self) -> bool:
        """True if the sales manager has no other active appointment (or blocked period)
        overlapping this one (UC2 S-1, S-1a, S-3)."""
        if self.sales_manager is None:
            return False
        return not any(
            other is not self and other.status in ACTIVE_BOOKING
            and _overlaps(self.scheduled_date_time, self.duration_minutes,
                          other.scheduled_date_time, other.duration_minutes)
            for other in self.sales_manager.appointments)


@entity
class TestDrive:
    booking_id: str
    scheduled_date_time: datetime
    duration_minutes: int = 30
    status: str = "Booked"                       # Booked / Confirmed / Rescheduled / Cancelled / Completed
    created_date: date = field(default_factory=date.today)
    driver_license_number: str = ""
    departure_time: Optional[datetime] = None
    return_time: Optional[datetime] = None
    customer: Optional[Customer] = None
    receptionist: Optional[Receptionist] = None
    vehicle: Optional[Vehicle] = None
    plate: Optional[DealerPlate] = None
    messages: List[Message] = field(default_factory=list)

    def __post_init__(self):
        if self.duration_minutes <= 0:
            raise ValueError("durationMinutes must be > 0")
        for owner in (self.customer, self.receptionist, self.vehicle):
            if owner is not None:
                owner.test_drives.append(self)

    # -- contract/specification ID 2 ---------------------------------------
    def confirm(self) -> None:
        if self.status not in ("Booked", "Rescheduled"):                    # 1
            raise ValueError("Only a booked or rescheduled test drive can be confirmed")
        if not self.driver_license_number.strip():                          # pre-condition: license checked
            raise ValueError("The driver license must be checked before confirming")
        self.status = "Confirmed"                                           # 2
        when = self.scheduled_date_time.strftime("%Y-%m-%d %H:%M")
        car = f"{self.vehicle.make} {self.vehicle.model}" if self.vehicle else "the vehicle"
        if self.customer is not None:
            try_send(_booking_message(self, "Test drive confirmed",                  # 3
                             f"Your test drive of the {car} is confirmed for {when}.", "Confirmation"))
            reminder = _booking_message(self, "Test drive reminder",        # 4 (+5)
                                        f"Reminder: your test drive of the {car} is tomorrow at {when}.", "Reminder")
            reminder.schedule(self.scheduled_date_time - timedelta(days=1))

    def cancel(self) -> None:
        """Cancel a test drive, for example when the driver license is not valid (UC4)."""
        if self.status not in ACTIVE_BOOKING:
            raise ValueError("This test drive is already cancelled or completed")
        self.status = "Cancelled"
        for m in self.messages:
            if m.status == "Scheduled":
                m.cancel()
        if self.plate is not None:
            self.plate.release()
        if self.customer is not None:
            try_send(_booking_message(self, "Test drive cancelled",
                             "Your test drive request was cancelled. Please contact us for details.",
                             "Notification"))

    # -- contract/specification ID 1 ---------------------------------------
    def reschedule(self, new_date_time: datetime) -> None:
        if self.status in ("Cancelled", "Completed"):                       # 1
            raise ValueError("A cancelled or completed test drive cannot be moved")
        old_date_time = self.scheduled_date_time                            # 2
        self.scheduled_date_time = new_date_time                            # 3
        if not self.is_vehicle_available():                                 # 4
            self.scheduled_date_time = old_date_time                        # 5
            raise ValueError("The vehicle is not free at the new time")
        self.status = "Rescheduled"                                         # 6
        for m in self.messages:                                             # 7
            if m.message_type == "Reminder" and m.status == "Scheduled":
                m.schedule(new_date_time - timedelta(days=1))
        if self.customer is not None:                                       # 8
            try_send(_booking_message(self, "Your test drive was moved",
                             f"New date and time: {new_date_time:%Y-%m-%d %H:%M}.", "Notification"))

    # -- contract/specification ID 4 ---------------------------------------
    def complete(self) -> None:
        if self.status not in ("Confirmed", "Rescheduled"):                 # 1
            raise ValueError("Only a confirmed test drive can be completed")
        if self.scheduled_date_time > datetime.now():                       # 2
            raise ValueError("A test drive cannot be completed before it starts")
        self.return_time = datetime.now()                                   # 3
        if self.plate is not None:                                          # 4
            self.plate.release()
        self.status = "Completed"                                           # 5
        if self.customer is not None:                                       # 6
            self.customer.add_status_update("Test drive", f"Test drive completed on {date.today()}")

    def is_vehicle_available(self) -> bool:
        """Ask the vehicle whether it is free at this test drive's time (UC4, M4 Figure 13).
        A test drive never conflicts with itself, so it is left out while checking."""
        if self.vehicle is None:
            return False
        mine = self in self.vehicle.test_drives
        if mine:
            self.vehicle.test_drives.remove(self)
        try:
            return self.vehicle.check_availability(self.scheduled_date_time)
        finally:
            if mine:
                self.vehicle.test_drives.append(self)

    def assign_plate(self, plate: DealerPlate) -> None:
        if self.status not in ACTIVE_BOOKING:
            raise ValueError("A plate can only be assigned to an active test drive")
        plate.assign()
        self.plate = plate
        if self not in plate.test_drives:
            plate.test_drives.append(self)
        self.departure_time = self.departure_time or datetime.now()


@entity
class Vehicle:
    stock_number: str
    vin: str = ""
    make: str = ""
    model: str = ""
    year: int = 0
    is_available: bool = True
    test_drives: List[TestDrive] = field(default_factory=list)

    def check_availability(self, date_time: datetime) -> bool:
        """The vehicle is in stock and no active test drive uses it at that time."""
        if not self.is_available:
            return False
        return not any(td.status in ACTIVE_BOOKING
                       and _overlaps(date_time, 30, td.scheduled_date_time, td.duration_minutes)
                       for td in self.test_drives)


@entity
class DealerPlate:
    plate_number: str
    status: str = "Free"                         # Free / Assigned
    test_drives: List[TestDrive] = field(default_factory=list)

    def assign(self) -> None:
        if self.status != "Free":
            raise ValueError(f"Plate {self.plate_number} is already in use")
        self.status = "Assigned"

    def release(self) -> None:
        self.status = "Free"


# ======================================================= messaging (UC6)
@entity
class Conversation:
    conversation_id: str
    subject: str = ""
    status: str = "Open"                         # Open / Escalated / Closed
    start_date: date = field(default_factory=date.today)
    last_activity_date: date = field(default_factory=date.today)
    customer: Optional[Customer] = None
    receptionist: Optional[Receptionist] = None
    sales_manager: Optional[SalesManager] = None
    messages: List[Message] = field(default_factory=list)

    def __post_init__(self):
        if self.customer is not None and self not in self.customer.conversations:
            self.customer.conversations.append(self)

    def add_message(self, message: Message) -> None:
        """Add a sent message to the thread and notify the other person (UC6 steps 5 and 8)."""
        if message not in self.messages:
            self.messages.append(message)
        message.conversation = self
        self.last_activity_date = date.today()
        if message.sender_role == "Customer":
            if self.receptionist is not None:
                notify(self.receptionist, f"new message from {self.customer.name}: {message.title}")
        elif self.customer is not None:
            notify(self.customer, f"{message.title}: {message.content}")

    def get_messages(self) -> List[Message]:
        return sorted(self.messages, key=lambda m: m.sent_date_time or datetime.min)

    def count_unread(self) -> int:
        return sum(1 for m in self.messages if m.status in ("Sent", "Delivered"))

    def assign_to(self, receptionist: Receptionist) -> None:
        self.receptionist = receptionist
        if self not in receptionist.conversations:
            receptionist.conversations.append(self)

    def escalate_to(self, manager: SalesManager) -> None:
        """The receptionist cannot resolve the concern (UC6 6a, M4 Figure 22)."""
        if self.status == "Closed":
            raise ValueError("A closed conversation cannot be escalated")
        self.sales_manager, self.status = manager, "Escalated"
        if self not in manager.escalated_conversations:
            manager.escalated_conversations.append(self)
        notice = Message(message_id=new_id("MS"), conversation=self, title="Conversation escalated",
                         content=f"Escalated to {manager.name}.", sender_role="System",
                         message_type="Notification")
        notice.sent_date_time, notice.status = datetime.now(), "Sent"
        self.messages.append(notice)
        notify(manager, f"conversation escalated: {self.subject}")

    def close(self) -> None:
        self.status = "Closed"


@entity
class Message:
    message_id: str
    title: str = ""
    content: str = ""
    sent_date_time: Optional[datetime] = None
    status: str = "Composed"                     # Composed / Scheduled / Sent / Delivered / Read / Failed / Cancelled
    channel: str = "In-app"                      # Email / SMS / In-app
    sender_role: str = "Customer"                # Customer / Receptionist / System
    message_type: str = "Message"                # Message / Notification / Confirmation / Reminder
    scheduled_date_time: Optional[datetime] = None
    conversation: Optional[Conversation] = None
    sales_appointment: Optional[SalesAppointment] = None
    test_drive: Optional[TestDrive] = None

    def __post_init__(self):
        if self.sales_appointment is not None and self.test_drive is not None:
            raise ValueError("A message is about at most one booking")

    def validate(self) -> bool:
        """Title and content filled in, and the customer agreed to be contacted."""
        customer = self.conversation.customer if self.conversation else None
        consent = customer is not None and (customer.messaging_consent or self.sender_role == "Customer")
        return bool(self.title.strip()) and bool(self.content.strip()) and consent

    # -- contract/specification ID 3 ---------------------------------------
    def send(self) -> None:
        if self.status not in ("Composed", "Scheduled"):                    # 1
            raise ValueError("A message can only be sent once")
        if not self.validate():                                             # 2
            raise ValueError("The message is not valid: title, content or consent is missing")
        conv = self.conversation                                            # 3
        recipient = None if conv is None else (conv.receptionist if self.sender_role == "Customer" else conv.customer)
        reachable = recipient is not None and (                             # 4
            (self.channel == "Email" and bool(recipient.email))
            or (self.channel == "SMS" and bool(recipient.phone_number))
            or self.channel == "In-app")
        if not reachable:                                                   # 5 (UC6 5a/8a)
            self.mark_failed()
            raise ValueError("The recipient cannot be reached: the message was not delivered")
        self.sent_date_time, self.status = datetime.now(), "Sent"          # 6
        self.conversation.add_message(self)                                 # 7

    def mark_as_read(self) -> None:
        if self.status not in ("Sent", "Delivered"):
            raise ValueError("Only a sent message can be read")
        self.status = "Read"

    def mark_failed(self) -> None:
        self.status = "Failed"

    def mark_as_delivered(self) -> None:
        if self.status != "Sent":
            raise ValueError("Only a sent message can be delivered")
        self.status = "Delivered"

    def schedule(self, send_time: datetime) -> None:
        """Hold a confirmation or reminder until send_time (moving it if already scheduled)."""
        if self.status not in ("Composed", "Scheduled"):
            raise ValueError("Only a message that was not sent yet can be scheduled")
        self.scheduled_date_time, self.status = send_time, "Scheduled"

    def cancel(self) -> None:
        if self.status != "Scheduled":
            raise ValueError("Only a scheduled message can be cancelled")
        self.status = "Cancelled"


# ============================================ automation / reports (UC3)
@entity
class AutomationRule:
    rule_id: str
    name: str = ""
    frequency: str = "Weekly"                    # Daily / Weekly / Monthly
    filters: str = ""                            # e.g. "lead_source=online"
    is_active: bool = True
    admin: Optional[Admin] = None
    reports: List[Report] = field(default_factory=list)
    sales_manager: Optional[SalesManager] = None   # the manager who receives this rule's reports

    PERIOD = {"Daily": 1, "Weekly": 7, "Monthly": 30}

    def generate_report(self) -> Report:
        """Create the report for the last period and fill it (UC3, M4 Figure 10)."""
        end = date.today()
        report = Report(report_id=new_id("RP"), report_type=self.name or "Sales activity",
                        start_date=end - timedelta(days=self.PERIOD[self.frequency]), end_date=end,
                        automation_rule=self, sales_manager=self.sales_manager)
        self.reports.append(report)
        report.generate()
        return report

    def run(self) -> None:
        """Called by the scheduler when the rule is due: generate the report and email it."""
        if not self.is_active:
            return
        self.generate_report().email_to_manager()

    def activate(self) -> None:
        self.is_active = True

    def deactivate(self) -> None:
        self.is_active = False


@entity
class Report:
    report_id: str
    report_type: str = ""
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    generated_date: Optional[date] = None
    delivery_status: str = ""                    # Sent / Failed
    content: str = ""                            # report text, built by generate()
    automation_rule: Optional[AutomationRule] = None
    sales_manager: Optional[SalesManager] = None

    def __post_init__(self):
        if self.sales_manager is not None:
            self.sales_manager.reports.append(self)

    def generate(self) -> None:
        """Collect the data that matches the rule's filters and calculate the totals.
        Alternate flow 1: no data -> a "No data available" report is produced."""
        if self.sales_manager is None:
            raise ValueError("Report generation error: no sales manager to collect data from")
        filters = dict(f.split("=") for f in (self.automation_rule.filters if self.automation_rule else "").split(";") if "=" in f)
        customers = [c for c in self.sales_manager.get_customers()
                     if self.start_date <= c.created_date <= self.end_date
                     and all(str(getattr(c, k, "")) == v for k, v in filters.items())]
        appointments = [a for a in self.sales_manager.get_appointments()
                        if self.start_date <= a.scheduled_date_time.date() <= self.end_date]
        if not customers and not appointments:
            self.content = "No data available for the selected filters."
        else:
            stages = {}
            for c in customers:
                stages[c.get_current_stage()] = stages.get(c.get_current_stage(), 0) + 1
            self.content = (f"{len(customers)} new customer(s), {len(appointments)} appointment(s); "
                             f"stages: {stages}")
        self.generated_date = date.today()

    def email_to_manager(self) -> None:
        if self.sales_manager is None or not self.sales_manager.email:
            self.delivery_status = "Failed"
            return
        notify(self.sales_manager, f"{self.report_type} report {self.start_date} to {self.end_date}: {self.content}")
        self.delivery_status = "Sent"
