-- Spinelli Kia sales system - database schema (SQLite)
-- One table per class in the class diagram. Subclasses share the parent's key.
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS person (
    person_id    TEXT PRIMARY KEY,
    name         TEXT NOT NULL,
    email        TEXT,
    phone_number TEXT
);

CREATE TABLE IF NOT EXISTS admin (
    person_id    TEXT PRIMARY KEY REFERENCES person(person_id),
    access_level TEXT
);

CREATE TABLE IF NOT EXISTS sales_manager (
    person_id  TEXT PRIMARY KEY REFERENCES person(person_id),
    sales_team TEXT
);

CREATE TABLE IF NOT EXISTS receptionist (
    person_id TEXT PRIMARY KEY REFERENCES person(person_id),
    shift     TEXT CHECK (shift IN ('Morning','Evening'))
);

CREATE TABLE IF NOT EXISTS customer (
    person_id          TEXT PRIMARY KEY REFERENCES person(person_id),
    vehicle_interest   TEXT,
    preferred_language TEXT CHECK (preferred_language IN ('English','French')),
    messaging_consent  INTEGER NOT NULL DEFAULT 0,
    created_date       TEXT,
    lead_source        TEXT CHECK (lead_source IN ('walk-in','phone','online')),
    sales_manager_id   TEXT REFERENCES sales_manager(person_id)      -- assignedTo (0..1)
);

CREATE TABLE IF NOT EXISTS status_update (
    update_id    TEXT PRIMARY KEY,
    customer_id  TEXT NOT NULL REFERENCES customer(person_id),       -- hasHistory
    stage        TEXT,
    updated_date TEXT,
    note         TEXT
);

CREATE TABLE IF NOT EXISTS service_request (
    request_id      TEXT PRIMARY KEY,
    customer_id     TEXT NOT NULL REFERENCES customer(person_id),    -- submits
    receptionist_id TEXT REFERENCES receptionist(person_id),         -- handledBy (0..1)
    subject         TEXT,
    description     TEXT,
    status          TEXT CHECK (status IN ('Open','In progress','Resolved','Closed')),
    created_date    TEXT,
    resolution      TEXT
);

CREATE TABLE IF NOT EXISTS vehicle (
    stock_number TEXT PRIMARY KEY,
    vin          TEXT,
    make         TEXT,
    model        TEXT,
    year         INTEGER,
    is_available INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS dealer_plate (
    plate_number TEXT PRIMARY KEY,
    status       TEXT
);

-- Booking (abstract) + its two subclasses
CREATE TABLE IF NOT EXISTS booking (
    booking_id          TEXT PRIMARY KEY,
    customer_id         TEXT NOT NULL REFERENCES customer(person_id),   -- makes
    receptionist_id     TEXT REFERENCES receptionist(person_id),        -- bookedBy (0..1)
    scheduled_date_time TEXT,
    duration_minutes    INTEGER,
    status              TEXT CHECK (status IN ('Booked','Confirmed','Rescheduled','Cancelled')),
    created_date        TEXT,
    booking_type        TEXT NOT NULL CHECK (booking_type IN ('SalesAppointment','TestDrive'))
);

CREATE TABLE IF NOT EXISTS sales_appointment (
    booking_id       TEXT PRIMARY KEY REFERENCES booking(booking_id),
    sales_manager_id TEXT NOT NULL REFERENCES sales_manager(person_id), -- meetsWith
    purpose          TEXT
);

CREATE TABLE IF NOT EXISTS test_drive (
    booking_id             TEXT PRIMARY KEY REFERENCES booking(booking_id),
    vehicle_stock_number   TEXT NOT NULL REFERENCES vehicle(stock_number), -- uses
    plate_number           TEXT REFERENCES dealer_plate(plate_number),     -- usesPlate (0..1)
    driver_license_number  TEXT,
    departure_time         TEXT,
    return_time            TEXT
);

-- Messaging (UC6)
CREATE TABLE IF NOT EXISTS conversation (
    conversation_id    TEXT PRIMARY KEY,
    customer_id        TEXT NOT NULL REFERENCES customer(person_id),      -- participatesIn
    receptionist_id    TEXT REFERENCES receptionist(person_id),           -- handles (0..1)
    sales_manager_id   TEXT REFERENCES sales_manager(person_id),          -- escalatedTo (0..1)
    subject            TEXT,
    status             TEXT NOT NULL DEFAULT 'Open' CHECK (status IN ('Open','Escalated','Closed')),
    start_date         TEXT,
    last_activity_date TEXT
);

CREATE TABLE IF NOT EXISTS message (
    message_id          TEXT PRIMARY KEY,
    conversation_id     TEXT NOT NULL REFERENCES conversation(conversation_id) ON DELETE CASCADE, -- contains
    booking_id          TEXT REFERENCES booking(booking_id),               -- about (0..1)
    title               TEXT,
    content             TEXT NOT NULL,
    sent_date_time      TEXT,
    status              TEXT CHECK (status IN ('Sent','Delivered','Read','Failed')),
    channel             TEXT CHECK (channel IN ('Email','SMS','In-app')),
    sender_role         TEXT CHECK (sender_role IN ('Customer','Receptionist','System')),
    message_type        TEXT CHECK (message_type IN ('Message','Notification','Confirmation','Reminder')),
    scheduled_date_time TEXT
);

-- Automation and reporting (UC3)
CREATE TABLE IF NOT EXISTS automation_rule (
    rule_id   TEXT PRIMARY KEY,
    admin_id  TEXT NOT NULL REFERENCES admin(person_id),                  -- manages
    name      TEXT,
    frequency TEXT CHECK (frequency IN ('Daily','Weekly','Monthly')),
    filters   TEXT,
    is_active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS report (
    report_id        TEXT PRIMARY KEY,
    rule_id          TEXT NOT NULL REFERENCES automation_rule(rule_id),   -- produces
    sales_manager_id TEXT NOT NULL REFERENCES sales_manager(person_id),   -- receives
    report_type      TEXT,
    start_date       TEXT,
    end_date         TEXT,
    generated_date   TEXT,
    delivery_status  TEXT CHECK (delivery_status IN ('Sent','Failed'))
);
