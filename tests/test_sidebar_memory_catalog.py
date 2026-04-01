"""Tests for sidebar memory-catalog behavior."""
from __future__ import annotations

import inspect
from types import SimpleNamespace

from src.services.preload_service import PreloadedStore
from src.ui import sidebar as sidebar_module


class _FakeSidebar:
    def __init__(self, session_state: dict):
        self._session_state = session_state
        self.selectbox_calls: list[dict] = []

    def title(self, *args, **kwargs):
        return None

    def markdown(self, *args, **kwargs):
        return None

    def warning(self, *args, **kwargs):
        return None

    def info(self, *args, **kwargs):
        return None

    def caption(self, *args, **kwargs):
        return None

    def success(self, *args, **kwargs):
        return None

    def button(self, *args, **kwargs):
        return False

    def progress(self, *args, **kwargs):
        return None

    def selectbox(self, _label, options, key=None, **kwargs):
        format_func = kwargs.get("format_func", lambda value: value)
        self.selectbox_calls.append(
            {
                "label": _label,
                "options": list(options),
                "formatted_options": [format_func(option) for option in options],
                "key": key,
            }
        )
        if key and self._session_state.get(key) in options:
            return self._session_state[key]
        value = options[0]
        if key:
            self._session_state[key] = value
        return value


class _FakeStreamlit:
    def __init__(self):
        self.session_state: _SessionState = _SessionState()
        self.sidebar = _FakeSidebar(self.session_state)

    def error(self, message):
        raise AssertionError(message)

    def stop(self):
        raise AssertionError("st.stop() should not be called in this test")

    def rerun(self):
        return None


class _FakePeriodSelector:
    def __init__(self):
        self.initialized = False
        self.rendered = False

    def ensure_initialized(self):
        self.initialized = True

    def render_selector(self, key_suffix=""):
        self.rendered = True
        return None


class _SessionState(dict):
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def __setattr__(self, name, value):
        self[name] = value


def test_sidebar_uses_store_catalog_only(monkeypatch):
    fake_st = _FakeStreamlit()
    fake_period_selector = _FakePeriodSelector()
    monkeypatch.setattr(sidebar_module, "st", fake_st)
    monkeypatch.setattr(sidebar_module, "period_selector", fake_period_selector)

    store = PreloadedStore(
        datasets_by_pop_id={"R1_P1": SimpleNamespace(is_empty=False)},
        catalog_by_region={"R1": ["P1", "P2"]},
        availability_by_pop_id={"R1_P1": True, "R1_P2": False},
        all_regions=["R1"],
        db_version="v1",
    )

    region, pop = sidebar_module.get_region_pop_selection(store)

    assert region == "R1"
    assert pop == "P1"
    assert fake_st.sidebar.selectbox_calls[1]["options"] == ["P1", "P2"]
    assert fake_st.sidebar.selectbox_calls[1]["formatted_options"] == [
        "P1 (données disponibles)",
        "P2 (données indisponibles)",
    ]
    assert fake_period_selector.initialized is True
    assert fake_period_selector.rendered is True


def test_sidebar_keeps_unavailable_pop_selectable(monkeypatch):
    fake_st = _FakeStreamlit()
    fake_st.session_state.selected_region_ui = "R1"
    fake_st.session_state.selected_pop_ui = "P2"
    fake_period_selector = _FakePeriodSelector()
    monkeypatch.setattr(sidebar_module, "st", fake_st)
    monkeypatch.setattr(sidebar_module, "period_selector", fake_period_selector)

    store = PreloadedStore(
        datasets_by_pop_id={"R1_P1": SimpleNamespace(is_empty=False)},
        catalog_by_region={"R1": ["P1", "P2"]},
        availability_by_pop_id={"R1_P1": True, "R1_P2": False},
        all_regions=["R1"],
        db_version="v1",
    )

    region, pop = sidebar_module.get_region_pop_selection(store)

    assert region == "R1"
    assert pop == "P2"
    assert fake_st.sidebar.selectbox_calls[1]["formatted_options"] == [
        "P1 (données disponibles)",
        "P2 (données indisponibles)",
    ]


def test_sidebar_has_no_repository_discovery_calls():
    source = inspect.getsource(sidebar_module.get_region_pop_selection)
    assert "get_regions(" not in source
    assert "get_pops(" not in source
    assert "has_pop_data(" not in source
