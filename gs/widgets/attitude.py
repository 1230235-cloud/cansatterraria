"""Indicador de actitud.

* :class:`Satellite3DView`: modelo OpenGL del CanSat (fuselaje, morro,
  paneles solares, antena) sobre ``pyqtgraph.opengl.GLViewWidget``; rota
  con los ángulos pitch / roll / yaw recibidos.
* :class:`Attitude2DView`: horizonte artificial dibujado con QPainter,
  usado como respaldo si PyOpenGL no está disponible.
* :class:`AttitudeIndicator`: fachada que elige el backend 3D o 2D.

Convención de ejes (aeronáutica, ejes cuerpo):
    roll  -> rotación longitudinal   (eje X)
    pitch -> rotación transversal   (eje Y)
    yaw   -> rotación vertical      (eje Z)
"""

from __future__ import annotations

import math

from PyQt5.QtCore import QPoint, QRectF, Qt
from PyQt5.QtGui import QColor, QFont, QPainter, QPen, QPolygon, QVector3D
from PyQt5.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ..theme import Colors
from .connection import Panel

OPENGL_AVAILABLE = False
OPENGL_ERROR = ""

try:  # pyqtgraph.opengl necesita PyOpenGL y un contexto GL válido
    import pyqtgraph.opengl as gl
    from pyqtgraph.opengl.MeshData import MeshData

    OPENGL_AVAILABLE = True
except Exception as exc:  # pragma: no cover - depende del entorno
    gl = None
    MeshData = None
    OPENGL_ERROR = str(exc)


# ------------------------------------------------------------------ vista 2D
class HorizonCanvas(QWidget):
    """Horizonte artificial: esfera de cima, retícula de cabeceo y alabeo."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(240, 220)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._pitch = 0.0
        self._roll = 0.0
        self._yaw = 0.0

    def update_state(self, pitch: float, roll: float, yaw: float) -> None:
        self._pitch, self._roll, self._yaw = float(pitch), float(roll), float(yaw)
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 (API Qt)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        cx, cy = self.width() // 2, self.height() // 2
        radius = int(min(self.width(), self.height()) * 0.40)
        box = QRectF(cx - radius, cy - radius, radius * 2, radius * 2)
        reach = radius * 3

        painter.save()
        painter.setClipRect(box)
        painter.translate(cx, cy)
        painter.rotate(-self._roll)

        offset = (self._pitch / 60.0) * radius
        painter.fillRect(QRectF(-reach, -reach + offset, reach * 2, reach),
                         QColor(0x0e, 0x3c, 0x60))
        painter.fillRect(QRectF(-reach, offset, reach * 2, reach),
                         QColor(0x3a, 0x2a, 0x14))
        painter.setPen(QPen(QColor(Colors.TEXT), 2))
        painter.drawLine(int(-reach), int(offset), int(reach), int(offset))

        painter.setFont(QFont("Consolas", 8))
        painter.setPen(QPen(QColor(0xb8, 0xcc, 0xdc, 210), 1))
        for angle in (-30, -20, -10, 10, 20, 30):
            y = offset - math.tan(math.radians(angle)) * radius
            half_w = radius * (0.55 if angle % 20 == 0 else 0.32)
            painter.drawLine(int(-half_w), int(y), int(half_w), int(y))
            painter.drawText(int(half_w + 8), int(y) + 4, str(abs(angle)))
        painter.restore()

        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(QColor(Colors.BORDER), 2))
        painter.drawEllipse(box)

        # Puntero de alabeo (triángulo superior, gira con la escena)
        painter.save()
        painter.translate(cx, cy)
        painter.rotate(-self._roll)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(Colors.WARN))
        painter.setClipRect(box.adjusted(0, 0, 0, -int(radius * 0.70)))
        painter.drawPolygon(QPolygon([
            QPoint(0, -int(radius * 0.80)),
            QPoint(-14, -int(radius * 0.80) - 20),
            QPoint(14, -int(radius * 0.80) - 20),
        ]))
        painter.restore()

        # Símbolo de la aeronave (referencia fija)
        painter.setPen(QPen(QColor(Colors.WARN), 3))
        arm = radius // 3
        painter.drawLine(cx - arm, cy, cx + arm, cy)
        painter.drawLine(cx - arm, cy, cx - arm, cy + arm // 3)
        painter.drawLine(cx + arm, cy, cx + arm, cy + arm // 3)

        painter.setFont(QFont("Consolas", 9))
        painter.setPen(QColor(Colors.PITCH))
        painter.drawText(10, 20, f"P {self._pitch:+06.1f}")
        painter.drawText(10, 36, f"R {self._roll:+06.1f}")
        painter.drawText(10, 52, f"Y {self._yaw:+06.1f}")
        painter.end()


class Attitude2DView(QWidget):
    """Vista 2D del indicador de actitud."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 10)
        layout.setSpacing(6)

        self.canvas = HorizonCanvas(self)
        layout.addWidget(self.canvas, 1)
        _holder, self.readout = _attitude_readout(self)
        layout.addWidget(_holder)

    def set_attitude(self, pitch: float, roll: float, yaw: float) -> None:
        self.canvas.update_state(pitch, roll, yaw)


