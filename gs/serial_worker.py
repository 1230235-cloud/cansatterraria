"""Puente de recepción de telemetría.

* :class:`SerialWorker` (QThread): abre el puerto COM/TTY, lee tramas y
  publica :class:`~gs.protocol.Telemetry` mediante señales Qt, de forma
  que la interfaz nunca se bloquea.
* :class:`PortScanThread` (QThread): enumera los puertos series
  disponibles (Windows COMx / Linux ttyUSBx, ttyACMx) sin congelar la UI.
* :class:`FlightSimulator`: genera un perfil de vuelo sintético
  (ascenso → apogeo → despliegue → descenso con paracaídas) para probar
  la estación terrestre sin|Arduino conectado.
"""

from __future__ import annotations

import math
import random
import threading
import time

from PyQt5.QtCore import QThread, pyqtSignal

from . import protocol
from .protocol import format_csv_row
from .recording import CsvRecorder

try:  # pyserial es opcional: en modo simulación no hace falta
    import serial  # type: ignore
    import serial.tools.list_ports  # type: ignore

    SERIAL_AVAILABLE = True
except Exception:  # pragma: no cover - depende del entorno
    serial = None  # type: ignore
    SERIAL_AVAILABLE = False


SIM_TAG = "__SIM__"


# --------------------------------------------------------------------- puertos
def list_serial_ports() -> list:
    """Devuelve ``[(puerto, descripcion, hwid)]`` o lista vacía."""
    if not SERIAL_AVAILABLE:
        return []
    try:
        ports = serial.tools.list_ports.comports()
    except Exception:
        return []
    return [(p.device, p.description or p.device, p.hwid or "") for p in ports]


def _encode(telemetry) -> bytes:
    """Serializa un :class:`Telemetry` a la trama de cable."""
    return (protocol.TELEMETRY_PREFIX + "," + format_csv_row(telemetry)).encode("ascii", "ignore")


class PortScanThread(QThread):
    """Enumeración de puertos en segundo plano."""

    found = pyqtSignal(list)

    def run(self) -> None:  # pragma: no cover - hilo
        self.found.emit(list_serial_ports())


# ------------------------------------------------------------------ simulador
class FlightSimulator:
    """Perfil de vuelo CanSat realista (balística + descenso con paracaídas)."""

    def __init__(self, rate_hz: float = 10.0) -> None:
        self.rate_hz = max(1.0, rate_hz)
        self.reset()

    def reset(self) -> None:
        self.t0 = time.monotonic()
        self.packet = 0
        self.phase = "ascenso"
        self._deploy_time: float | None = None

    def next(self) -> str:
        """Devuelve la siguiente trama CSV de telemetría."""
        elapsed = time.monotonic() - self.t0
        self.packet += 1

        # --- Altitud: ascenso hasta apogeo (45 s), luego caída ---------------
        if elapsed < 45.0:
            self.phase = "ascenso"
            altitude = 1150.0 * (1.0 - math.exp(-elapsed / 18.0)) + 12.0 * elapsed * 0.15
        else:
            if self._deploy_time is None:
                self._deploy_time = elapsed
            self.phase = "descenso"
            fall = elapsed - 45.0
            if fall < 25.0:            # caída libre hasta desplegar
                altitude = 800.0 - 12.0 * fall
            else:                     # descenso con paracaídas (~5 m/s)
                altitude = 500.0 - 5.0 * (fall - 25.0)
            altitude = max(altitude, 0.0)

        # --- Ambiente --------------------------------------------------------
        pressure = 1013.25 * math.exp(-altitude / 8434.5)
        temperature = 15.0 - 0.0065 * altitude + 1.2 * math.sin(elapsed / 30.0)
        if self.phase == "descenso" and (elapsed - 45.0) >= 25.0:
            temperature += 1.5  # el suelo está más caliente que la tropopausa

        # --- Batería: 9 V con consumo enogee durante el vuelo ---------------
        voltage = 9.0 - 0.9 * (1.0 - math.exp(-elapsed / 260.0)) - random.uniform(0.0, 0.02)
        if elapsed > 300.0:
            voltage = max(voltage - 0.002 * (elapsed - 300.0), 5.0)

        # --- Actitud: cabeceo/alabeo por turbulencia + guiñada lenta --------
        pitch = 62.0 * math.exp(-max(elapsed - 20.0, 0.0) / 12.0) + random.gauss(0.0, 1.2)
        if self.phase == "descenso":
            pitch = 3.0 + random.gauss(0.0, 2.5)
        roll = 8.0 * math.sin(elapsed / 4.0) + random.gauss(0.0, 1.5)
        yaw = (elapsed * 9.0) % 360.0
        if self.phase == "descenso":
            roll = 6.0 * math.sin(elapsed / 3.0) + random.gauss(0.0, 1.0)

        state = 1 if self.phase == "ascenso" else 2
        satellite = 1 if (self._deploy_time is not None and elapsed - 45.0 > 6.0) else 0
        chute = 1 if (self._deploy_time is not None and elapsed - 45.0 > 25.0) else 0

        return protocol.Telemetry(
            t=elapsed,
            altitude=altitude,
            temperature=temperature,
            pressure=pressure,
            voltage=voltage,
            pitch=pitch,
            roll=roll,
            yaw=yaw,
            state=state,
            satellite=satellite,
            chute=chute,
            packet=self.packet,
        )


