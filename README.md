# BlackRoad Event Manager

> Event management and registration platform — SQLite-backed, zero-dependency Python.

## Features

- **Events** — conference / webinar / workshop / meetup lifecycle
- **Registration** — auto-waitlist when capacity is reached
- **Check-in** — mark attendees as arrived
- **Sessions** — multi-track session scheduling with rooms
- **Notifications** — reminder simulation with recipient lists
- **Analytics** — fill rate, check-in rate, revenue, ticket breakdown

## Quick Start

```python
from event_manager import EventManager, EventType, TicketType

em = EventManager("events.db")

event = em.create_event("Dev Summit", EventType.CONFERENCE,
                         "2025-09-15T09:00:00", "2025-09-15T18:00:00",
                         "Austin Convention Center", max_attendees=200, price=299.0)
em.publish_event(event.id)

attendee = em.register_attendee(event.id, "Alice Johnson", "alice@co.com", TicketType.VIP)
em.check_in(attendee.id)

em.add_session(event.id, "Keynote", "Alice Chen",
               "2025-09-15T09:00:00", "2025-09-15T10:00:00", room="Main Hall")

print(em.event_report(event.id))
```

## Running Tests

```bash
pip install pytest
pytest test_event_manager.py -v
```