# ------------------------------------------------------------------ vista 3D
def _box_mesh(width: float, height: float, depth: float, color) -> MeshData:
    """Malla de un paralelepípedo centrado en el origen, con color plano."""
    x, y, z = width / 2.0, height / 2.0, depth / 2.0
    vertices = [
        (-x, -y, -z), (x, -y, -z), (x, y, -z), (-x, y, -z),      # base
        (-x, -y, z), (x, -y, z), (x, y, z), (-x, y, z),            # tapa
    ]
    faces = [
        (0, 1, 2), (0, 2, 3),          # inferior
        (4, 6, 5), (4, 7, 6),          # superior
        (0, 4, 5), (0, 5, 1),          # frente
        (1, 5, 6), (1, 6, 2),          # derecha
        (2, 6, 7), (2, 7, 3),          # atrás
        (3, 7, 4), (3, 4, 0),          # izquierda
    ]
    vertex_colors = [(color.redF(), color.greenF(), color.blueF(), 1.0)] * 8
    return MeshData(vertexes=vertices, faces=faces, vertexColors=vertex_colors)


def _cone_mesh(radius: float, height: float, color) -> MeshData:
    """Malla de una pirámide de base cuadrada (morro del satélite)."""
    side = radius * 1.4142
    vertices = [
        (-side / 2, -side / 2, 0.0), (side / 2, -side / 2, 0.0),
        (side / 2, side / 2, 0.0), (-side / 2, side / 2, 0.0),
        (0.0, 0.0, height),
    ]
    faces = [(0, 1, 4), (1, 2, 4), (2, 3, 4), (3, 0, 4), (0, 3, 2), (0, 2, 1)]
    vertex_colors = [(color.redF(), color.greenF(), color.blueF(), 1.0)] * 5
    return MeshData(vertexes=vertices, faces=faces, vertexColors=vertex_colors)


