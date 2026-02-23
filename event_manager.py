"""
BlackRoad Event Manager - Event Management and Registration Platform
SQLite-backed system for events, attendees, sessions, waitlists.
"""

import sqlite3
import json
import uuid
from datetime import datetime, date, timedelta
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from enum import Enum


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class EventType(str, Enum):
    CONFERENCE = "conference"
    WEBINAR = "webinar"
    WORKSHOP = "workshop"
    MEETUP = "meetup"


class EventStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


class PaymentStatus(str, Enum):
    PENDING = "pending"
    PAID = "paid"
    REFUNDED = "refunded"
    WAIVED = "waived"


class TicketType(str, Enum):
    GENERAL = "general"
    VIP = "vip"
    STUDENT = "student"
    SPEAKER = "speaker"
    SPONSOR = "sponsor"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class Event:
    id: str
    title: str
    type: EventType
    description: str
    start_dt: str
    end_dt: str
    location: str
    max_attendees: int
    price: float = 0.0
    status: EventStatus = EventStatus.DRAFT
    organizer: str = ""
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class Attendee:
    id: str
    event_id: str
    name: str
    email: str
    ticket_type: TicketType = TicketType.GENERAL
    registered_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    checked_in_at: Optional[str] = None
    payment_status: PaymentStatus = PaymentStatus.PENDING
    waitlisted: bool = False
    notes: str = ""


@dataclass
class Session:
    id: str
    event_id: str
    title: str
    speaker: str
    start_dt: str
    end_dt: str
    room: str = ""
    capacity: int = 0
    description: str = ""
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

class EventDatabase:
    def __init__(self, db_path: str = "events.db"):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        with self.conn:
            self.conn.executescript("""
                CREATE TABLE IF NOT EXISTS events (
                    id            TEXT PRIMARY KEY,
                    title         TEXT NOT NULL,
                    type          TEXT NOT NULL,
                    description   TEXT DEFAULT '',
                    start_dt      TEXT NOT NULL,
                    end_dt        TEXT NOT NULL,
                    location      TEXT DEFAULT '',
                    max_attendees INTEGER DEFAULT 0,
                    price         REAL DEFAULT 0,
                    status        TEXT DEFAULT 'draft',
                    organizer     TEXT DEFAULT '',
                    created_at    TEXT NOT NULL,
                    updated_at    TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS attendees (
                    id             TEXT PRIMARY KEY,
                    event_id       TEXT NOT NULL REFERENCES events(id),
                    name           TEXT NOT NULL,
                    email          TEXT NOT NULL,
                    ticket_type    TEXT DEFAULT 'general',
                    registered_at  TEXT NOT NULL,
                    checked_in_at  TEXT,
                    payment_status TEXT DEFAULT 'pending',
                    waitlisted     INTEGER DEFAULT 0,
                    notes          TEXT DEFAULT '',
                    UNIQUE(event_id, email)
                );

                CREATE TABLE IF NOT EXISTS sessions (
                    id          TEXT PRIMARY KEY,
                    event_id    TEXT NOT NULL REFERENCES events(id),
                    title       TEXT NOT NULL,
                    speaker     TEXT NOT NULL,
                    start_dt    TEXT NOT NULL,
                    end_dt      TEXT NOT NULL,
                    room        TEXT DEFAULT '',
                    capacity    INTEGER DEFAULT 0,
                    description TEXT DEFAULT '',
                    created_at  TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_att_event ON attendees(event_id);
                CREATE INDEX IF NOT EXISTS idx_att_email ON attendees(email);
                CREATE INDEX IF NOT EXISTS idx_sess_event ON sessions(event_id);
            """)


# ---------------------------------------------------------------------------
# Event Manager Service
# ---------------------------------------------------------------------------

