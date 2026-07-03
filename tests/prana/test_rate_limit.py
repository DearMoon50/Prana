import backend.main as main


def test_expired_ip_entries_are_evicted(monkeypatch):
    main._window_store.clear()
    fake_now = [1000.0]
    monkeypatch.setattr(main.time, "time", lambda: fake_now[0])

    main._window_store["1.2.3.4"] = [900.0, 905.0]
    main._evict_stale_windows(now=1000.0)
    assert "1.2.3.4" not in main._window_store