# ----------------------------------------------------------------- hilo lector
class SerialWorker(QThread):
    """Hilo de recepción de telemetría por puerto serie.

    Señales emitidas:
        ``telemetry(Telemetry)``   paquete válido recibido
        ``log(str, str)``          mensaje de consola (texto, nivel)
        ``linked(bool, str)``      cambio de estado del enlace
        ``stats(int, float, float)`` paquetes, paquetes perdidos, paquetes/s
    """

    telemetry = pyqtSignal(object)
    log = pyqtSignal(str, str)
    linked = pyqtSignal(bool, str)
    stats = pyqtSignal(int, float, float)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.recorder = CsvRecorder()

        self._stop_event = threading.Event()
        self._port_lock = threading.Lock()
        self._port = ""
        self._baudrate = 115200
        self._simulation = False
        self._outbox: list = []
        self._serial = None

        self._packets = 0
        self._lost = 0
        self._last_packet = 0
        self._window_start = time.monotonic()
        self._window_packets = 0

    # -------------------------------------------------------------- controles
    def configure(self, port: str, baudrate: int) -> None:
        """Ajusta la configuración del enlace (aplicada al conectar)."""
        with self._port_lock:
            self._port = port
            self._baudrate = int(baudrate)
            self._simulation = port == SIM_TAG

    def send_command(self, command: str) -> None:
        """Encola un comando para enviar al|Arduino (o simulación)."""
        with self._port_lock:
            self._outbox.append(command)

    def start_recording(self, path: str) -> bool:
        return self.recorder.start(path)

    def stop_recording(self) -> int:
        return self.recorder.stop()

    def shutdown(self, timeout_ms: int = 2500) -> None:
        """Pide el cierre y espera a que el hilo termine."""
        self._stop_event.set()
        if self.isRunning():
            self.wait(timeout_ms)

    # ------------------------------------------------------------------ run
    def run(self) -> None:  # pragma: no cover - hilo
        with self._port_lock:
            port, baudrate, simulation = self._port, self._baudrate, self._simulation
        self._reset_counters()

        handle = None
        if simulation:
            self.log.emit("MODO SIMULACIÓN: fuente de telemetría virtual", "warn")
            self.log.emit("TX interfaz -> CanSat simulado", "info")
            self._run_simulation()
            return

        if not SERIAL_AVAILABLE:
            self.log.emit("pyserial no instalado: no se puede abrir el puerto", "error")
            self.linked.emit(False, "SIN PYSERIAL")
            return

        try:
            handle = serial.Serial(port=port, baudrate=baudrate, timeout=0.2)
        except Exception as exc:
            self.log.emit(f"No se pudo abrir {port} @ {baudrate}: {exc}", "error")
            self.linked.emit(False, "ERROR DE APERTURA")
            return

        self._serial = handle
        self.linked.emit(True, f"{port} @ {baudrate}")
        self.log.emit(f"Enlace abierto: {port} @ {baudrate} 8N1", "ok")

        buffer = b""
        last_report = time.monotonic()
        try:
            while not self._stop_event.is_set():
                chunk = handle.read(512)
                if chunk:
                    buffer += chunk
                    if len(buffer) > 8192:      # descarta basura acumulada
                        buffer = buffer[-4096:]
                        self.log.emit("Buffer desbordado: trama perdida", "warn")
                    while b"\n" in buffer or b"\r" in buffer:
                        line, buffer = self._split_frame(buffer)
                        if line is None:
                            break
                        self._handle_line(line)
                    if time.monotonic() - last_report > 1.0:
                        self._report_stats()
                        last_report = time.monotonic()
                else:
                    self._flush_pending()
                    now = time.monotonic()
                    if now - last_report >= 1.0:
                        self._report_stats()
                        last_report = now
        finally:
            self._close(handle)

    # ------------------------------------------------------------- simulación
    def _run_simulation(self) -> None:
        """Bucle del simulador con la misma interfaz de señales."""
        simulator = FlightSimulator()
        interval = 1.0 / simulator.rate_hz
        next_tick = time.monotonic()
        last_report = next_tick
        self.linked.emit(True, "SIMULADOR @ 10 Hz")

        while not self._stop_event.is_set():
            now = time.monotonic()
            if now < next_tick:
                self._stop_event.wait(min(next_tick - now, 0.05))
                self._flush_pending()
                continue
            next_tick += interval
            if next_tick < now:                  # evita ráfagas tras un retardo
                next_tick = now + interval
            self._handle_line(_encode(simulator.next()))
            if now - last_report >= 1.0:
                self._report_stats()
                last_report = now

        self._close(None)

    # ------------------------------------------------------------- auxiliares
    @staticmethod
    def _split_frame(buffer: bytes):
        """Extrae una trama delimitada por \\r o \\n. Devuelve (linea, resto)."""
        for sep in (b"\n", b"\r"):
            index = buffer.find(sep)
            if index != -1:
                line = buffer[:index]
                rest = buffer[index + 1:]
                if not line.strip():
                    return None, rest          # línea vacía: sigue
                return line, rest
        return None, buffer

    def _handle_line(self, raw: bytes) -> None:
        """Decodifica y clasifica una trama recibida."""
        try:
            text = raw.decode("utf-8", errors="replace").strip()
        except Exception:
            return
        if not text:
            return

        try:
            telemetry = protocol.parse_telemetry(text)
        except protocol.ProtocolError as exc:
            self._lost += 1
            self.log.emit(f"RX corrupto: {exc}", "error")
            return

        if telemetry is None:
            event = protocol.parse_event(text)
            if event:
                self.log.emit(f"RX << {event}", "info")
            else:
                self.log.emit(f"RX ?? {text}", "warn")
            return

        # Control de paquetes perdidos (contador monotónico del|Arduino)
        if telemetry.packet > 0:
            if self._last_packet and telemetry.packet > self._last_packet + 1:
                self._lost += telemetry.packet - self._last_packet - 1
            self._last_packet = telemetry.packet

        self._packets += 1
        self._window_packets += 1
        self.recorder.write(telemetry)
        self.telemetry.emit(telemetry)
        self._flush_pending()

    def _flush_pending(self) -> None:
        """Vacía la cola de comandos hacia el|Arduino."""
        with self._port_lock:
            pending, self._outbox = self._outbox, []
        for command in pending:
            if self._simulation or self._serial is None:
                self.log.emit(f"TX >> {command}  (simulado)", "info")
                continue
            try:
                payload = command if command.endswith("\n") else command + "\n"
                self._serial.write(payload.encode("ascii", "ignore"))
                self.log.emit(f"TX >> {command}", "tx")
            except Exception as exc:
                self.log.emit(f"Error enviando '{command}': {exc}", "error")

    def _reset_counters(self) -> None:
        self._packets = 0
        self._lost = 0
        self._last_packet = 0
        self._window_packets = 0
        self._window_start = time.monotonic()

    def _report_stats(self) -> None:
        elapsed = max(time.monotonic() - self._window_start, 1e-6)
        rate = self._window_packets / elapsed
        self._window_packets = 0
        self._window_start = time.monotonic()
        self.stats.emit(self._packets, float(self._lost), rate)

    def _close(self, handle) -> None:
        rows = self.recorder.stop()
        if rows:
            self.log.emit(f"Grabación finalizada: {self.recorder.path} ({rows} muestras)", "info")
        if handle is not None:
            try:
                handle.close()
            except Exception:
                pass
        self._serial = None
        self.linked.emit(False, "DESCONECTADO")
        self.log.emit("Enlace cerrado", "info")
        self.stats.emit(self._packets, float(self._lost), 0.0)