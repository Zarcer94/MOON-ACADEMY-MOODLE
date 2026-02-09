import os
from PySide6.QtCore import Signal, Qt, QUrl
from PySide6.QtGui import QPixmap, QDesktopServices
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QFrame, QHBoxLayout

from app.utils import resource_path


class Card(QFrame):
    """Tarjeta reutilizable. La apariencia la define el QSS."""
    def __init__(self):
        super().__init__()
        self.setObjectName("Card")


class HomeScreen(QWidget):
    """
    Panel principal.

    Botones:
    - Registro de usuarios
    - Gestión de cursos
    - Alumnos por curso
    - Abrir Moodle en navegador
    - Cerrar sesión
    """
    go_users = Signal()
    go_courses = Signal()
    go_students = Signal()
    logout = Signal()

    URL_MOODLE = "https://41438038.servicio-online.net/my/"

    def __init__(self):
        super().__init__()

        layout_raiz = QVBoxLayout(self)
        layout_raiz.setContentsMargins(24, 24, 24, 24)
        layout_raiz.setSpacing(14)

        # =========================
        # Cabecera (izq textos, der logo Moodle)
        # =========================
        cabecera = QHBoxLayout()
        cabecera.setSpacing(12)

        col_izq = QVBoxLayout()
        col_izq.setSpacing(6)

        self.lbl_usuario = QLabel("Bienvenido/a")
        self.lbl_usuario.setStyleSheet("font-size: 16px; font-weight: 800;")
        self.lbl_usuario.setAlignment(Qt.AlignLeft | Qt.AlignTop)

        titulo = QLabel("Panel principal")
        titulo.setStyleSheet("font-size: 22px; font-weight: 900;")
        titulo.setAlignment(Qt.AlignLeft | Qt.AlignTop)

        col_izq.addWidget(self.lbl_usuario)
        col_izq.addWidget(titulo)
        cabecera.addLayout(col_izq, 1)

        self.logo_moodle = QLabel(alignment=Qt.AlignRight | Qt.AlignTop)
        self._poner_logo_moodle()
        cabecera.addWidget(self.logo_moodle, 0, Qt.AlignRight | Qt.AlignTop)

        layout_raiz.addLayout(cabecera)

        # =========================
        # Centro (card + botones)
        # =========================
        fila_centro = QHBoxLayout()
        fila_centro.addStretch(1)

        card = Card()
        card.setMaximumWidth(760)
        card.setMinimumHeight(380)
        card.setObjectName("HomeCard")

        layout_card = QVBoxLayout(card)
        layout_card.setContentsMargins(22, 22, 22, 22)
        layout_card.setSpacing(12)
        layout_card.setAlignment(Qt.AlignCenter)

        self.logo_academia = QLabel(alignment=Qt.AlignCenter)
        self._poner_logo_academia()
        layout_card.addWidget(self.logo_academia)

        self.btn_usuarios = QPushButton("Registro de usuarios")
        self.btn_cursos = QPushButton("Gestión de cursos")
        self.btn_alumnos = QPushButton("Alumnos por curso")

        self.btn_moodle = QPushButton("Acceso a Moodle")
        self.btn_moodle.setObjectName("OrangeButton")  # 👈 QSS

        self.btn_logout = QPushButton("Cerrar sesión")
        self.btn_logout.setObjectName("RedButton")  # 👈 QSS

        # Altura consistente
        for b in (self.btn_usuarios, self.btn_cursos, self.btn_alumnos, self.btn_moodle, self.btn_logout):
            b.setMinimumHeight(48)

        layout_card.addWidget(self.btn_usuarios)
        layout_card.addWidget(self.btn_cursos)
        layout_card.addWidget(self.btn_alumnos)
        layout_card.addWidget(self.btn_moodle)
        layout_card.addWidget(self.btn_logout)

        fila_centro.addWidget(card)
        fila_centro.addStretch(1)

        layout_raiz.addStretch(1)
        layout_raiz.addLayout(fila_centro)
        layout_raiz.addStretch(2)

        # =========================
        # Conexiones
        # =========================
        self.btn_usuarios.clicked.connect(self.go_users.emit)
        self.btn_cursos.clicked.connect(self.go_courses.emit)
        self.btn_alumnos.clicked.connect(self.go_students.emit)
        self.btn_moodle.clicked.connect(self.abrir_moodle)
        self.btn_logout.clicked.connect(self.logout.emit)

    def abrir_moodle(self):
        """Abre Moodle en el navegador por defecto."""
        QDesktopServices.openUrl(QUrl(self.URL_MOODLE))

    def _poner_logo_academia(self):
        ruta = resource_path(os.path.join("styles", "logo.png"))
        pix = QPixmap(ruta)
        if pix.isNull():
            self.logo_academia.setText("MOON ACADEMY")
            self.logo_academia.setStyleSheet("font-size: 28px; font-weight: 900;")
            return
        self.logo_academia.setPixmap(pix.scaled(360, 180, Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def _poner_logo_moodle(self):
        ruta = resource_path(os.path.join("styles", "logo moodle.png"))
        pix = QPixmap(ruta)
        if pix.isNull():
            self.logo_moodle.setText("Moodle")
            self.logo_moodle.setStyleSheet("font-size: 18px; font-weight: 800;")
            return
        self.logo_moodle.setPixmap(pix.scaled(300, 120, Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def set_welcome_name(self, firstname: str):
        """Llamado por el router tras login."""
        self.lbl_usuario.setText(f"Bienvenido/a, {firstname}")
