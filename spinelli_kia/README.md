# Spinelli Kia Sales System – Prototype 1 (BTM 495, Team 23)

First prototype: version control, database service, and the problem-domain classes
with their attributes (from the Milestone 3 class diagram).

## What is here
| File | Purpose |
|---|---|
| `schema.sql` | Database tables: one per class, foreign keys = associations in the class diagram |
| `db.py` | Database service (SQLite). `init_db()` builds the tables from `schema.sql` |
| `models.py` | The 16 classes and their attributes (Messaging methods implemented) |
| `main.py` | Demo: creates the DB, saves a customer/conversation/messages, reads them back |

## Run it
Requires Python 3.10+ (no extra packages).

    python main.py

The database file `spinelli_kia.db` is created next to the code (it is git-ignored).

## Team
Team 23 – see the Milestone 1–3 documents. Branch workflow: one branch per use case, merge into `main` by pull request.
