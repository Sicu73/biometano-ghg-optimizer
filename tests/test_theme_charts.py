# -*- coding: utf-8 -*-
"""Test dei colori dei grafici nel tema scuro (theme_charts.py)."""
import re
import sys
from pathlib import Path

import plotly.graph_objects as go
import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from theme_charts import (  # noqa: E402
    DARK_BACKGROUND,
    MIN_CONTRAST,
    adapt_figure_for_dark,
    contrast_ratio,
    lift_for_dark,
)

DARK_PAPER = "#15140F"  # BG_APP del tema scuro, più scuro di DARK_BACKGROUND
NAVY = "#15242E"


def _feedstock_colors() -> list[str]:
    """Colori di FEEDSTOCK_DB letti dal sorgente, senza importare core/
    (core/__init__ avvia il motore di calcolo e l'app)."""
    text = (ROOT / "core" / "feedstock_db.py").read_text(encoding="utf-8")
    return sorted(set(re.findall(r'"color"\s*:\s*"(#[0-9A-Fa-f]{6})"', text)))


def test_contrast_ratio_extremes():
    assert contrast_ratio("#000000", "#ffffff") == pytest.approx(21.0)
    assert contrast_ratio("#ffffff", "#ffffff") == pytest.approx(1.0)


def test_navy_netti_becomes_visible_on_dark():
    assert contrast_ratio(NAVY, DARK_BACKGROUND) < 1.5  # il difetto di partenza
    lifted = lift_for_dark(NAVY)
    assert lifted != NAVY
    assert contrast_ratio(lifted, DARK_BACKGROUND) >= MIN_CONTRAST
    assert contrast_ratio(lifted, DARK_PAPER) >= MIN_CONTRAST


def test_lift_keeps_hue_family():
    # Il navy schiarito resta un blu-grigio: il blu supera il rosso.
    r, g, b = (int(lift_for_dark(NAVY)[i:i + 2], 16) for i in (1, 3, 5))
    assert b > r


@pytest.mark.parametrize("color", ["#A49D8C", "#9A7B3C", "#C9A968", "#E8E3D5"])
def test_readable_colors_unchanged(color):
    assert lift_for_dark(color) == color


@pytest.mark.parametrize("value", ["rgba(0,0,0,0)", "red", "", None, 42])
def test_non_hex_values_unchanged(value):
    assert lift_for_dark(value) == value


def test_every_feedstock_color_readable_on_dark():
    colors = _feedstock_colors()
    assert len(colors) >= 30  # FEEDSTOCK_DB letto davvero
    low = [c for c in colors if contrast_ratio(lift_for_dark(c), DARK_BACKGROUND) < MIN_CONTRAST]
    assert low == []


def test_adapt_figure_for_dark_covers_bars_pies_scales_shapes():
    fig = go.Figure()
    fig.add_trace(go.Bar(x=[1, 2], y=[3, 4], marker_color="#A49D8C", name="lordi"))
    fig.add_trace(go.Bar(x=[1, 2], y=[2, 3], marker_color=NAVY, name="netti"))
    fig.add_trace(go.Bar(x=[1, 2], y=[1, 2], marker_color=["#C0392B", "#3C6A52"]))
    fig.add_trace(go.Bar(x=[1, 2], y=[5, 6], marker=dict(
        color=[80.0, 95.0],
        colorscale=[[0, "#C0392B"], [0.5, "#9A7B3C"], [1, "#3C6A52"]],
    )))
    fig.add_trace(go.Pie(labels=["a", "b"], values=[1, 1], marker=dict(colors=["#880E4F", "#FFE082"])))
    fig.add_hline(y=80, line_color="#C0392B")
    fig.update_layout(colorway=[NAVY, "#9A7B3C"])

    adapt_figure_for_dark(fig)

    lordi, netti, pos_neg, scale_bar, pie = fig.data
    assert lordi.marker.color == "#A49D8C"  # già leggibile: invariato
    assert contrast_ratio(netti.marker.color, DARK_BACKGROUND) >= MIN_CONTRAST
    assert all(contrast_ratio(c, DARK_BACKGROUND) >= MIN_CONTRAST for c in pos_neg.marker.color)
    assert tuple(scale_bar.marker.color) == (80.0, 95.0)  # valori numerici della scala intatti
    assert all(contrast_ratio(stop[1], DARK_BACKGROUND) >= MIN_CONTRAST
               for stop in scale_bar.marker.colorscale)
    assert all(contrast_ratio(c, DARK_BACKGROUND) >= MIN_CONTRAST for c in pie.marker.colors)
    assert pie.marker.colors[1] == "#FFE082"
    assert all(contrast_ratio(c, DARK_BACKGROUND) >= MIN_CONTRAST for c in fig.layout.colorway)
    assert contrast_ratio(fig.layout.shapes[0].line.color, DARK_BACKGROUND) >= MIN_CONTRAST


def test_named_colorscale_lifted_keeping_positions():
    # Plotly espande 'Viridis' in stop esadecimali: l'estremo viola scuro va schiarito.
    fig = go.Figure(go.Bar(x=[1], y=[1], marker=dict(color=[1.0], colorscale="Viridis")))
    before = fig.data[0].marker.colorscale
    adapt_figure_for_dark(fig)
    after = fig.data[0].marker.colorscale
    assert [s[0] for s in after] == [s[0] for s in before]
    assert all(contrast_ratio(s[1], DARK_BACKGROUND) >= MIN_CONTRAST for s in after)
    assert after[-1][1] == before[-1][1]  # il giallo finale era già leggibile
