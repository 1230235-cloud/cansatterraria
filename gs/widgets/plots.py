"""Gráficas en tiempo real con pyqtgraph.

Dos instrumentos:
  * Altitud (m) frente a tiempo de misión.
  * Temperatura (°C) y Presión (hPa) frente a tiempo de misión, con
    eje derecho secundario para la presión.

Los buffers son circulares (``collections.deque``) con un límite de
muestras, y el redibujado se limita a ``SAMPLE_DT`` segundos para no
saturar la CPU con tasas de envío altas.
"""

from __future__ import annotations

import time
from collections import deque

import pyqtgraph as pg
from PyQt5.QtWidgets import QSizePolicy, QVBoxLayout

from ..theme import Colors
from .connection import Panel

#: Máximo de muestras retenidas por canal.
MAX_SAMPLES = 1500
#: Intervalo mínimo (s) entre muestras dibujadas.
SAMPLE_DT = 0.25


class TelemetryPlots(Panel):
    """Conjunto de gráficas en tiempo real."""

    def __init__(self, parent=None) -> None:
        super().__init__("TELEMETRÍA EN TIEMPO REAL", parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self._t = deque(maxlen=MAX_SAMPLES)
        self._alt = deque(maxlen=MAX_SAMPLES)
        self._temp = deque(maxlen=MAX_SAMPLES)
        self._press = deque(maxlen=MAX_SAMPLES)
        self._last_plot = 0.0
        self._dirty = False
        self._window: float | None = None
        self._frozen = False

        layout = QVBoxLayout()
        layout.setSpacing(8)

        # -------------------------------------------------- altitud vs tiempo
        self.alt_plot = self._make_plot("Altitud vs tiempo", "m")
        self.alt_curve = self.alt_plot.plot(
            pen=pg.mkPen(Colors.ALT, width=2),
            fillLevel=0,
            brush=pg.mkBrush(0, 212, 255, 26),
        )
        self.alt_plot.setYRange(0, 500, padding=0.08)
        self.alt_plot.setMouseEnabled(x=True, y=False)
        self.alt_markers = pg.ScatterPlotItem(
            size=5, pen=pg.mkPen(Colors.ALT), brush=pg.mkBrush(Colors.ALT)
        )
        self.alt_plot.addItem(self.alt_markers)
        layout.addWidget(self.alt_plot, 3)

        # ------------------------------------- temperatura + presión vs tiempo
        self.env_plot = self._make_plot("Temperatura y presión vs tiempo", "°C")
        self.temp_curve = self.env_plot.plot(pen=pg.mkPen(Colors.TEMP, width=2))
        self._setup_right_axis()

        layout.addWidget(self.env_plot, 2)
        self.body.addLayout(layout, 1)

    # ------------------------------------------------------------- públicas
    def add_sample(self, telemetry) -> None:
        """Añade un paquete a los buffers (no dibuja necesariamente)."""
        self._t.append(telemetry.t)
        self._alt.append(telemetry.altitude)
        self._temp.append(telemetry.temperature)
        self._press.append(telemetry.pressure)

        now = time.monotonic()
        if now - self._last_plot >= SAMPLE_DT or len(self._t) < 2:
            self._last_plot = now
            self._redraw()
            self._dirty = False
        else:
            self._dirty = True

    def redraw(self) -> None:
        """Fuerza el redibujado (usado por el temporizador de la ventana)."""
        if self._dirty and self._t:
            self._dirty = False
            self._redraw()

    def clear(self) -> None:
        """Borra las trazas y reinicia las escalas."""
        self._t.clear()
        self._alt.clear()
        self._temp.clear()
        self._press.clear()
        self._dirty = False
        for curve in (self.alt_curve, self.temp_curve, self._press_curve):
            curve.setData([], [])
        self.alt_markers.setData([], [])
        self.alt_plot.setYRange(0, 500, padding=0.08)
        self._pressure_vb.setYRange(900, 1050, padding=0.1)

    def set_window(self, seconds: float | None) -> None:
        """Fija la ventana temporal visible (en segundos de misión)."""
        self._window = max(5.0, float(seconds)) if seconds else None
        if self._t:
            self._apply_x_range()

    def freeze(self, frozen: bool) -> None:
        """Detiene el desplazamiento temporal sin dejar de dibujar."""
        self._frozen = bool(frozen)

    # ------------------------------------------------------------ internas
    @staticmethod
    def _make_plot(title: str, unit: str) -> pg.PlotWidget:
        plot = pg.PlotWidget(background=Colors.BG_WIDGET)
        plot.setTitle(title, color=Colors.TEXT, size="10pt")
        plot.showGrid(x=True, y=True, alpha=0.18)
        plot.getAxis("left").setLabel(unit, color=Colors.TEXT_FAINT, size="9pt")
        plot.getAxis("bottom").setLabel(
            "tiempo de misión (s)", color=Colors.TEXT_FAINT, size="9pt"
        )
        plot.getPlotItem().setContentsMargins(4, 6, 4, 4)
        plot.setClipToView(True)
        plot.hideButtons()
        for name in ("left", "bottom"):
            axis = plot.getAxis(name)
            axis.setPen(pg.mkPen(Colors.BORDER))
            axis.setTextPen(pg.mkPen(Colors.TEXT_FAINT))
        plot.setBackground(Colors.BG_WIDGET)
        return plot

    def _setup_right_axis(self) -> None:
        """Crea un segundo eje vertical (presión) enlazado al principal."""
        self._pressure_vb = pg.ViewBox()
        self.env_plot.plotItem.showAxis("right")
        self.env_plot.plotItem.scene().addItem(self._pressure_vb)
        right_axis = self.env_plot.getAxis("right")
        right_axis.linkToView(self._pressure_vb)
        right_axis.setLabel("hPa", color=Colors.TEXT_FAINT, size="9pt")
        right_axis.setPen(pg.mkPen(Colors.BORDER))
        right_axis.setTextPen(pg.mkPen(Colors.TEXT_FAINT))
        right_axis.setWidth(58)
        self._pressure_vb.setXLink(self.env_plot.plotItem.vb)

        self._press_curve = self.env_plot.plot(
            pen=pg.mkPen(Colors.PRESS, width=2), name="presión"
        )
        self.env_plot.plotItem.vb.addItem(self._press_curve)
        self._pressure_vb.setYRange(900, 1050, padding=0.1)
        self._sync_pressure_vb()
        self.env_plot.installEventFilter(self)

    def _sync_pressure_vb(self) -> None:
        """Mantiene el eje derecho alineado con el ViewBox principal."""
        vb = self.env_plot.plotItem.vb
        self._pressure_vb.setGeometry(vb.sceneBoundingRect())
        self._pressure_vb.linkedViewChanged(vb, self._pressure_vb.XAxis)

    def eventFilter(self, obj, event):  # noqa: N802 (API Qt)
        if obj is self.env_plot and event.type() == event.Resize:
            self._sync_pressure_vb()
        return super().eventFilter(obj, event)

    def _redraw(self) -> None:
        xs = list(self._t)
        self.alt_curve.setData(xs, list(self._alt))
        self.temp_curve.setData(xs, list(self._temp))
        self._press_curve.setData(xs, list(self._press))

        last_x, last_alt = xs[-1], self._alt[-1]
        self.alt_markers.setData([last_x], [last_alt])

        if not self._frozen:
            self._apply_x_range(xs)

    def _apply_x_range(self, xs=None) -> None:
        if xs is None:
            xs = list(self._t)
        if not xs:
            return
        if self._window:
            self.alt_plot.setXRange(xs[-1] - self._window, xs[-1], padding=0)
            self.env_plot.setXRange(xs[-1] - self._window, xs[-1], padding=0)
        else:
            span = max(xs[-1] - xs[0], 10.0)
            self.alt_plot.setXRange(xs[0], xs[-1] + span * 0.02, padding=0)
            self.env_plot.setXRange(xs[0], xs[-1] + span * 0.02, padding=0)

    def follow_y(self) -> None:
        """Ajusta automáticamente las escalas verticales."""
        if self._alt:
            self.alt_plot.setYRange(min(self._alt), max(max(self._alt), min(self._alt) + 50),
                                    padding=0.12)
        if self._press:
            lo, hi = min(self._press), max(self._press)
            self._pressure_vb.setYRange(lo - 5, hi + 5, padding=0.1)