class EventManager:
    def __init__(self, db_path: str = "events.db"):
        self.db = EventDatabase(db_path)
        self.conn = self.db.conn

    # -----------------------------------------------------------------------
    # Event CRUD
    # -----------------------------------------------------------------------

    def create_event(
        self,
        title: str,
        event_type: EventType,
        start_dt: str,
        end_dt: str,
        location: str,
        max_attendees: int,
        description: str = "",
        price: float = 0.0,
        organizer: str = "",
    ) -> Event:
        now = datetime.utcnow().isoformat()
        event = Event(
            id=str(uuid.uuid4()),
            title=title,
            type=event_type,
            description=description,
            start_dt=start_dt,
            end_dt=end_dt,
            location=location,
            max_attendees=max_attendees,
            price=price,
            organizer=organizer,
            created_at=now,
            updated_at=now,
        )
        with self.conn:
            self.conn.execute(
                """INSERT INTO events
                   (id, title, type, description, start_dt, end_dt, location,
                    max_attendees, price, status, organizer, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (event.id, event.title, event.type.value, event.description,
                 event.start_dt, event.end_dt, event.location, event.max_attendees,
                 event.price, event.status.value, event.organizer,
                 event.created_at, event.updated_at),
            )
        return event

    def get_event(self, event_id: str) -> Optional[Event]:
        row = self.conn.execute(
            "SELECT * FROM events WHERE id = ?", (event_id,)
        ).fetchone()
        return self._row_to_event(row) if row else None

    def list_events(
        self,
        status: Optional[EventStatus] = None,
        event_type: Optional[EventType] = None,
    ) -> List[Event]:
        query = "SELECT * FROM events WHERE 1=1"
        params: List[Any] = []
        if status:
            query += " AND status = ?"
            params.append(status.value)
        if event_type:
            query += " AND type = ?"
            params.append(event_type.value)
        rows = self.conn.execute(query, params).fetchall()
        return [self._row_to_event(r) for r in rows]

    def publish_event(self, event_id: str) -> Optional[Event]:
        return self._set_status(event_id, EventStatus.PUBLISHED)

    def cancel_event(self, event_id: str) -> Optional[Event]:
        return self._set_status(event_id, EventStatus.CANCELLED)

    def complete_event(self, event_id: str) -> Optional[Event]:
        return self._set_status(event_id, EventStatus.COMPLETED)

    def _set_status(self, event_id: str, status: EventStatus) -> Optional[Event]:
        if not self.get_event(event_id):
            return None
        now = datetime.utcnow().isoformat()
        with self.conn:
            self.conn.execute(
                "UPDATE events SET status = ?, updated_at = ? WHERE id = ?",
                (status.value, now, event_id),
            )
        return self.get_event(event_id)

    # -----------------------------------------------------------------------
    # Attendee management
    # -----------------------------------------------------------------------

    def register_attendee(
        self,
        event_id: str,
        name: str,
        email: str,
        ticket_type: TicketType = TicketType.GENERAL,
        notes: str = "",
    ) -> Attendee:
        """Register for an event. Auto-waitlists if full."""
        event = self.get_event(event_id)
        if not event:
            raise ValueError(f"Event {event_id} not found")
        if event.status not in (EventStatus.PUBLISHED, EventStatus.DRAFT):
            raise ValueError(f"Event is {event.status.value}, cannot register")
        # Check capacity
        current = self._registered_count(event_id)
        waitlisted = current >= event.max_attendees
        attendee = Attendee(
            id=str(uuid.uuid4()),
            event_id=event_id,
            name=name,
            email=email,
            ticket_type=ticket_type,
            waitlisted=waitlisted,
            notes=notes,
            payment_status=PaymentStatus.WAIVED if event.price == 0 else PaymentStatus.PENDING,
        )
        with self.conn:
            self.conn.execute(
                """INSERT INTO attendees
                   (id, event_id, name, email, ticket_type, registered_at,
                    checked_in_at, payment_status, waitlisted, notes)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (attendee.id, attendee.event_id, attendee.name, attendee.email,
                 attendee.ticket_type.value, attendee.registered_at,
                 attendee.checked_in_at, attendee.payment_status.value,
                 1 if attendee.waitlisted else 0, attendee.notes),
            )
        return attendee

    def check_in(self, attendee_id: str) -> Optional[Attendee]:
        """Mark attendee as checked in."""
        row = self.conn.execute(
            "SELECT * FROM attendees WHERE id = ?", (attendee_id,)
        ).fetchone()
        if not row:
            return None
        now = datetime.utcnow().isoformat()
        with self.conn:
            self.conn.execute(
                "UPDATE attendees SET checked_in_at = ? WHERE id = ?",
                (now, attendee_id),
            )
        return self._row_to_attendee(
            self.conn.execute("SELECT * FROM attendees WHERE id = ?", (attendee_id,)).fetchone()
        )

    def cancel_registration(self, attendee_id: str) -> bool:
        with self.conn:
            cursor = self.conn.execute(
                "DELETE FROM attendees WHERE id = ?", (attendee_id,)
            )
        return cursor.rowcount > 0

    def get_attendees(self, event_id: str, waitlisted: Optional[bool] = None) -> List[Attendee]:
        query = "SELECT * FROM attendees WHERE event_id = ?"
        params: List[Any] = [event_id]
        if waitlisted is not None:
            query += " AND waitlisted = ?"
            params.append(1 if waitlisted else 0)
        rows = self.conn.execute(query, params).fetchall()
        return [self._row_to_attendee(r) for r in rows]

    def get_waitlist(self, event_id: str) -> List[Attendee]:
        return self.get_attendees(event_id, waitlisted=True)

    def update_payment(self, attendee_id: str, status: PaymentStatus) -> Optional[Attendee]:
        row = self.conn.execute(
            "SELECT * FROM attendees WHERE id = ?", (attendee_id,)
        ).fetchone()
        if not row:
            return None
        with self.conn:
            self.conn.execute(
                "UPDATE attendees SET payment_status = ? WHERE id = ?",
                (status.value, attendee_id),
            )
        return self._row_to_attendee(
            self.conn.execute("SELECT * FROM attendees WHERE id = ?", (attendee_id,)).fetchone()
        )

    # -----------------------------------------------------------------------
    # Sessions
    # -----------------------------------------------------------------------

    def add_session(
        self,
        event_id: str,
        title: str,
        speaker: str,
        start_dt: str,
        end_dt: str,
        room: str = "",
        capacity: int = 0,
        description: str = "",
    ) -> Session:
        if not self.get_event(event_id):
            raise ValueError(f"Event {event_id} not found")
        session = Session(
            id=str(uuid.uuid4()),
            event_id=event_id,
            title=title,
            speaker=speaker,
            start_dt=start_dt,
            end_dt=end_dt,
            room=room,
            capacity=capacity,
            description=description,
        )
        with self.conn:
            self.conn.execute(
                """INSERT INTO sessions
                   (id, event_id, title, speaker, start_dt, end_dt, room, capacity, description, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (session.id, session.event_id, session.title, session.speaker,
                 session.start_dt, session.end_dt, session.room, session.capacity,
                 session.description, session.created_at),
            )
        return session

    def list_sessions(self, event_id: str) -> List[Session]:
        rows = self.conn.execute(
            "SELECT * FROM sessions WHERE event_id = ? ORDER BY start_dt", (event_id,)
        ).fetchall()
        return [Session(id=r["id"], event_id=r["event_id"], title=r["title"],
                        speaker=r["speaker"], start_dt=r["start_dt"], end_dt=r["end_dt"],
                        room=r["room"], capacity=r["capacity"],
                        description=r["description"], created_at=r["created_at"])
                for r in rows]

    # -----------------------------------------------------------------------
    # Notifications (simulated)
    # -----------------------------------------------------------------------

    def send_reminder(self, event_id: str, days_before: int = 1) -> Dict[str, Any]:
        """Simulate sending reminder emails. Returns summary."""
        event = self.get_event(event_id)
        if not event:
            raise ValueError(f"Event {event_id} not found")
        attendees = self.get_attendees(event_id, waitlisted=False)
        emails = [a.email for a in attendees if a.checked_in_at is None]
        return {
            "event": event.title,
            "days_before": days_before,
            "recipients": len(emails),
            "emails": emails,
            "message": f"Reminder: {event.title} starts on {event.start_dt}",
        }

    # -----------------------------------------------------------------------
    # Analytics
    # -----------------------------------------------------------------------

    def event_report(self, event_id: str) -> Dict[str, Any]:
        """Full event statistics report."""
        event = self.get_event(event_id)
        if not event:
            raise ValueError(f"Event {event_id} not found")
        attendees = self.get_attendees(event_id)
        registered = [a for a in attendees if not a.waitlisted]
        waitlisted = [a for a in attendees if a.waitlisted]
        checked_in = [a for a in registered if a.checked_in_at]
        paid = [a for a in registered if a.payment_status == PaymentStatus.PAID]
        revenue = len(paid) * event.price
        sessions = self.list_sessions(event_id)
        ticket_breakdown: Dict[str, int] = {}
        for a in registered:
            ticket_breakdown[a.ticket_type.value] = ticket_breakdown.get(a.ticket_type.value, 0) + 1
        return {
            "event_id": event_id,
            "title": event.title,
            "type": event.type.value,
            "status": event.status.value,
            "capacity": event.max_attendees,
            "registered": len(registered),
            "waitlisted": len(waitlisted),
            "checked_in": len(checked_in),
            "no_show": len(registered) - len(checked_in),
            "check_in_rate": round(len(checked_in) / len(registered), 3) if registered else 0,
            "fill_rate": round(len(registered) / event.max_attendees, 3) if event.max_attendees else 0,
            "ticket_breakdown": ticket_breakdown,
            "revenue": round(revenue, 2),
            "sessions": len(sessions),
            "start_dt": event.start_dt,
            "end_dt": event.end_dt,
            "location": event.location,
        }

    # -----------------------------------------------------------------------
    # Private helpers
    # -----------------------------------------------------------------------

    def _registered_count(self, event_id: str) -> int:
        return self.conn.execute(
            "SELECT COUNT(*) FROM attendees WHERE event_id = ? AND waitlisted = 0",
            (event_id,),
        ).fetchone()[0]

    def _row_to_event(self, row: sqlite3.Row) -> Event:
        return Event(
            id=row["id"], title=row["title"], type=EventType(row["type"]),
            description=row["description"], start_dt=row["start_dt"],
            end_dt=row["end_dt"], location=row["location"],
            max_attendees=row["max_attendees"], price=row["price"],
            status=EventStatus(row["status"]), organizer=row["organizer"],
            created_at=row["created_at"], updated_at=row["updated_at"],
        )

    def _row_to_attendee(self, row: sqlite3.Row) -> Attendee:
        return Attendee(
            id=row["id"], event_id=row["event_id"], name=row["name"],
            email=row["email"], ticket_type=TicketType(row["ticket_type"]),
            registered_at=row["registered_at"], checked_in_at=row["checked_in_at"],
            payment_status=PaymentStatus(row["payment_status"]),
            waitlisted=bool(row["waitlisted"]), notes=row["notes"],
        )

    def close(self) -> None:
        self.conn.close()


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------

def demo() -> None:
    import tempfile, os
    db_file = tempfile.mktemp(suffix=".db")
    em = EventManager(db_file)

    print("\n=== Creating Event ===")
    evt = em.create_event(
        "BlackRoad Dev Summit 2025", EventType.CONFERENCE,
        "2025-09-15T09:00:00", "2025-09-15T18:00:00",
        "Austin Convention Center", max_attendees=3,
        price=299.0, organizer="BlackRoad Foundation",
    )
    em.publish_event(evt.id)
    print(f"  Created: {evt.title}")

    print("\n=== Adding Sessions ===")
    em.add_session(evt.id, "Keynote: BlackRoad OS Future", "Alice Chen",
                   "2025-09-15T09:00:00", "2025-09-15T10:00:00", room="Main Hall", capacity=500)
    em.add_session(evt.id, "AI Agents Workshop", "Bob Martinez",
                   "2025-09-15T10:30:00", "2025-09-15T12:00:00", room="Room A", capacity=50)
    print("  Sessions added")

    print("\n=== Registering Attendees ===")
    a1 = em.register_attendee(evt.id, "Alice Johnson", "alice@test.com", TicketType.VIP)
    a2 = em.register_attendee(evt.id, "Bob Smith", "bob@test.com")
    a3 = em.register_attendee(evt.id, "Carol Lee", "carol@test.com")
    a4 = em.register_attendee(evt.id, "Dave Nguyen", "dave@test.com")  # waitlisted
    print(f"  Registered: {a1.name} ({a1.ticket_type.value}), {a2.name}, {a3.name}")
    print(f"  Waitlisted: {a4.name} — {a4.waitlisted}")

    print("\n=== Check-in ===")
    em.check_in(a1.id)
    em.check_in(a2.id)
    print("  Alice and Bob checked in")

    print("\n=== Reminder ===")
    reminder = em.send_reminder(evt.id, days_before=1)
    print(f"  Sent to {reminder['recipients']} attendees")

    print("\n=== Event Report ===")
    report = em.event_report(evt.id)
    for k, v in report.items():
        if k not in ("event_id", "start_dt", "end_dt", "location"):
            print(f"  {k}: {v}")

    em.close()
    os.unlink(db_file)
    print("\n✓ Demo complete")


if __name__ == "__main__":
    demo()
