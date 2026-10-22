"""Problem-domain classes from the Milestone 3 class diagram (attributes first).

Python names use snake_case; each attribute matches the diagram
(personID -> person_id, phoneNumber -> phone_number, ...).
Methods are optional for this prototype: the Messaging ones (UC6) are
implemented, the rest are added in later iterations.
"""
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import List, Optional


# ---------------------------------------------------------------- people
@dataclass(kw_only=True)
class Person:                       # abstract: nobody is only a "Person"
    person_id: str
    name: str
    email: str = ""
    phone_number: str = ""

    def update_contact_info(self, email: str, phone_number: str) -> None:
        self.email, self.phone_number = email, phone_number


@dataclass(kw_only=True)
class Admin(Person):
    access_level: str = "Standard"


@dataclass(kw_only=True)
class SalesManager(Person):
    sales_team: str = ""


@dataclass(kw_only=True)
class Receptionist(Person):
    shift: str = "Morning"          # Morning / Evening


@dataclass(kw_only=True)
class Customer(Person):
    vehicle_interest: str = ""
    preferred_language: str = "English"      # English / French
    messaging_consent: bool = False
    created_date: date = field(default_factory=date.today)
    lead_source: str = "walk-in"             # walk-in / phone / online
    sales_manager_id: Optional[str] = None   # assignedTo (0..1)

    def matches_search(self, text: str) -> bool:
        t = text.lower()
        return t in self.name.lower() or t in self.email.lower() or t in self.phone_number


@dataclass(kw_only=True)
class StatusUpdate:
    update_id: str
    customer_id: str
    stage: str
    updated_date: date = field(default_factory=date.today)
    note: str = ""


@dataclass(kw_only=True)
class ServiceRequest:
    request_id: str
    customer_id: str
    subject: str
    description: str = ""
    status: str = "Open"             # Open / In progress / Resolved / Closed
    created_date: date = field(default_factory=date.today)
    resolution: str = ""
    receptionist_id: Optional[str] = None


# ------------------------------------------------------ bookings (UC2/UC4)
@dataclass(kw_only=True)
class Booking:                      # abstract
    booking_id: str
    customer_id: str
    scheduled_date_time: datetime
    duration_minutes: int = 30
    status: str = "Booked"           # Booked / Confirmed / Rescheduled / Cancelled
    created_date: date = field(default_factory=date.today)
    receptionist_id: Optional[str] = None


@dataclass(kw_only=True)
class SalesAppointment(Booking):
    sales_manager_id: str = ""
    purpose: str = ""


@dataclass(kw_only=True)
class TestDrive(Booking):
    vehicle_stock_number: str = ""
    plate_number: Optional[str] = None
    driver_license_number: str = ""
    departure_time: Optional[datetime] = None
    return_time: Optional[datetime] = None


@dataclass(kw_only=True)
class Vehicle:
    stock_number: str
    vin: str = ""
    make: str = ""
    model: str = ""
    year: int = 0
    is_available: bool = True


@dataclass(kw_only=True)
class DealerPlate:
    plate_number: str
    status: str = "Free"


# ------------------------------------------------------- messaging (UC6)
@dataclass(kw_only=True)
class Message:
    message_id: str
    conversation_id: str
    title: str = ""
    content: str = ""
    sent_date_time: Optional[datetime] = None
    status: str = "Sent"             # Sent / Delivered / Read / Failed
    channel: str = "In-app"          # Email / SMS / In-app
    sender_role: str = "Customer"    # Customer / Receptionist / System
    message_type: str = "Message"    # Message / Notification / Confirmation / Reminder
    scheduled_date_time: Optional[datetime] = None
    booking_id: Optional[str] = None  # about (0..1)

    def validate(self, customer_consented: bool = True) -> bool:
        """Title and content filled in, and the customer agreed to be contacted."""
        return bool(self.title.strip()) and bool(self.content.strip()) and customer_consented

    def send(self) -> None:
        self.sent_date_time = datetime.now()
        self.status = "Sent"

    def mark_failed(self) -> None:   # recipient inactive or not found (alt. flow)
        self.status = "Failed"

    def mark_as_read(self) -> None:
        self.status = "Read"

    def schedule(self, send_time: datetime) -> None:
        self.scheduled_date_time = send_time

    def cancel(self) -> None:
        self.scheduled_date_time = None


@dataclass(kw_only=True)
class Conversation:
    conversation_id: str
    customer_id: str
    subject: str = ""
    status: str = "Open"             # Open / Escalated / Closed
    start_date: date = field(default_factory=date.today)
    last_activity_date: date = field(default_factory=date.today)
    receptionist_id: Optional[str] = None     # handles (0..1)
    sales_manager_id: Optional[str] = None    # escalatedTo (0..1)
    messages: List[Message] = field(default_factory=list)  # contains (1..*)

    def add_message(self, message: Message) -> None:
        self.messages.append(message)
        self.last_activity_date = date.today()

    def get_messages(self) -> List[Message]:
        return sorted(self.messages, key=lambda m: m.sent_date_time or datetime.min)

    def count_unread(self) -> int:
        return sum(1 for m in self.messages if m.status in ("Sent", "Delivered"))

    def assign_to(self, receptionist_id: str) -> None:
        self.receptionist_id = receptionist_id

    def escalate_to(self, manager_id: str) -> None:
        self.sales_manager_id, self.status = manager_id, "Escalated"

    def close(self) -> None:
        self.status = "Closed"


# --------------------------------------------- automation / reports (UC3)
@dataclass(kw_only=True)
class AutomationRule:
    rule_id: str
    admin_id: str
    name: str = ""
    frequency: str = "Weekly"        # Daily / Weekly / Monthly
    filters: str = ""
    is_active: bool = True


@dataclass(kw_only=True)
class Report:
    report_id: str
    rule_id: str
    sales_manager_id: str
    report_type: str = ""
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    generated_date: Optional[date] = None
    delivery_status: str = "Sent"    # Sent / Failed
