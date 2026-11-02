"""Panel de control (comandos y grabación CSV) y consola de mensajes."""

from __future__ import annotations

import time

from PyQt5.QtGui import QColor, QTextCharFormat, QTextCursor
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .. import protocol
from ..theme import Colors
from .connection import Panel

#: Color de consola por nivel de mensaje.
LEVEL_COLORS = {
    "info": Colors.TEXT_DIM,
    "tx": Colors.ACCENT,
    "rx": Colors.OK,
    "ok": Colors.OK,
    "warn": Colors.WARN,
    "error": Colors.ERROR,
}

DEFAULT_RECORD_DIR = "grabaciones"


def _format(color: str) -> QTextCharFormat:
    char_format = QTextCharFormat()
    char_format.setForeground(QColor(color))
    return char_format


def _restyle(widget: QWidget) -> None:
    """Fuerza la re-evaluación del estilo tras cambiar ``objectName``."""
    widget.style().unpolish(widget)
    widget.style().polish(widget)


class LogConsole(QFrame):
    """Consola de texto con marca de tiempo y color por nivel."""

    def __init__(self, parent: QWidget | None = None, max_lines: int = 800) -> None:
        super().__init__(parent)
        self.setObjectName("Panel")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(1, 1, 1, 10)
        layout.setSpacing(0)

        title = QLabel("CONSOLA DE COMUNICACIONES")
        title.setObjectName("PanelTitle")
        layout.addWidget(title)

        self.view = QPlainTextEdit(self)
        self.view.setObjectName("Console")
        self.view.setReadOnly(True)
        self.view.setMaximumBlockCount(max_lines)
        self.view.setLineWrapMode(QPlainTextEdit.NoWrap)
        layout.addWidget(self.view, 1)

        self._formats = {level: _format(color) for level, color in LEVEL_COLORS.items()}
        self._formats["default"] = _format(Colors.TEXT)

    def append(self, message: str, level: str = "info", stamp: bool = True) -> None:
        """Añade una línea a la consola (scroll automático)."""
        prefix = f"[{time.strftime('%H:%M:%S')}] " if stamp else ""
        cursor = self.view.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertText(f"{prefix}{message}\n",
                          self._formats.get(level, self._formats["default"]))
        self.view.setTextCursor(cursor)
        self.view.ensureCursorVisible()

    def clear(self) -> None:
        self.view.clear()


