#!/usr/bin/env python3
"""
Estación Terrestre (Ground Station) para CanSat
==============================================

Punto de entrada de la aplicación.

DEPENDENCIAS
------------
    pip install PyQt5 pyqtgraph PyOpenGL numpy pyserial

    * PyQt5      -> interfaz gráfica
    * pyqtgraph  -> gráficas en tiempo real
    * PyOpenGL   -> vista 3D del satélite (pyqtgraph.opengl)
    * numpy      -> dependencia interna de pyqtgraph
    * pyserial   -> acceso al puerto COM/TTL

    Equivalente:  pip install -r requirements.txt

    Linux (Debian/Ubuntu) necesita las librerías de sistema para OpenGL:
        sudo apt install libgl1 libglu1-mesa x11-utils
        Si PyOpenGL no está disponible, la aplicación arranca igualmente
        con el horizonte artificial 2D.

USO
---
    python3 main.py [--sim] [--port TTYUSB0] [--baud 115200]

        --sim            arranca con el simulador de vuelo ya seleccionado
        --port PUERTO    puerto inicial (COM3, /dev/ttyUSB0, ...)
        --baud N         velocidad inicial en baudios

ESTRUCTURA DEL CÓDIGO
---------------------
    main.py                     arranque y opciones de línea de comandos
    gs/main_window.py           dashboard y cableado de señales
    gs/theme.py                 paleta dark y hoja de estilos Qt
    gs/protocol.py              parseo de tramas CSV y comandos
    gs/serial_worker.py         QThread de recepción serie + simulador
    gs/recording.py             grabación CSV
    gs/widgets/                 connection, indicator, plots, attitude, console
"""

from __future__ import annotations

import argparse
import os
import sys

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QGuiApplication
from PyQt5.QtWidgets import QApplication

from gs import theme
from gs.main_window import APP_TITLE, MainWindow
from gs.serial_worker import SERIAL_AVAILABLE


def parse_args(argv: list | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="CanSat Ground Station (PyQt5 + PyQtGraph + OpenGL)")
    parser.add_argument("--port", help="puerto serie inicial (COM3, /dev/ttyUSB0)")
    parser.add_argument("--baud", type=int, default=115200, help="baudios (def. 115200)")
    parser.add_argument("--sim", action="store_true",
                        help="selecciona el simulador de vuelo al arrancar")
    return parser.parse_args(argv)


def main(argv: list | None = None) -> int:
    args = parse_args(argv)

    # La escala HiDPI debe fijarse antes de crear la aplicación.
    QGuiApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QGuiApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv[:1] + list(argv or []))
    app.setApplicationName(APP_TITLE)
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("CanSat Team")
    app.setStyleSheet(theme.STYLESHEET)

    try:
        import pyqtgraph as pg

        theme.apply_graph_theme(pg)
    except Exception as exc:
        print(f"[aviso] pyqtgraph no disponible: {exc}", file=sys.stderr)

    os.makedirs("grabaciones", exist_ok=True)

    window = MainWindow(
        initial_port=args.port,
        initial_baudrate=args.baud,
        force_simulation=args.sim or not SERIAL_AVAILABLE,
    )
    window.show()
    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())