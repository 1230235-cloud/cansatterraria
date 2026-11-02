"""Ventana principal de la Estación Terrestre: dashboard y cableado de señales."""

from __future__ import annotations

import os

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QKeySequence
from PyQt5.QtWidgets import (
    QAction,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QSplitter,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from .serial_worker import SIM_TAG, PortScanThread, SerialWorker
from .theme import Colors
from .widgets import (
    AttitudeIndicator,
    ConnectionPanel,
    ControlPanel,
    IndicatorCard,
    LogConsole,
    MissionClockCard,
    TelemetryPlots,
)

APP_TITLE = "CanSat · Estación Terrestre (Ground Station)"


class MainWindow(QMainWindow):
    """Dashboard de telemetría: indicadores, gráficas, actitud y control."""

    def __init__(
        self,
        initial_port: str | None = None,
        initial_baudrate: int | None = None,
        force_simulation: bool = False,
    ) -> None:
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.resize(1560, 940)

        self.worker = SerialWorker(self)
        self.port_scanner: PortScanThread | None = None
        self._linked = False
        self._echo = True
        self._max_altitude = 0.0

        # Opciones de arranque, aplicadas cuando termine el escaneo de puertos.
        self._initial_port = initial_port
        self._initial_baudrate = initial_baudrate or 115200
        self._force_simulation = bool(force_simulation)

        self._build_ui()
        self._connect_signals()
        self._build_status_bar()
        self._build_shortcuts()

        self.console.append("Estación terrestre lista.", "ok", stamp=False)
        self.console.append(
            f"Actitud: {self.attitude.backend_name}"
            "   ·   trama: T,t,alt,temp,pres,vol,pitch,roll,yaw,state,sat,chute,packet",
            "info", stamp=False)
        self.scan_ports()

        # Redibujado periódico: mantiene las curvas vivas aunque el hilo
        # tarde entre muestras.
        self._ui_timer = QTimer(self)
        self._ui_timer.timeout.connect(self._on_ui_tick)
        self._ui_timer.start(120)

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        central = QWidget(self)
        root = QHBoxLayout(central)
        root.setContentsMargins(10, 10, 10, 6)
        root.setSpacing(10)

        root.addWidget(self._build_left_column(), 0)
        root.addWidget(self._build_right_area(), 1)

        self.setCentralWidget(central)

    def _build_left_column(self) -> QWidget:
        column = QWidget(self)
        layout = QVBoxLayout(column)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self.connection = ConnectionPanel(self)
        layout.addWidget(self.connection)

        # -------------------------------------------------- indicadores
        indicators = QWidget(self)
        grid = QGridLayout(indicators)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(8)

        self.ind_alt = IndicatorCard("ALTITUD", "m", Colors.ALT, decimals=1)
        self.ind_temp = IndicatorCard("TEMPERATURA", "°C", Colors.TEMP, decimals=1)
        self.ind_press = IndicatorCard("PRESIÓN", "hPa", Colors.PRESS, decimals=2)
        self.ind_volt = IndicatorCard("BATERÍA", "V", Colors.VOLT, decimals=2,
                                      warning_low=6.8)
        self.ind_st = MissionClockCard(self)
        self.ind_state = IndicatorCard("ESTADO DE MISIÓN", "", Colors.INFO)

        grid.addWidget(self.ind_alt, 0, 0)
        grid.addWidget(self.ind_temp, 0, 1)
        grid.addWidget(self.ind_press, 1, 0)
        grid.addWidget(self.ind_volt, 1, 1)
        grid.addWidget(self.ind_st, 2, 0, 1, 2)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        layout.addWidget(indicators)

        self.controls = ControlPanel(self)
        layout.addWidget(self.controls)
        layout.addStretch(1)
        column.setFixedWidth(392)
        return column

    def _build_right_area(self) -> QWidget:
        splitter = QSplitter(Qt.Vertical, self)
        splitter.setChildrenCollapsible(False)

        self.plots = TelemetryPlots(self)

        bottom = QSplitter(Qt.Horizontal, splitter)
        bottom.setChildrenCollapsible(False)
        bottom.addWidget(self._build_attitude_block())
        bottom.addWidget(self._build_console_block())
        bottom.setSizes([620, 700])

        splitter.addWidget(self.plots)
        splitter.addWidget(bottom)
        splitter.setSizes([520, 420])
        return splitter

    def _build_attitude_block(self) -> QWidget:
        holder = QWidget(self)
        layout = QVBoxLayout(holder)
        layout.setContentsMargins(0, 0, 0, 0)

        self.attitude = AttitudeIndicator(self)
        layout.addWidget(self.attitude)

        reset = QLabel("Arrastra para orbitar · rueda para zoom · botón derecho para rotar",
                       holder)
        reset.setObjectName("Hint")
        reset.setAlignment(Qt.AlignCenter)
        layout.addWidget(reset)
        return holder

    def _build_console_block(self) -> QWidget:
        holder = QWidget(self)
        layout = QVBoxLayout(holder)
        layout.setContentsMargins(0, 0, 0, 0)
        self.console = LogConsole(self)
        layout.addWidget(self.console)
        return holder

    def _build_status_bar(self) -> None:
        self.status = QStatusBar(self)
        self.setStatusBar(self.status)

        self.lbl_link = _status_label("ENLACE: —", Colors.TEXT_FAINT)
        self.lbl_packets = _status_label("PAQUETES: 0", Colors.TEXT_DIM)
        self.lbl_loss = _status_label("PERDIDOS: 0", Colors.TEXT_DIM)
        self.lbl_rate = _status_label("CADENCIA: 0.0 Hz", Colors.TEXT_DIM)
        self.lbl_record = _status_label("● SIN GRABAR", Colors.TEXT_FAINT)
        self.lbl_backend = _status_label("MOTOR: —", Colors.TEXT_FAINT)
        self.lbl_backend.setText(f"MOTOR: {self.attitude.backend_name}")

        for label in (self.lbl_link, self.lbl_packets, self.lbl_loss, self.lbl_rate):
            self.status.addWidget(label)
        self.status.addPermanentWidget(self.lbl_record)
        self.status.addPermanentWidget(self.lbl_backend)

    def _build_shortcuts(self) -> None:
        for key, slot, name in (
            ("Ctrl+O", self._open_connect, "Conectar"),
            ("Ctrl+D", self._disconnect, "Desconectar"),
            ("Ctrl+R", self.controls.toggle_recording, "Grabación"),
            ("Ctrl+L", self.controls.clear_requested.emit, "Limpiar consola"),
        ):
            action = QAction(name, self)
            action.setShortcut(QKeySequence(key))
            action.triggered.connect(slot)
            self.addAction(action)

    # ------------------------------------------------------------- señales
    def _connect_signals(self) -> None:
        self.connection.connect_requested.connect(self._open_connect)
        self.connection.disconnect_requested.connect(self._disconnect)
        self.connection.refresh_requested.connect(self.scan_ports)

        self.controls.command_sent.connect(self._send_command)
        self.controls.record_toggle.connect(self._toggle_recording)
        self.controls.echo_toggled.connect(self._set_echo)
        self.controls.clear_requested.connect(self.console.clear)

        self.worker.telemetry.connect(self._on_telemetry)
        self.worker.log.connect(self._on_worker_log)
        self.worker.linked.connect(self._on_linked)
        self.worker.stats.connect(self._on_stats)

    # ------------------------------------------------------------- acciones
    def _open_connect(self) -> None:
        if self.worker.isRunning():
            return
        port = self.connection.selected_port
        if not port:
            self.console.append("Selecciona un puerto COM/TTY o el simulador.", "warn")
            return

        self.connection.set_busy(True)
        self.worker.configure(SIM_TAG if self.connection.simulation_selected else port,
                              self.connection.selected_baudrate)
        self.worker.start()
        self.controls.set_link_active(True)

    def _disconnect(self) -> None:
        if not self.worker.isRunning():
            return
        self.console.append("Cerrando enlace…", "warn")
        self.connection.set_busy(False)
        self.worker.shutdown()

    def _send_command(self, command: str) -> None:
        self.worker.send_command(command)

    def _toggle_recording(self, path: str) -> None:
        if path:
            directory = os.path.dirname(os.path.abspath(path))
            os.makedirs(directory, exist_ok=True)
            if self.worker.start_recording(path):
                self.controls.set_recording(True, path)
                self.lbl_record.setText("● GRABANDO")
                self.lbl_record.setStyleSheet(f"color: {Colors.ERROR}; font-weight: bold;")
                self.console.append(f"Grabación iniciada → {path}", "ok")
            else:
                self.console.append(f"No se pudo abrir {path} para escritura", "error")
                self.controls.set_recording(False)
        else:
            rows = self.worker.stop_recording()
            self.controls.set_recording(False)
            self.lbl_record.setText("● SIN GRABAR")
            self.lbl_record.setStyleSheet(f"color: {Colors.TEXT_FAINT};")
            self.console.append(f"Grabación detenida ({rows} muestras)", "ok")

    def _set_echo(self, enabled: bool) -> None:
        self._echo = bool(enabled)

    # ---------------------------------------------------------- recepción
    def scan_ports(self) -> None:
        """Re-escanea los puertos en segundo plano."""
        if self.port_scanner is not None and self.port_scanner.isRunning():
            return
        self.port_scanner = PortScanThread(self)
        self.port_scanner.found.connect(self._on_ports_found)
        self.port_scanner.start()

    def _on_ports_found(self, ports) -> None:
        self.connection.set_ports(ports)
        self._apply_startup_options()
        if ports:
            self.console.append(
                f"Puertos detectados: {', '.join(p[0] for p in ports)}", "info")
        else:
            self.console.append(
                "Sin puertos series: usa el modo simulación o conecta el receptor USB.", "warn")

    def _apply_startup_options(self) -> None:
        """Respeta ``--port`` / ``--baud`` / ``--sim`` de la línea de comandos."""
        index = self.connection.baud_combo.findData(int(self._initial_baudrate))
        if index >= 0:
            self.connection.baud_combo.setCurrentIndex(index)

        port_index = self.connection.port_combo.findData(self._initial_port or "")
        if port_index >= 0 and self._initial_port:
            self.connection.port_combo.setCurrentIndex(port_index)
        elif self._force_simulation:
            self.connection.port_combo.setCurrentIndex(0)   # "— SIMULACIÓN —"

    def _on_telemetry(self, telemetry) -> None:
        """Actualiza todos los instrumentos con un paquete (slot en hilo GUI)."""
        self.ind_alt.set_value(telemetry.altitude)
        self.ind_temp.set_value(telemetry.temperature)
        self.ind_press.set_value(telemetry.pressure)
        self.ind_volt.set_value(telemetry.voltage)
        self.ind_st.set_time(telemetry.t, telemetry.state_name)
        self.ind_state.set_text(telemetry.state_name, Colors.INFO)
        self.attitude.set_attitude(telemetry.pitch, telemetry.roll, telemetry.yaw)
        self.plots.add_sample(telemetry)

        self._max_altitude = max(self._max_altitude, telemetry.altitude)
        if self._echo:
            self.console.append(
                f"RX T {telemetry.t:8.2f}s | alt {telemetry.altitude:7.1f} m | "
                f"{telemetry.temperature:5.1f} °C | {telemetry.pressure:7.2f} hPa | "
                f"{telemetry.voltage:4.2f} V | P{telemetry.pitch:+6.1f} "
                f"R{telemetry.roll:+6.1f} Y{telemetry.yaw:+6.1f} | pkt {telemetry.packet}",
                "rx")

    def _on_worker_log(self, message: str, level: str) -> None:
        self.console.append(message, level)

    def _on_linked(self, linked: bool, detail: str) -> None:
        self._linked = linked
        self.connection.set_connected(linked, detail)
        self.controls.set_link_active(linked)
        if not linked:
            self.lbl_link.setText("ENLACE: CERRADO")
            self.lbl_link.setStyleSheet(f"color: {Colors.TEXT_FAINT};")
            if self.controls.is_recording:
                self.controls.set_recording(False)
                self.lbl_record.setText("● SIN GRABAR")
                self.lbl_record.setStyleSheet(f"color: {Colors.TEXT_FAINT};")
        else:
            color = Colors.OK if detail.startswith("SIMULADOR") else Colors.ACCENT
            self.lbl_link.setText(f"ENLACE: {detail}")
            self.lbl_link.setStyleSheet(f"color: {color}; font-weight: bold;")

    def _on_stats(self, packets: int, lost: float, rate: float) -> None:
        self.lbl_packets.setText(f"PAQUETES: {packets}")
        self.lbl_loss.setText(f"PERDIDOS: {int(lost)}")
        color = Colors.ERROR if lost > 0 else Colors.TEXT_DIM
        self.lbl_loss.setStyleSheet(f"color: {color};")
        self.lbl_rate.setText(f"CADENCIA: {rate:.1f} Hz")

    def _on_ui_tick(self) -> None:
        """Tarea periódica de la interfaz (no bloquea el hilo de datos)."""
        self.plots.redraw()

    # -------------------------------------------------------------- cierre
    def closeEvent(self, event) -> None:  # noqa: N802 (API Qt)
        self._ui_timer.stop()
        if self.controls.is_recording:
            rows = self.worker.stop_recording()
            self.console.append(f"Grabación cerrada al salir ({rows} muestras)", "warn")
        self.worker.shutdown()
        if self.port_scanner is not None and self.port_scanner.isRunning():
            self.port_scanner.wait(1000)
        super().closeEvent(event)


def _status_label(text: str, color: str) -> QLabel:
    label = QLabel(text)
    label.setStyleSheet(f"color: {color}; font-family: Consolas, monospace; font-size: 11px;")
    return label