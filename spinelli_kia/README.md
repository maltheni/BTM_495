# Spinelli Kia Sales System – Prototype 2 (BTM 495, Team 23)

Second prototype: the problem-domain classes with **all their attributes and all their methods**,
following the Milestone 5 implementation class diagram.

## What changed since Prototype 1
- `models.py` follows the **implementation class diagram** (Milestone 5):
  - Person and Booking (abstract) are no longer classes: their attributes and methods are written
    out in Admin, SalesManager, Receptionist, Customer, SalesAppointment and TestDrive.
  - Associations are attributes that hold the related objects (e.g. `Customer.status_updates`,
    `StatusUpdate.customer`) instead of ID strings.
  - **All methods are implemented** (Prototype 1 had only the Messaging ones).
    `reschedule()`, `confirm()`, `send()` and `complete()` follow their Milestone 5 method
    specifications; the step numbers are in the code comments.
- `schema.sql`: new status values (Booking: Completed; Message: Composed, Scheduled, Cancelled),
  `report.content` and `automation_rule.sales_manager_id`.
- `main.py`: a demo that walks through all seven use cases and saves the results in the database.
- `test_methods.py`: 31 tests, at least one for every method, grouped by use case.

## Files
| File | Purpose |
|---|---|
| `models.py` | The 14 classes of the implementation class diagram, with attributes and methods |
| `schema.sql` | Database tables (data management layer) |
| `db.py` | Database service (SQLite). `init_db()` builds the tables from `schema.sql` |
| `main.py` | Demo of UC1–UC7, then saves and reads back from the database |
| `test_methods.py` | Unit tests for every method |

## Run it
Requires Python 3.10+ (no extra packages).

    python main.py                          # demo of the seven use cases
    python -m unittest test_methods -v      # run the tests

Names use Python's snake_case: `personID` → `person_id`, `addStatusUpdate()` → `add_status_update()`.

## Team 23
| Member | Use case |
|---|---|
| Vincent Mousseau | UC1 Create and manage profiles |
| Ludovic Missihoun | UC2 Scheduling system |
| Sameer Grover | UC3 Automation and reporting |
| Aiden Cheong | UC4 Booking system for test driving |
| Pierre El-Gemayel | UC5 Tracking for the customer |
| Mohammed Altheni | UC6 Messaging system |
| Abd-Al Karim Taylouni | UC7 Customer service system |

Branch workflow: one branch per change, merged into `main` by pull request.

## Project progress
| Deliverable | Status | Where |
|---|---|---|
| Prototype 1 – classes, attributes, database | Submitted | `main` history |
| Prototype 2 – all methods implemented | Done, due Nov 22 | Release / tag `Prototype_2` |
| Milestone 5 – implementation class diagram, method contracts and specifications | Done, due Nov 22 | Course documents |
| Final prototype | Next | `main` |

`docs/` holds the Milestone 3 class diagram and CRC cards used for Prototype 1. The current design is
the Milestone 5 implementation class diagram, which `models.py` follows.
