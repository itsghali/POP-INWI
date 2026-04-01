"""Tests for lazy tab rendering in src.ui.app_orchestrator."""
from datetime import datetime
import sys
import types

import pandas as pd

from src.ui import app_orchestrator


def _make_tab_module(module_name: str, calls: list[str]) -> types.ModuleType:
    module = types.ModuleType(module_name)

    def _render_tab(*args, **kwargs):
        calls.append(module_name)

    module.render_tab = _render_tab
    return module


def test_render_active_tab_calls_only_selected_renderer(monkeypatch):
    calls: list[str] = []
    module_name = "src.ui.tabs.tab01_vue_ensemble"
    monkeypatch.setitem(sys.modules, module_name, _make_tab_module(module_name, calls))

    app_orchestrator.render_active_tab(
        active_tab=app_orchestrator.TAB_LABELS[0],
        filtered_data=pd.DataFrame(),
        unfiltered_data=pd.DataFrame(),
        start_date=datetime(2024, 1, 1),
        end_date=datetime(2024, 1, 2),
        selected_region="R1",
        selected_pop="P1",
        store=None,
    )

    assert calls == [module_name]


def test_orchestrate_dashboard_skips_render_when_no_data(monkeypatch):
    called = {"no_data": 0, "render": 0}

    monkeypatch.setattr(
        app_orchestrator, "create_navigation", lambda: app_orchestrator.TAB_LABELS[0]
    )
    monkeypatch.setattr(
        app_orchestrator,
        "show_no_data_message",
        lambda *args, **kwargs: called.__setitem__("no_data", called["no_data"] + 1),
    )
    monkeypatch.setattr(
        app_orchestrator,
        "render_active_tab",
        lambda *args, **kwargs: called.__setitem__("render", called["render"] + 1),
    )

    app_orchestrator.orchestrate_dashboard(
        filtered_data=pd.DataFrame(),
        unfiltered_data=pd.DataFrame(),
        start_date=datetime(2024, 1, 1),
        end_date=datetime(2024, 1, 2),
        selected_region="R1",
        selected_pop="P1",
        store=None,
    )

    assert called["no_data"] == 1
    assert called["render"] == 0