class ControlPanel(Panel):
    """Calibración, comandos de misión, grabación CSV y entrada libre.

    Señales:
        ``command_sent(str)``       comando a transmitir por el puerto
        ``record_toggle(str)``      ruta destino (iniciar) o ``""`` (detener)
        ``echo_toggled(bool)``      impresión de tramas brutas
        ``clear_requested()``       limpiar la consola
    """

    command_sent = pyqtSignal(str)
    record_toggle = pyqtSignal(str)
    echo_toggled = pyqtSignal(bool)
    clear_requested = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("CONTROL DE MISIÓN", parent)
        self._recording = False

        grid = QGridLayout()
        grid.setSpacing(8)

        self.calib_btn = _button("CALIBRAR SENSOR", "Accent",
                                 "Envía la orden de calibración de sensores "
                                 "(offset y ganancia del IMU / barómetro)")
        self.calib_btn.clicked.connect(lambda: self._send(protocol.CMD_CALIBRATE))
        grid.addWidget(self.calib_btn, 0, 0, 1, 2)

        self.inject_btn = _button("INYECCIÓN", "Warn",
                                  "Comando de inyección (p. ej. gases de recuperación)")
        self.inject_btn.clicked.connect(lambda: self._send(protocol.CMD_INJECTION))
        grid.addWidget(self.inject_btn, 1, 0)

        self.deploy_btn = _button("DESPLIEGUE", "Primary",
                                  "Ordena el despliegue del conjunto de parenthood")
        self.deploy_btn.clicked.connect(lambda: self._send(protocol.CMD_DEPLOY_PARENT))
        grid.addWidget(self.deploy_btn, 1, 1)

        self.chute_btn = _button("CORTAR PARACAÍDAS", "Danger",
                                 "Corte del cable de apertura del paracaídas")
        self.chute_btn.clicked.connect(lambda: self._send(protocol.CMD_CUT_PARACHUTE))
        grid.addWidget(self.chute_btn, 2, 0, 1, 2)

        self.record_btn = _button("INICIAR GRABACIÓN CSV", "Primary",
                                  "Registra toda la telemetría recibida en un fichero CSV")
        self.record_btn.clicked.connect(self._toggle_recording)
        grid.addWidget(self.record_btn, 3, 0, 1, 2)
        self.body.addLayout(grid)

        row = QHBoxLayout()
        row.setSpacing(8)
        self.command_edit = QLineEdit(self)
        self.command_edit.setPlaceholderText("Comando libre (Enter para enviar)")
        self.command_edit.returnPressed.connect(self._send_typed)
        row.addWidget(self.command_edit, 1)
        self.send_btn = _button("ENVIAR", "Primary", "Envía el texto del campo de comando")
        self.send_btn.setFixedWidth(92)
        self.send_btn.clicked.connect(self._send_typed)
        row.addWidget(self.send_btn)
        self.body.addLayout(row)

        row2 = QHBoxLayout()
        row2.setSpacing(8)
        self.path_label = QLabel("CSV: —", self)
        self.path_label.setObjectName("Hint")
        self.path_label.setToolTip("Sin grabación activa")
        row2.addWidget(self.path_label, 1)
        self.browse_btn = _button("RUTA…", "", "Elige el fichero CSV de destino")
        self.browse_btn.setFixedWidth(78)
        self.browse_btn.clicked.connect(self._browse)
        row2.addWidget(self.browse_btn)
        self.body.addLayout(row2)

        row3 = QHBoxLayout()
        row3.setSpacing(8)
        self.echo_check = QCheckBox("Trama cruda", self)
        self.echo_check.setToolTip("Muestra cada telemetría recibida en la consola")
        self.echo_check.setChecked(True)
        self.echo_check.toggled.connect(self.echo_toggled)
        row3.addWidget(self.echo_check)
        self.clear_btn = _button("LIMPIAR CONSOLA", "", "Borra el historial de la consola")
        self.clear_btn.clicked.connect(self.clear_requested)
        row3.addWidget(self.clear_btn, 1)
        self.body.addLayout(row3)

        self._pending_path = ""

    # ------------------------------------------------------------------ API
    @property
    def is_recording(self) -> bool:
        return self._recording

    def toggle_recording(self) -> None:
        """Alterna la grabación (usado también por atajo de teclado)."""
        self._toggle_recording()

    def set_link_active(self, active: bool) -> None:
        """Habilita los comandos solo con el enlace abierto."""
        for button in (self.calib_btn, self.inject_btn, self.deploy_btn,
                       self.chute_btn, self.send_btn):
            button.setEnabled(active)
        self.command_edit.setEnabled(active)
        self.browse_btn.setEnabled(active or self._recording)

    def set_recording(self, recording: bool, path: str = "") -> None:
        """Refleja el estado de la grabación en el botón y la etiqueta."""
        self._recording = recording
        self.record_btn.setText("DETENER GRABACIÓN" if recording else "INICIAR GRABACIÓN CSV")
        self.record_btn.setObjectName("Danger" if recording else "Primary")
        _restyle(self.record_btn)
        self.path_label.setText(f"CSV: {path}" if path else "CSV: —")
        self.path_label.setToolTip(path or "Sin grabación activa")
        self.browse_btn.setEnabled(recording)

    # -------------------------------------------------------------- internos
    def _send(self, command: str) -> None:
        self.command_edit.setText(command)
        self.command_sent.emit(command)

    def _send_typed(self) -> None:
        command = self.command_edit.text().strip()
        if command:
            self.command_sent.emit(command)

    def _toggle_recording(self) -> None:
        if self._recording:
            self.record_toggle.emit("")
            return
        path = self._choose_path()
        if path:
            self.record_toggle.emit(path)

    def _choose_path(self) -> str:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Guardar telemetría en CSV",
            f"{DEFAULT_RECORD_DIR}/cansat.csv",
            "Archivos CSV (*.csv);;Todos los archivos (*)",
        )
        if path:
            self._pending_path = path
        return path

    def _browse(self) -> None:
        self._choose_path()


def _button(text: str, object_name: str, tooltip: str) -> QPushButton:
    button = QPushButton(text)
    if object_name:
        button.setObjectName(object_name)
    button.setToolTip(tooltip)
    button.setCursor(Qt.PointingHandCursor)
    return button