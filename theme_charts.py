"""Colori dei grafici Plotly nel tema scuro di Metan.iQ.

In scuro i grafici hanno fondo trasparente sulla carta scura (#15140F) o su una
superficie (#1E1C16). I colori di serie pensati per la carta chiara spariscono:
il navy delle barre «Sm³ netti» (#15242E) fa 1,1:1, alcune biomasse di
FEEDSTOCK_DB (#880E4F, #5D4037, #6A1B9A…) restano sotto 2:1.

`adapt_figure_for_dark` schiarisce verso l'avorio dell'inchiostro scuro solo i
colori sotto 3:1 (soglia WCAG 2.x, criterio 1.4.11, per gli elementi grafici),
quanto basta per raggiungerla e mantenendo la tinta. I colori già leggibili
restano identici. Modulo senza dipendenze da Streamlit: si testa da solo.
"""
from __future__ import annotations

import re

# Superficie più chiara su cui può stare un grafico in scuro (BG_SURFACE dark):
# chi supera 3:1 qui lo supera anche sulla carta #15140F, più scura.
DARK_BACKGROUND = "#1E1C16"
# Inchiostro del tema scuro (INK dark di theme_editorial.py): direzione di schiarimento.
DARK_INK = "#E8E3D5"
MIN_CONTRAST = 3.0
_STEP = 0.05

_HEX = re.compile(r"^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")


def _to_rgb(color: str) -> tuple[int, int, int] | None:
    """'#rgb' o '#rrggbb' -> (r, g, b); None per ogni altro formato."""
    if not isinstance(color, str) or not _HEX.match(color.strip()):
        return None
    h = color.strip()[1:]
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _luminance(rgb: tuple[int, int, int]) -> float:
    def channel(c: int) -> float:
        s = c / 255
        return s / 12.92 if s <= 0.03928 else ((s + 0.055) / 1.055) ** 2.4

    r, g, b = (channel(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(a: str, b: str) -> float:
    """Rapporto di contrasto WCAG 2.x tra due colori esadecimali."""
    ra, rb = _to_rgb(a), _to_rgb(b)
    if ra is None or rb is None:
        raise ValueError(f"colori non esadecimali: {a!r}, {b!r}")
    la, lb = sorted((_luminance(ra), _luminance(rb)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def lift_for_dark(color, background: str = DARK_BACKGROUND,
                  min_ratio: float = MIN_CONTRAST, toward: str = DARK_INK):
    """Restituisce `color` schiarito verso `toward` finché fa almeno `min_ratio`
    su `background`. Colori già sufficienti e valori non esadecimali (nomi,
    rgba(), numeri di una scala) tornano invariati."""
    rgb = _to_rgb(color)
    if rgb is None or contrast_ratio(color, background) >= min_ratio:
        return color
    target = _to_rgb(toward)
    steps = round(1 / _STEP)
    for i in range(1, steps + 1):
        t = i * _STEP
        mixed = "#" + "".join(
            f"{round(c + (d - c) * t):02x}" for c, d in zip(rgb, target, strict=True)
        )
        if contrast_ratio(mixed, background) >= min_ratio:
            return mixed
    return toward


def _lift_value(value):
    """Un colore singolo o una sequenza di colori (barre, fette di torta)."""
    if isinstance(value, str):
        return lift_for_dark(value)
    if isinstance(value, (list, tuple)) and value and all(isinstance(v, str) for v in value):
        return [lift_for_dark(v) for v in value]
    return value


def adapt_figure_for_dark(fig):
    """Porta sopra 3:1 i colori di serie di una figura Plotly per il tema scuro.

    Tocca: colorway del layout; marker.color, marker.colors (torte),
    marker.colorscale e line.color delle tracce; linea delle forme (soglie
    tracciate con add_hline). Restituisce la figura modificata."""
    if fig.layout.colorway:
        fig.layout.colorway = [lift_for_dark(c) for c in fig.layout.colorway]
    for trace in fig.data:
        marker = getattr(trace, "marker", None)
        if marker is not None:
            if getattr(marker, "color", None) is not None:
                marker.color = _lift_value(marker.color)
            if getattr(marker, "colors", None) is not None:
                marker.colors = _lift_value(marker.colors)
            scale = getattr(marker, "colorscale", None)
            # Plotly espande anche le scale con nome ('Viridis') in [[posizione, colore], …].
            if (isinstance(scale, (list, tuple)) and scale
                    and all(isinstance(stop[1], str) for stop in scale)):
                marker.colorscale = [[stop[0], lift_for_dark(stop[1])] for stop in scale]
        line = getattr(trace, "line", None)
        if line is not None and getattr(line, "color", None) is not None:
            line.color = _lift_value(line.color)
    for shape in fig.layout.shapes or ():
        if shape.line is not None and shape.line.color is not None:
            shape.line.color = lift_for_dark(shape.line.color)
    return fig
