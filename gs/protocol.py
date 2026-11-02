"""Protocolo de telemetría CanSat.

Formato de trama de telemetría (CSV, terminated por '\\r' o '\\n')::

    T,t,alt,temp,pres,vol,pitch,roll,yaw,state,sat,chute,packet

Ejemplo real::

    T,125.40,1042.6,22.8,891.4,8.61,3.1,-2.4,179.8,1,1,0,1254

Convenciones:
  * ``t``       segundos de misión (ST)
  * ``alt``     altitud en metros
  * ``temp``    temperatura en °C
  * ``pres``    presión en hPa
  * ``vol``     tensión de batería en V
  * ``pitch``   cabeceo en grados (+ arriba)
  * ``roll``    alabeo en grados (+ derecha)
  * ``yaw``     guiñada en grados
  * ``state``   estado de la misión (0 = pre-lanzamiento, 1 = vuelo, 2 = descenso)
  * ``sat``     estado del conjunto de parenthood (deploy)
  * ``chute``   estado del paracaídas
  * ``packet``  contador de paquetes

Tramas de estado/respuesta aceptadas y mostradas en consola:
  ``E,<texto>``  -> aviso/error del|Arduino
  ``OK,...`` / ``CMD,...`` -> confirmaciones
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional

TELEMETRY_PREFIX = "T"
EVENT_PREFIX = "E"

# Comandos hacia el|Arduino (CanSat 2023+ style)
CMD_CALIBRATE = "C,CAL,1"
CMD_INJECTION = "C,INJ,1"
CMD_DEPLOY_PARENT = "C,DEP,DEPLOY"
CMD_CUT_PARACHUTE = "C,CHUTE,CUT"
CMD_RECOVER = "C,SYS,RESET"

#: Comandos expuestos como botones en el panel de control.
COMMANDS: dict = {
    "Calibrar sensor": CMD_CALIBRATE,
    "Inyección": CMD_INJECTION,
    "Despliegue": CMD_DEPLOY_PARENT,
    "Cortar paracaídas": CMD_CUT_PARACHUTE,
    "Reset": CMD_RECOVER,
}

BAUDRATES = [9600, 19200, 38400, 57600, 74880, 115200, 230400, 460800, 921600]


@dataclass
class Telemetry:
    """Paquete de telemetría ya normalizado."""

    t: float = 0.0
    altitude: float = 0.0
    temperature: float = 0.0
    pressure: float = 0.0
    voltage: float = 0.0
    pitch: float = 0.0
    roll: float = 0.0
    yaw: float = 0.0
    state: int = 0
    satellite: int = 0
    chute: int = 0
    packet: int = 0
    received_at: float = field(default_factory=time.time)

    @property
    def st(self) -> str:
        """Tiempo de misión formateado HH:MM:SS."""
        total = int(self.t)
        sign = "-" if total < 0 else ""
        total = abs(total)
        return f"{sign}{total // 3600:02d}:{(total % 3600) // 60:02d}:{total % 60:02d}"

    @property
    def state_name(self) -> str:
        return {0: "PRE-LANZAMIENTO", 1: "VUELO ASCENSOR", 2: "DESCENSO",
                3: "ATERRIZAJE", 4: "FIN DE MISIÓN"}.get(self.state, f"S{self.state}")


class ProtocolError(ValueError):
    """Trama recibida que no cumple el protocolo."""


def _to_float(value: str, field_name: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ProtocolError(f"campo '{field_name}' no numérico: {value!r}") from exc


def parse_telemetry(line: str) -> Optional[Telemetry]:
    """Convierte una línea de telemetría en :class:`Telemetry`.

    Devuelve ``None`` si la línea no es una trama de telemetría válida
    (mensaje de estado o línea corrupta), para que el llamante pueda
    registrarla sin abortar el flujo.
    """
    if not line:
        return None

    frame = line.strip()
    if not frame:
        return None

    if not frame.startswith(TELEMETRY_PREFIX + ",") and frame != TELEMETRY_PREFIX:
        return None

    fields = frame.split(",")[1:]
    if len(fields) < 9:
        raise ProtocolError(f"trama incompleta ({len(fields)} campos): {frame!r}")

    def num(index: int, name: str, default: float = 0.0) -> float:
        if index >= len(fields) or fields[index].strip() == "":
            return default
        return _to_float(fields[index], name)

    telemetry = Telemetry(
        t=num(0, "t"),
        altitude=num(1, "alt"),
        temperature=num(2, "temp"),
        pressure=num(3, "pres"),
        voltage=num(4, "vol"),
        pitch=num(5, "pitch"),
        roll=num(6, "roll"),
        yaw=num(7, "yaw"),
        state=int(num(8, "state")),
        satellite=int(num(9, "sat", 0)),
        chute=int(num(10, "chute", 0)),
        packet=int(num(11, "packet", 0)),
    )

    for name in ("pitch", "roll", "yaw"):
        value = getattr(telemetry, name)
        if value < -360.0 or value > 360.0:
            raise ProtocolError(f"ángulo '{name}' fuera de rango: {value}")

    if telemetry.pressure < 0.0:
        raise ProtocolError(f"presión negativa: {telemetry.pressure}")

    return telemetry


def parse_event(line: str) -> Optional[str]:
    """Devuelve el texto de una trama de estado ``E,<texto>`` o ``None``."""
    frame = (line or "").strip()
    if not frame:
        return None
    if frame.startswith(EVENT_PREFIX + ","):
        return frame.split(",", 1)[1].strip() or "evento"
    if frame.startswith(("OK", "CMD", "ACK")):
        return frame
    return None


def format_csv_row(telemetry: Telemetry) -> str:
    """Serializa un paquete para el fichero CSV de grabación."""
    return ",".join([
        f"{telemetry.t:.2f}",
        f"{telemetry.altitude:.2f}",
        f"{telemetry.temperature:.2f}",
        f"{telemetry.pressure:.2f}",
        f"{telemetry.voltage:.3f}",
        f"{telemetry.pitch:.2f}",
        f"{telemetry.roll:.2f}",
        f"{telemetry.yaw:.2f}",
        str(telemetry.state),
        str(telemetry.satellite),
        str(telemetry.chute),
        str(telemetry.packet),
    ])


CSV_HEADER = (
    "mission_time_s,altitude_m,temperature_c,pressure_hpa,voltage_v,"
    "pitch_deg,roll_deg,yaw_deg,state,satellite,chute,packet"
)