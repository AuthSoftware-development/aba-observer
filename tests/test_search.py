"""Tests for search engine."""

import os


def test_index_and_search_text():
    from search.engine import index_events, search_text, SEARCH_DB

    # Use a test DB
    index_events([
        {"event_id": "test_s1", "domain": "security", "event_type": "possible_fall",
         "description": "Person fell near entrance", "severity": "high"},
        {"event_id": "test_s2", "domain": "aba", "event_type": "behavior",
         "description": "Client hand flapping detected", "person_name": "Test Client"},
    ])

    results = search_text("fell")
    assert any(r["event_id"] == "test_s1" for r in results)

    results = search_text("flapping")
    assert any(r["event_id"] == "test_s2" for r in results)


def test_search_by_type():
    from search.engine import index_events, search_by_type

    index_events([
        {"event_id": "test_t1", "event_type": "loitering", "description": "Loitering detected"},
    ])

    results = search_by_type("loitering")
    assert any(r["event_id"] == "test_t1" for r in results)


def test_search_by_person():
    from search.engine import index_events, search_by_person

    index_events([
        {"event_id": "test_p1", "person_name": "Jane Doe", "event_type": "behavior",
         "description": "Jane clapping"},
    ])

    results = search_by_person("Jane")
    assert any(r["event_id"] == "test_p1" for r in results)


def test_natural_language_parsing():
    from search.engine import natural_language_to_query

    parsed = natural_language_to_query("show me all falls")
    assert parsed["event_type"] == "possible_fall"

    parsed = natural_language_to_query("find loitering in security")
    assert parsed["event_type"] == "loitering"
    assert parsed["domain"] == "security"


def test_event_stats():
    from search.engine import get_event_stats

    stats = get_event_stats()
    assert "total_events" in stats
    assert "by_type" in stats
    assert "by_domain" in stats
