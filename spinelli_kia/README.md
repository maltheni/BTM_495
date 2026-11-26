# Spinelli Kia Sales System – Final Prototype (BTM 495, Team 23)

A working web application for the seven use cases of the Spinelli Kia sales system, with
the screens of Milestone 6, the classes and methods of Milestone 5, and the layers of the
Milestone 7 deployment design.

## Run it

Requires Python 3.10 or later.

    cd spinelli_kia
    python -m pip install -r requirements.txt      # installs Django 5.2
    python manage.py runserver

Then open **http://127.0.0.1:8000** in a browser. The demo data is created automatically the
first time. To start again from the original data, use **Switches and reset → Reset demo data**
in the dark bar at the bottom of every page (do this before the presentation).

Online copy (same app, hosted on PythonAnywhere): **https://maltheni.pythonanywhere.com**

| Who | How to sign in |
|---|---|
| Customer | Sign In (top right): `marie.tremblay@mail.com`, password `spinelli` (every demo customer uses `spinelli`) |
| Receptionist, sales managers, admin | Staff portal (bottom right) and choose Sam Lee, Jordan Roy, Nadia Haddad or Ana Costa |

## What each use case can do

| Use case | Where | Normal flow | Error and alternate flows you can show |
|---|---|---|---|
| UC1 Create and manage profiles | Staff → Customers | Search, open a profile, edit and save (history line added), create a customer | No matching customer (3a), possible duplicate warning (3b), validation errors (6a) |
| UC2 Scheduling | Staff → Schedule; Sales manager → Schedule | Book and confirm an appointment (confirmation + reminder), move it, cancel it, complete it | Slot taken or blocked (S-1a); manager blocks a period of unavailability (S-3) |
| UC3 Automation and reporting | Admin → Automation Rules | Create a rule, Run now: report generated and emailed to the sales manager | No data available (alternate 1), rule without a sales manager: generation error (alternate 2) |
| UC4 Test drive booking | Customer → Book a Test Drive; Staff → Test Drive Requests | Request online, receptionist checks availability and license, confirms (email + reminder) | Form errors, CRM offline (Figure 16), existing customer (Figure 14), invalid license: deny with a reason (Figure 15), vehicle not available, plate and completion |
| UC5 Tracking | Customer → Track my Purchase; Sales manager → My Customers | Manager records a new stage, customer is notified and sees it | Status unavailable (A-1): sign in as `olivier.martin@mail.com` |
| UC6 Messaging | Customer → Messages; Staff → Messages | Send, receptionist notified, reads, replies, customer notified, reads, ends the conversation | Empty fields, message not delivered (5a/8a, switch the reception inbox off), escalation to a sales manager (6a) |
| UC7 Customer service | Customer → Contact Us; Staff → Messages → Service requests | Submit a request (signed in or not), receptionist assigns, resolves and closes it | Missing information (A-1), invalid information (A-2) |

The **Prototype demo tools** page (bottom bar) has two switches to show the exceptional flows
(CRM offline, reception inbox inactive) and lists every email/SMS notification the system sent.

## How it is built (Milestone 7 layers)

| Layer | Files |
|---|---|
| HCI layer (web pages, EN/FR) | `portal/` (Django views, templates, CSS) – the Milestone 6 screens |
| Problem-domain layer | `models.py` – the 14 classes and their methods from Milestone 5 (unchanged from Prototype 2, except the report text) |
| Data management layer | `store.py` (saves and loads the objects), `db.py`, `schema.sql` (SQLite here, PostgreSQL in the final system) |
| Demo data | `seed.py` – the Milestone 6 example data (Marie Tremblay, 2026 Kia Sportage EX, request TD-1042...) |

Django only provides the web pages; the objects are our own classes, saved by our own data layer.
Change from Prototype 2: `booking.customer_id` may be empty, for a sales manager's blocked period (UC2 S-3).

## Tests

    python manage.py test portal            # 27 end-to-end tests: every page and every flow above
    python -m unittest test_methods         # 31 tests of the methods (Prototype 2)
    python main.py                          # console demo of the seven use cases (separate database)

## Photo credits

The vehicle photos come from Wikimedia Commons and are used under their free licences (author and licence on each file page).
The model years may differ from the cars in the demo inventory.

| Vehicle | Wikimedia Commons file |
|---|---|
| Sportage EX | [25 Kia Sportage EX.jpg](https://commons.wikimedia.org/wiki/File:25_Kia_Sportage_EX.jpg) |
| Seltos EX | [2024 Kia Seltos EX, front right, 03-15-2026.jpg](https://commons.wikimedia.org/wiki/File:2024_Kia_Seltos_EX,_front_right,_03-15-2026.jpg) |
| EV6 Wind | [22 Kia EV6 Wind.jpg](https://commons.wikimedia.org/wiki/File:22_Kia_EV6_Wind.jpg) |
| Telluride SX | [24 Kia Telluride SX-Prestige.jpg](https://commons.wikimedia.org/wiki/File:24_Kia_Telluride_SX-Prestige.jpg) |
| Sorento LX | [25 Kia Sorento LX.jpg](https://commons.wikimedia.org/wiki/File:25_Kia_Sorento_LX.jpg) |
| Carnival EX | [2025 Kia Carnival Hybrid EX, front right, 10-12-2025.jpg](https://commons.wikimedia.org/wiki/File:2025_Kia_Carnival_Hybrid_EX,_front_right,_10-12-2025.jpg) |
| K5 GT-Line | [2021 Kia K5 GT-Line, front left, 09-09-2023.jpg](https://commons.wikimedia.org/wiki/File:2021_Kia_K5_GT-Line,_front_left,_09-09-2023.jpg) |
| Niro Hybrid EX | [2023 Kia Niro Hybrid EX in Runway Red, Front Right, 10-09-2023.jpg](https://commons.wikimedia.org/wiki/File:2023_Kia_Niro_Hybrid_EX_in_Runway_Red,_Front_Right,_10-09-2023.jpg) |

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

## Project progress
| Deliverable | Status | Where |
|---|---|---|
| Prototype 1 – classes, attributes, database | Submitted | `main` history |
| Prototype 2 – all methods implemented | Submitted | Release / tag `Prototype_2` |
| Final prototype – working web application | Done | Tag `Final_Prototype` |
