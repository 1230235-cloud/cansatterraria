"""Widgets de indicadores digitales (altitud, temperatura, presión, batería, ST)."""

from __future__ import annotations

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor, QFont, QPainter, QPainterPath
from PyQt5.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from ..theme import Colors, MONO_FAMILY


class _AccentBar(QWidget):
    """Barra de color lateral que identifica el canal."""

    def __init__(self, color: str, parent=None) -> None:
        super().__init__(parent)
        self._color = QColor(color)
        self.setFixedWidth(4)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)

    def paintEvent(self, event) -> None:  # noqa: N802 (API Qt)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        path = QPainterPath()
        path.addRoundedRect(2, 4, 3, max(self.height() - 8, 6), 2, 2)
        painter.fillPath(path, self._color)
        painter.end()


class IndicatorCard(QFrame):
    """Tarjeta instrumental: etiqueta grande + unidad + barra de acento.

    Señales:
        ``critical(bool)``  se emite al cruzar el umbral de alerta.
    """

    critical = pyqtSignal(bool)

    def __init__(
        self,
        title: str,
        unit: str = "",
        color: str = Colors.ACCENT,
        decimals: int = 1,
        warning_low: float | None = None,
        warning_high: float | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("Card")
        self.setMinimumHeight(92)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self._title = title
        self._unit = unit
        self._decimals = decimals
        self._color = QColor(color)
        self._warn_low = warning_low
        self._warn_high = warning_high
        self._critical = False
        self._value: float | None = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(10)
        layout.addWidget(_AccentBar(color))

        body = QVBoxLayout()
        body.setSpacing(1)

        self._label = QLabel(title)
        self._label.setObjectName("IndLabel")

        value_row = QHBoxLayout()
        value_row.setSpacing(6)
        self._value_label = QLabel("--.-")
        value_label_font = QFont(MONO_FAMILY.split(",")[0].strip())
        value_label_font.setPointSize(17)
        value_label_font.setBold(True)
        self._value_label.setFont(value_label_font)
        self._value_label.setStyleSheet(f"color: {color};")

        self._unit_label = QLabel(unit)
        self._unit_label.setObjectName("IndUnit")
        self._unit_label.setAlignment(Qt.AlignLeft | Qt.AlignBottom)

        value_row.addWidget(self._value_label, 0, Qt.AlignBottom)
        value_row.addWidget(self._unit_label, 0, Qt.AlignBottom)
        value_row.addStretch(1)

        self._status = QLabel("sin datos")
        self._status.setObjectName("IndUnit")
        self._status.setAlignment(Qt.AlignRight | Qt.AlignTop)

        body.addWidget(self._label)
        body.addLayout(value_row)
        body.addWidget(self._status)
        body.addStretch(1)

        layout.addLayout(body, 1)

    # ------------------------------------------------------------------ API
    def set_value(self, value) -> None:
        """Actualiza la lectura; admito ``None`` para estado 'sin datos'."""
        if value is None:
            self._value = None
            self._value_label.setText("--.-")
            self._status.setText("sin datos")
            self._value_label.setStyleSheet(f"color: {Colors.TEXT_FAINT};")
            self._set_critical(False, announce=False)
            return

        self._value = float(value)
        text = f"{self._value:.{self._decimals}f}"
        self._value_label.setText(text)

        critical = self._evaluate(self._value)
        self._status.setText("ALERTA" if critical else "nominal")
        self._status.setStyleSheet(
            f"color: {Colors.ERROR if critical else Colors.TEXT_FAINT};"
        )
        self._value_label.setStyleSheet(
            f"color: {Colors.ERROR if critical else self._color.name()};"
        )
        self._set_critical(critical)

    def set_text(self, text: str, color: str | None = None) -> None:
        """Muestra un texto libre (p. ej. el estado de la misión)."""
        self._value = None
        self._value_label.setText(text)
        self._value_label.setStyleSheet(
            f"color: {color or self._color.name()}; font-size: 15px;"
        )
        self._status.setText("")
        self._set_critical(False)

    def clear(self) -> None:
        self.set_value(None)

    # -------------------------------------------------------------- internos
    def _evaluate(self, value: float) -> bool:
        if self._warn_low is not None and value < self._warn_low:
            return True
        if self._warn_high is not None and value > self._warn_high:
            return True
        return False

    def _set_critical(self, critical: bool, announce: bool = True) -> None:
        if critical == self._critical:
            return
        self._critical = critical
        if announce:
            self.critical.emit(critical)


class MissionClockCard(QFrame):
    """Tiempo de misión (ST) con barra de progreso del evento y Segmentation."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("Card")
        self.setMinimumHeight(92)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(10)
        layout.addWidget(_AccentBar(Colors.WARN))

        body = QVBoxLayout()
        body.setSpacing(1)

        title = QLabel("TIEMPO DE MISIÓN")
        title.setObjectName("IndLabel")

        self._value = QLabel("00:00:00")
        clock_font = QFont(MONO_FAMILY.split(",")[0].strip())
        clock_font.setPointSize(20)
        clock_font.setBold(True)
        self._value.setFont(clock_font)
        self._value.setStyleSheet(f"color: {Colors.WARN};")

        self._event = QLabel("en espera")
        self._event.setObjectName("IndUnit")

        body.addWidget(title)
        body.addWidget(self._value)
        body.addWidget(self._event)
        body.addStretch(1)

        layout.addLayout(body, 1)

    def set_time(self, seconds: float, event: str = "") -> None:
        self._value.setText(_format_duration(seconds))
        if event:
            self._event.setText(event)

    def clear(self) -> None:
        self._value.setText("00:00:00")
        self._event.setText("en espera")


def _format_duration(seconds: float) -> str:
    """Segundos a ``HH:MM:SS`` con signo opcional."""
    total = int(seconds)
    sign = "-" if total < 0 else ""
    total = abs(total)
    return f"{sign}{total // 3600:02d}:{(total % 3600) // 60:02d}:{total % 60:02d}"