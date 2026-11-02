"""Tema oscuro aerospacial: paleta, estilos Qt y estilos de pyqtgraph."""

from __future__ import annotations


class Colors:
    """Paleta central de la aplicación (dark mode aerospacial)."""

    BG_DEEP = "#070b10"        # fondo de ventana
    BG_PANEL = "#0f1620"       # fondo de panel
    BG_WIDGET = "#141d29"      # fondo de widget/input
    BG_HEADER = "#1b2735"      # cabeceras y barras
    BORDER = "#22303f"         # borde sutil
    BORDER_FOCUS = "#00d4ff"   # borde con foco

    TEXT = "#e6edf3"
    TEXT_DIM = "#8fa3b8"
    TEXT_FAINT = "#5b6b7d"

    ACCENT = "#00d4ff"         # cian telemetría
    ACCENT_2 = "#7c5cff"       # violeta
    OK = "#00e676"
    WARN = "#ffb300"
    ERROR = "#ff5252"
    INFO = "#29b6f6"

    ALT = "#00d4ff"
    TEMP = "#ff8a3d"
    PRESS = "#7c5cff"
    VOLT = "#00e676"
    PITCH = "#ffb300"


#: Tamaño de fuente base y família monoespaciada para lecturas numéricas.
FONT_FAMILY = "Segoe UI, DejaVu Sans, Arial, sans-serif"
MONO_FAMILY = "Consolas, DejaVu Sans Mono, Menlo, monospace"


