from app.core.cache import cache_delete, cache_get, cache_set, cache_stats, mark_redis_unavailable, reset_cache_client
from app.services.events import publish_event


def test_cache_miss_then_hit_when_redis_optional():
    reset_cache_client()
    cache_delete("proof:test")
    assert cache_get("proof:test") is None
    cache_set("proof:test", {"ok": True}, 30)
    cached = cache_get("proof:test")
    stats = cache_stats()
    assert stats["hits"] + stats["misses"] >= 1
    if stats["available"]:
        assert cached == {"ok": True}
        cache_delete("proof:test")
        assert cache_get("proof:test") is None


def test_cache_and_events_survive_redis_outage():
    mark_redis_unavailable()
    assert cache_get("anything") is None
    cache_set("anything", {"x": 1})
    assert publish_event("LoanDecisionGenerated", {"applicationId": 1}) is None
    reset_cache_client()
