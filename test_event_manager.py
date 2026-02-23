"""pytest tests for BlackRoad Event Manager"""
import pytest
from event_manager import (EventManager, EventType, EventStatus,
                            TicketType, PaymentStatus)


@pytest.fixture
def em(tmp_path):
    e = EventManager(str(tmp_path / "test.db"))
    yield e
    e.close()


@pytest.fixture
def published_event(em):
    evt = em.create_event("Test Event", EventType.CONFERENCE,
                          "2025-09-15T09:00:00", "2025-09-15T18:00:00",
                          "Convention Center", 3, price=100.0)
    published = em.publish_event(evt.id)
    return published


def test_create_event(em):
    evt = em.create_event("Summit", EventType.WEBINAR,
                          "2025-06-01T09:00:00", "2025-06-01T12:00:00",
                          "Online", 100)
    assert evt.id
    assert evt.status == EventStatus.DRAFT

def test_publish_event(em, published_event):
    assert published_event.status == EventStatus.PUBLISHED

def test_register_attendee(em, published_event):
    a = em.register_attendee(published_event.id, "Alice", "alice@test.com")
    assert a.id
    assert not a.waitlisted

def test_waitlist_when_full(em, published_event):
    em.register_attendee(published_event.id, "A", "a@test.com")
    em.register_attendee(published_event.id, "B", "b@test.com")
    em.register_attendee(published_event.id, "C", "c@test.com")
    a4 = em.register_attendee(published_event.id, "D", "d@test.com")
    assert a4.waitlisted

def test_check_in(em, published_event):
    a = em.register_attendee(published_event.id, "Bob", "bob@test.com")
    checked = em.check_in(a.id)
    assert checked.checked_in_at is not None

def test_get_waitlist(em, published_event):
    for i in range(4):
        em.register_attendee(published_event.id, f"Person{i}", f"p{i}@test.com")
    wl = em.get_waitlist(published_event.id)
    assert len(wl) == 1

def test_add_session(em, published_event):
    s = em.add_session(published_event.id, "Keynote", "Speaker One",
                       "2025-09-15T09:00:00", "2025-09-15T10:00:00", "Main Hall")
    assert s.id

def test_event_report(em, published_event):
    em.register_attendee(published_event.id, "Alice", "alice@test.com")
    report = em.event_report(published_event.id)
    assert report["registered"] == 1
    assert report["capacity"] == 3

def test_send_reminder(em, published_event):
    em.register_attendee(published_event.id, "Alice", "alice@test.com")
    result = em.send_reminder(published_event.id, days_before=2)
    assert result["recipients"] == 1

def test_cancel_event(em, published_event):
    cancelled = em.cancel_event(published_event.id)
    assert cancelled.status == EventStatus.CANCELLED

def test_free_event_payment_waived(em):
    evt = em.create_event("Free Meetup", EventType.MEETUP,
                          "2025-06-01T18:00:00", "2025-06-01T20:00:00",
                          "Coffee Shop", 20, price=0.0)
    a = em.register_attendee(evt.id, "Alice", "alice@test.com")
    assert a.payment_status == PaymentStatus.WAIVED
