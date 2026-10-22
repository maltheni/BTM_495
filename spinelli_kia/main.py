"""Prototype demo: creates the database, saves sample data and reads it back."""
from datetime import datetime
import db
from models import (Customer, Receptionist, SalesManager, Conversation, Message)


def main():
    db.init_db()
    cust = Customer(person_id="C001", name="Alex Tremblay", email="alex@example.com",
                    phone_number="514-555-0101", messaging_consent=True,
                    vehicle_interest="Kia Seltos")
    rec = Receptionist(person_id="R001", name="Sam Lee", email="sam@spinellikia.example")
    mgr = SalesManager(person_id="M001", name="Jordan Roy", sales_team="New cars")

    with db.connect() as conn:
        for p in (cust, rec, mgr):
            conn.execute("INSERT OR REPLACE INTO person VALUES (?,?,?,?)",
                         (p.person_id, p.name, p.email, p.phone_number))
        conn.execute("INSERT OR REPLACE INTO receptionist VALUES (?,?)", (rec.person_id, rec.shift))
        conn.execute("INSERT OR REPLACE INTO sales_manager VALUES (?,?)", (mgr.person_id, mgr.sales_team))
        conn.execute("""INSERT OR REPLACE INTO customer
            (person_id, vehicle_interest, preferred_language, messaging_consent, created_date, lead_source)
            VALUES (?,?,?,?,?,?)""",
            (cust.person_id, cust.vehicle_interest, cust.preferred_language,
             int(cust.messaging_consent), str(cust.created_date), cust.lead_source))

        # UC6: customer contacts the receptionist, receptionist replies, then escalates
        conv = Conversation(conversation_id="CV001", customer_id=cust.person_id, subject="Seltos pricing")
        conv.assign_to(rec.person_id)
        m1 = Message(message_id="MS001", conversation_id=conv.conversation_id,
                     title="Question", content="What is the price of the Seltos?",
                     sender_role="Customer")
        if m1.validate(cust.messaging_consent):
            m1.send(); conv.add_message(m1)
        m2 = Message(message_id="MS002", conversation_id=conv.conversation_id,
                     title="Re: Question", content="Let me check with the sales manager.",
                     sender_role="Receptionist")
        m2.send(); conv.add_message(m2)
        conv.escalate_to(mgr.person_id)

        conn.execute("""INSERT OR REPLACE INTO conversation VALUES (?,?,?,?,?,?,?,?)""",
            (conv.conversation_id, conv.customer_id, conv.receptionist_id, conv.sales_manager_id,
             conv.subject, conv.status, str(conv.start_date), str(conv.last_activity_date)))
        for m in conv.get_messages():
            conn.execute("""INSERT OR REPLACE INTO message
                (message_id, conversation_id, title, content, sent_date_time, status, channel,
                 sender_role, message_type) VALUES (?,?,?,?,?,?,?,?,?)""",
                (m.message_id, m.conversation_id, m.title, m.content, str(m.sent_date_time),
                 m.status, m.channel, m.sender_role, m.message_type))

        print("Tables:", [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")])
        row = conn.execute("""SELECT c.conversation_id, c.status, COUNT(m.message_id) AS messages
                              FROM conversation c JOIN message m USING (conversation_id)
                              GROUP BY c.conversation_id""").fetchone()
        print("Conversation:", dict(row))


if __name__ == "__main__":
    main()