STYLESHEET = f"""
QWidget {{
    background-color: {Colors.BG_DEEP};
    color: {Colors.TEXT};
    font-family: {FONT_FAMILY};
    font-size: 13px;
}}

QMainWindow, QDialog {{
    background-color: {Colors.BG_DEEP};
}}

/* ---------- Paneles ---------- */
QLabel {{
    background: transparent;
    border: none;
}}

QFrame#Panel {{
    background-color: {Colors.BG_PANEL};
    border: 1px solid {Colors.BORDER};
    border-radius: 10px;
}}

QFrame#Card {{
    background-color: {Colors.BG_WIDGET};
    border: 1px solid {Colors.BORDER};
    border-radius: 8px;
}}

QFrame#Header {{
    background-color: {Colors.BG_HEADER};
    border: none;
    border-bottom: 1px solid {Colors.BORDER};
    border-radius: 0px;
}}

QLabel#PanelTitle {{
    color: {Colors.ACCENT};
    font-size: 12px;
    font-weight: bold;
    letter-spacing: 2px;
    padding: 8px 10px 6px 10px;
    background: transparent;
    border: none;
}}

QLabel#Hint {{
    color: {Colors.TEXT_FAINT};
    font-size: 11px;
    background: transparent;
    border: none;
}}

/* ---------- Indicadores ---------- */
QLabel#IndLabel {{
    color: {Colors.TEXT_DIM};
    font-size: 11px;
    font-weight: bold;
    letter-spacing: 1px;
    background: transparent;
    border: none;
}}

QLabel#IndValue {{
    font-family: {MONO_FAMILY};
    font-size: 26px;
    font-weight: bold;
    color: {Colors.TEXT};
    background: transparent;
    border: none;
}}

QLabel#IndUnit {{
    color: {Colors.TEXT_FAINT};
    font-size: 11px;
    background: transparent;
    border: none;
}}

/* ---------- Inputs ---------- */
QComboBox, QLineEdit, QSpinBox, QDoubleSpinBox {{
    background-color: {Colors.BG_WIDGET};
    border: 1px solid {Colors.BORDER};
    border-radius: 6px;
    padding: 6px 8px;
    selection-background-color: {Colors.ACCENT};
    selection-color: #06121a;
}}

QComboBox:hover, QLineEdit:hover, QSpinBox:hover {{
    border: 1px solid #2f4256;
}}

QComboBox:focus, QLineEdit:focus, QSpinBox:focus {{
    border: 1px solid {Colors.BORDER_FOCUS};
}}

QComboBox::drop-down {{
    border: none;
    width: 22px;
}}

QComboBox QAbstractItemView {{
    background-color: {Colors.BG_WIDGET};
    border: 1px solid {Colors.BORDER};
    selection-background-color: {Colors.ACCENT};
    selection-color: #06121a;
    outline: none;
}}

/* ---------- Botones ---------- */
QPushButton {{
    background-color: {Colors.BG_HEADER};
    border: 1px solid {Colors.BORDER};
    border-radius: 6px;
    padding: 7px 12px;
    font-weight: bold;
    color: {Colors.TEXT};
}}

QPushButton:hover {{
    background-color: #24344a;
    border-color: {Colors.ACCENT};
}}

QPushButton:pressed {{
    background-color: #16202c;
}}

QPushButton:disabled {{
    color: {Colors.TEXT_FAINT};
    background-color: #121924;
    border-color: #1b242f;
}}

QPushButton#Primary {{
    background-color: {Colors.OK};
    color: #04140c;
    border: none;
}}

QPushButton#Primary:hover {{ background-color: #33f08c; }}
QPushButton#Primary:disabled {{ background-color: #1c4a35; color: #6b7f75; }}

QPushButton#Danger {{
    background-color: {Colors.ERROR};
    color: #ffffff;
    border: none;
}}

QPushButton#Danger:hover {{ background-color: #ff6f6f; }}
QPushButton#Danger:disabled {{ background-color: #4a1f26; color: #8a6a70; }}

QPushButton#Accent {{
    background-color: {Colors.ACCENT};
    color: #04121a;
    border: none;
}}

QPushButton#Accent:hover {{ background-color: #4fe3ff; }}
QPushButton#Accent:disabled {{ background-color: #123a48; color: #5c7d88; }}

QPushButton#Warn {{
    background-color: {Colors.WARN};
    color: #1a1200;
    border: none;
}}

QPushButton#Warn:hover {{ background-color: #ffc733; }}
QPushButton#Warn:disabled {{ background-color: #4d3c12; color: #8a7a52; }}

/* ---------- Casillas / radios ---------- */
QCheckBox, QRadioButton {{
    color: {Colors.TEXT_DIM};
    background: transparent;
    spacing: 7px;
}}

QCheckBox::indicator, QRadioButton::indicator {{
    width: 15px;
    height: 15px;
    border: 1px solid {Colors.BORDER};
    background-color: {Colors.BG_WIDGET};
}}

QCheckBox::indicator {{ border-radius: 4px; }}
QRadioButton::indicator {{ border-radius: 8px; }}

QCheckBox::indicator:checked {{
    background-color: {Colors.ACCENT};
    border: 1px solid {Colors.ACCENT};
}}

QRadioButton::indicator:checked {{
    background-color: {Colors.ACCENT};
    border: 3px solid {Colors.BG_WIDGET};
    outline: 1px solid {Colors.ACCENT};
}}

/* ---------- Consola ---------- */
QPlainTextEdit#Console {{
    background-color: #05080c;
    border: 1px solid {Colors.BORDER};
    border-radius: 8px;
    font-family: {MONO_FAMILY};
    font-size: 11px;
    color: {Colors.TEXT};
}}

/* ---------- Barras de progreso / scroll ---------- */
QProgressBar {{
    background-color: {Colors.BG_WIDGET};
    border: 1px solid {Colors.BORDER};
    border-radius: 6px;
    text-align: center;
    color: {Colors.TEXT_DIM};
    font-size: 11px;
}}

QProgressBar::chunk {{
    background-color: {Colors.ACCENT};
    border-radius: 5px;
}}

QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 2px;
}}

QScrollBar::handle:vertical {{
    background: #2b3a4c;
    border-radius: 5px;
    min-height: 28px;
}}

QScrollBar::handle:vertical:hover {{ background: {Colors.ACCENT}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0px; }}

QScrollBar:horizontal {{
    background: transparent;
    height: 10px;
    margin: 2px;
}}

QScrollBar::handle:horizontal {{
    background: #2b3a4c;
    border-radius: 5px;
    min-width: 28px;
}}

QScrollBar::add-page, QScrollBar::sub-page {{ background: none; }}

/* ---------- Varios ---------- */
QSplitter::handle {{ background-color: {Colors.BORDER}; }}
QSplitter::handle:hover {{ background-color: {Colors.ACCENT}; }}

QStatusBar {{
    background-color: {Colors.BG_HEADER};
    border-top: 1px solid {Colors.BORDER};
    color: {Colors.TEXT_DIM};
}}

QStatusBar::item {{ border: none; }}

QToolTip {{
    background-color: {Colors.BG_HEADER};
    color: {Colors.TEXT};
    border: 1px solid {Colors.ACCENT};
    padding: 4px;
}}

QMenu {{
    background-color: {Colors.BG_WIDGET};
    border: 1px solid {Colors.BORDER};
}}

QMenu::item:selected {{ background-color: {Colors.ACCENT}; color: #06121a; }}
"""


def apply_graph_theme(pg) -> None:
    """Aplica la paleta oscura a pyqtgraph (llamar tras importar pyqtgraph)."""
    pg.setConfigOption("background", Colors.BG_PANEL)
    pg.setConfigOption("foreground", Colors.TEXT_DIM)
    pg.setConfigOptions(antialias=True)

    # Ejes con estética "instrumentación": fondo de etiquetas translúcido
    for axis_name in ("left", "bottom", "right", "top"):
        try:
            axis = pg.getViewBox().getAxis(axis_name)
        except Exception:  # pragma: no cover - depende de la versión de pyqtgraph
            axis = None
        if axis is None:
            continue
        axis.setPen(pg.mkPen(Colors.BORDER))
        axis.setTextPen(pg.mkPen(Colors.TEXT_FAINT))
        axis.setStyle(tickFont=lambda *a: _tick_font())
        axis.setHeight(42)
        axis.setWidth(58)


def _tick_font():
    from PyQt5.QtGui import QFont

    font = QFont("Consolas")
    font.setPointSize(8)
    return font