class Satellite3DView(QWidget):
    """Modelo 3D del CanSat rotado según pitch / roll / yaw.

    La escena usa mallas propias (:class:`MeshData` + ``GLMeshItem``) porque
    ``GLBoxItem`` de pyqtgraph solo dibuja el alambre; así el satélite se ve
    sólido. El morro es una pirámide y los paneles solares son cajas finas.
    """

    FUSELAGE = QColor(96, 128, 165)
    NOSE = QColor(132, 168, 200)
    PANEL = QColor(28, 78, 168)
    BOOM = QColor(186, 200, 216)
    ANTENNA = QColor(255, 178, 0)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 10)
        layout.setSpacing(6)

        self.view = gl.GLViewWidget()
        self.view.setMinimumSize(260, 240)
        self.view.setBackgroundColor(QColor(Colors.BG_WIDGET))
        self.view.setCameraPosition(pos=QVector3D(0, 0, 0), distance=5.6,
                                    elevation=18, azimuth=35)
        layout.addWidget(self.view, 1)   # botón izq.: orbitar · Ctrl+izq.: desplazar

        _holder, self.readout = _attitude_readout(self)
        layout.addWidget(_holder)

        self._build_reference()

        self.model = self._build_model()
        self.view.addItem(self.model)
        self._pitch = self._roll = self._yaw = 0.0

    def _build_reference(self) -> None:
        """Ejes de referencia y rejilla de suelo."""
        self.view.addItem(gl.GLAxisItem(size=QVector3D(1.6, 1.6, 1.6),
                                        glOptions="translucent"))
        grid = gl.GLGridItem(size=QVector3D(10, 10, 1), color=(40, 55, 72, 170))
        grid.setSpacing(x=1.0, y=1.0)
        grid.translate(0, 0, -1.7)
        self.view.addItem(grid)

    # ------------------------------------------------------------ escena
    def _build_model(self):
        """Construye la jerarquía del satélite (raíz = fuselaje)."""
        root = gl.GLMeshItem(meshdata=_box_mesh(0.62, 0.62, 1.10, self.FUSELAGE))
        self._add(_cone_mesh(0.32, 0.46, self.NOSE), (0, 0, 0.55), root)
        self._add(_box_mesh(0.05, 0.05, 0.60, self.ANTENNA), (0, 0, -0.84), root)
        for sign in (1, -1):
            self._add(_box_mesh(0.62, 0.08, 0.08, self.BOOM),
                      (sign * 0.47, 0, 0.05), root)               # brazo
            self._add(_box_mesh(1.24, 0.12, 0.62, self.PANEL),
                      (sign * 1.00, 0, 0.05), root)               # panel solar
        return root

    @staticmethod
    def _add(mesh_data, pos, parent_item):
        """Crea un item de malla hijo y lo posiciona."""
        item = gl.GLMeshItem(meshdata=mesh_data)
        item.translate(*pos)
        item.setParentItem(parent_item)
        return item

    # ---------------------------------------------------------------- API
    def set_attitude(self, pitch: float, roll: float, yaw: float) -> None:
        """Aplica la actitud (yaw → pitch → roll) al modelo."""
        self._pitch, self._roll, self._yaw = float(pitch), float(roll), float(yaw)

        # Se reconstruye la transformación completa (resetTransform evita que
        # las rotaciones se acumulen entre muestras).
        self.model.resetTransform()
        self.model.rotate(self._yaw, 0, 0, 1)
        self.model.rotate(self._pitch, 0, 1, 0)
        self.model.rotate(self._roll, 1, 0, 0)

        self.readout[0].setText(f"P {pitch:+06.1f}")
        self.readout[1].setText(f"R {roll:+06.1f}")
        self.readout[2].setText(f"Y {yaw:+06.1f}")

    def reset_camera(self) -> None:
        """Devuelve la cámara a la vista de referencia."""
        self.view.setCameraPosition(pos=QVector3D(0, 0, 0), distance=5.6,
                                    elevation=18, azimuth=35)


def _attitude_readout(parent: QWidget):
    """Fila con las lecturas P/R/Y. Devuelve ``(widget, [etiquetas])``."""
    row = QHBoxLayout()
    row.setSpacing(14)
    row.setContentsMargins(0, 0, 0, 0)
    labels = []
    for text in ("P ---", "R ---", "Y ---"):
        label = QLabel(text, parent)
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet(
            f"font-family: Consolas, monospace; font-size: 12px; color: {Colors.PITCH};"
        )
        row.addWidget(label, 1)
        labels.append(label)
    holder = QWidget(parent)
    holder.setLayout(row)
    return holder, labels


# ------------------------------------------------------------------ fachada
class AttitudeIndicator(Panel):
    """Indicador de actitud con backend 3D (OpenGL) o 2D (respaldo)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("ACTITUD · MODELO 3D", parent)

        self.backend_name = "3D · OpenGL" if OPENGL_AVAILABLE else "2D · respaldo"
        self.view = Satellite3DView(self) if OPENGL_AVAILABLE else Attitude2DView(self)
        self.body.addWidget(self.view, 1)

        if not OPENGL_AVAILABLE:
            hint = QLabel(
                "PyOpenGL no disponible → horizonte artificial 2D.\n"
                f"Detalle: {OPENGL_ERROR or 'sin soporte OpenGL'}",
                self,
            )
            hint.setObjectName("Hint")
            hint.setWordWrap(True)
            hint.setAlignment(Qt.AlignCenter)
            self.body.addWidget(hint)

    def set_attitude(self, pitch: float, roll: float, yaw: float) -> None:
        self.view.set_attitude(pitch, roll, yaw)

    def clear(self) -> None:
        self.set_attitude(0.0, 0.0, 0.0)