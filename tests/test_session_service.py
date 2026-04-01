"""Tests for src.services.session_service."""
from __future__ import annotations

from src.services import session_service


class _SessionState(dict):
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def __setattr__(self, name, value):
        self[name] = value


class _FakeStreamlit:
    def __init__(self):
        self.session_state = _SessionState()


def test_maybe_auto_select_first_ready_pop_sets_initial_selection(monkeypatch):
    fake_st = _FakeStreamlit()
    monkeypatch.setattr(session_service, "st", fake_st)
    monkeypatch.setattr(
        session_service,
        "get_first_loaded_pop",
        lambda store: ("R2", "P3"),
    )
    monkeypatch.setattr(
        session_service,
        "is_pop_loaded",
        lambda store, region, pop: False,
    )

    changed = session_service.maybe_auto_select_first_ready_pop(object())

    assert changed is True
    assert fake_st.session_state.selected_region_ui == "R2"
    assert fake_st.session_state.selected_pop_ui == "P3"
    assert fake_st.session_state.auto_first_pop_applied is True


def test_maybe_auto_select_first_ready_pop_replaces_unready_selection(monkeypatch):
    fake_st = _FakeStreamlit()
    fake_st.session_state.selected_region_ui = "R1"
    fake_st.session_state.selected_pop_ui = "P_missing"
    fake_st.session_state.auto_first_pop_applied = True
    monkeypatch.setattr(session_service, "st", fake_st)
    monkeypatch.setattr(
        session_service,
        "get_first_loaded_pop",
        lambda store: ("R2", "P3"),
    )
    monkeypatch.setattr(
        session_service,
        "is_pop_loaded",
        lambda store, region, pop: (region, pop) == ("R2", "P3"),
    )

    changed = session_service.maybe_auto_select_first_ready_pop(object())

    assert changed is True
    assert fake_st.session_state.selected_region_ui == "R2"
    assert fake_st.session_state.selected_pop_ui == "P3"
    assert fake_st.session_state.auto_first_pop_applied is True
