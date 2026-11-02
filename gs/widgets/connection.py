"""Panel de conexión: selector de puerto, baudrate y botón conectar."""

from __future__ import annotations

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
)

from .. import protocol
from ..theme import Colors


class Panel(QFrame):
    """Contenedor base con cabecera de sección (se reutiliza en todo el panel)."""

    def __init__(self, title: str, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("Panel")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(1, 1, 1, 10)
        outer.setSpacing(0)

        header = QLabel(title)
        header.setObjectName("PanelTitle")
        outer.addWidget(header)

        self.body = QVBoxLayout()
        self.body.setContentsMargins(12, 6, 12, 4)
        self.body.setSpacing(8)
        outer.addLayout(self.body)


class ConnectionPanel(Panel):
    """Puerto / baudrate / conectar + indicador de estado del enlace.

    Señales:
        ``connect_requested(str, int)``  puerto y baudrate elegidos
        ``disconnect_requested()``       petición de cierre de enlace
        ``refresh_requested()``          re-escaneo de puertos
    """

    connect_requested = pyqtSignal(str, int)
    disconnect_requested = pyqtSignal()
    refresh_requested = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__("ENLACE DE TELEMETRÍA", parent)

        grid = QGridLayout()
        grid.setSpacing(8)

        grid.addWidget(self._caption("PUERTO"), 0, 0)
        self.port_combo = QComboBox()
        self.port_combo.setEditable(False)
        self.port_combo.setMinimumWidth(150)
        self.port_combo.addItem("— SIMULACIÓN —", "@sim@")
        self.port_combo.addItem("Buscando puertos…", "")
        self.port_combo.setCurrentIndex(0)
        grid.addWidget(self.port_combo, 0, 1)

        refresh = QPushButton("⟳")
        refresh.setFixedWidth(32)
        refresh.setToolTip("Volver a escanear los puertos COM/TTY disponibles")
        refresh.clicked.connect(self.refresh_requested)
        grid.addWidget(refresh, 0, 2)

        grid.addWidget(self._caption("BAUDRATE"), 1, 0)
        self.baud_combo = QComboBox()
        for rate in protocol.BAUDRATES:
            self.baud_combo.addItem(f"{rate:,}".replace(",", " "), rate)
        self.baud_combo.setCurrentText("115 200")
        grid.addWidget(self.baud_combo, 1, 1, 1, 2)

        self.body.addLayout(grid)

        self.connect_btn = QPushButton("CONECTAR")
        self.connect_btn.setObjectName("Primary")
        self.connect_btn.setCursor(Qt.PointingHandCursor)
        self.connect_btn.clicked.connect(self._toggle)
        self.body.addWidget(self.connect_btn)

        self.status_label = QLabel("ENLACE CERRADO")
        self.status_label.setObjectName("Hint")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.body.addWidget(self.status_label)

    # ------------------------------------------------------------------ API
    def set_ports(self, ports) -> None:
        """Rellena el desplegable con ``[(puerto, descripción, hwid)]``."""
        current = self.port_combo.currentData()
        self.port_combo.blockSignals(True)
        self.port_combo.clear()
        self.port_combo.addItem("— SIMULACIÓN —", "@sim@")
        for device, description, _hwid in ports:
            self.port_combo.addItem(f"{device} — {description}", device)
        if not ports:
            self.port_combo.addItem("(sin puertos detectados)", "")
            self.port_combo.setEnabled(True)
        self.port_combo.blockSignals(False)

        index = self.port_combo.findData(current)
        if index >= 0:
            self.port_combo.setCurrentIndex(index)

    def set_connected(self, connected: bool, detail: str = "") -> None:
        """Refleja el estado real del enlace."""
        self.port_combo.setEnabled(not connected)
        self.baud_combo.setEnabled(not connected)
        self.connect_btn.setEnabled(True)
        self.connect_btn.setText("DESCONECTAR" if connected else "CONECTAR")
        self.connect_btn.setObjectName("Danger" if connected else "Primary")
        _restyle(self.connect_btn)
        if connected:
            self.status_label.setText(f"ENLACE ACTIVO · {detail}")
            self.status_label.setStyleSheet(f"color: {Colors.OK};")
        else:
            self.status_label.setText(f"ENLACE CERRADO{f' · {detail}' if detail else ''}")
            self.status_label.setStyleSheet(f"color: {Colors.TEXT_FAINT};")

    def set_busy(self, busy: bool) -> None:
        self.connect_btn.setEnabled(not busy)

    @property
    def simulation_selected(self) -> bool:
        return self.port_combo.currentData() == "@sim@"

    @property
    def selected_port(self) -> str:
        return self.port_combo.currentData() or ""

    @property
    def selected_baudrate(self) -> int:
        return int(self.baud_combo.currentData() or 115200)

    # -------------------------------------------------------------- internos
    def _toggle(self) -> None:
        if self.connect_btn.text().startswith("CONECTAR"):
            self.connect_requested.emit(self.selected_port, self.selected_baudrate)
        else:
            self.disconnect_requested.emit()

    @staticmethod
    def _caption(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("Hint")
        return label


def _restyle(widget: QPushButton) -> None:
    """Fuerza la re-evaluación del estilo tras cambiar ``objectName``."""
    widget.style().unpolish(widget)
    widget.style().polish(widget)
