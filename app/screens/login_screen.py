import os
import traceback

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QPushButton, QMessageBox, QFrame
)

from app.utils import resource_path, log_line
from app.moodle_client import MoodleClient, login_get_token
from app.session import Session


class Card(QFrame):
    """Contenedor tipo tarjeta (la estética la define el QSS con #Card)."""
    def __init__(self):
        super().__init__()
        self.setObjectName("Card")


class LoginScreen(QWidget):
    """
    Pantalla de login.

    Flujo:
    1) Usuario escribe usuario/contraseña
    2) Pedimos token a Moodle
    3) Leemos site_info para obtener userid/nombre
    4) Verificamos permisos (heurística: puede leer participantes)
    5) Emitimos login_success(Session)
    """
    login_success = Signal(object)  # Session

    def __init__(self, config: dict):
        super().__init__()
        self.setObjectName("LoginScreen")
        self._cfg = config

        # =========================
        # Layout raíz (centrado)
        # =========================
        layout_raiz = QVBoxLayout(self)
        layout_raiz.setContentsMargins(24, 24, 24, 24)
        layout_raiz.setSpacing(12)
        layout_raiz.addStretch(1)

        fila_centrada = QHBoxLayout()
        fila_centrada.addStretch(1)

        card = Card()
        card.setMaximumWidth(760)
        card.setMinimumHeight(360)

        layout_card = QVBoxLayout(card)
        layout_card.setContentsMargins(28, 28, 28, 28)
        layout_card.setSpacing(16)
        layout_card.setAlignment(Qt.AlignCenter)

        # =========================
        # Logo
        # =========================
        self.logo = QLabel(alignment=Qt.AlignCenter)
        self._poner_logo_academia()
        layout_card.addWidget(self.logo)

        # =========================
        # Formulario
        # =========================
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)

        self.input_usuario = QLineEdit()
        self.input_usuario.setPlaceholderText("Usuario")

        self.input_password = QLineEdit()
        self.input_password.setPlaceholderText("Contraseña")
        self.input_password.setEchoMode(QLineEdit.Password)

        form.addRow("Usuario:", self.input_usuario)
        form.addRow("Contraseña:", self.input_password)
        layout_card.addLayout(form)

        # =========================
        # Botón entrar
        # =========================
        self.boton_login = QPushButton("ENTRAR")
        self.boton_login.setObjectName("GreenButton")  
        self.boton_login.setMinimumHeight(44)
        self.boton_login.setMinimumWidth(200)

        fila_boton = QHBoxLayout()
        fila_boton.addStretch(1)
        fila_boton.addWidget(self.boton_login)
        fila_boton.addStretch(1)
        layout_card.addLayout(fila_boton)

        # Texto inferior
        self.label_estado = QLabel("Acceso solo para profesores.", alignment=Qt.AlignCenter)
        layout_card.addWidget(self.label_estado)

        fila_centrada.addWidget(card)
        fila_centrada.addStretch(1)

        layout_raiz.addLayout(fila_centrada)
        layout_raiz.addStretch(2)

        # =========================
        # Conexiones
        # =========================
        self.boton_login.clicked.connect(self.do_login)
        self.input_usuario.returnPressed.connect(self.input_password.setFocus)
        self.input_password.returnPressed.connect(self.boton_login.click)

    def _poner_logo_academia(self):
        """Carga styles/logo.png; si no existe, muestra texto."""
        ruta_logo = resource_path(os.path.join("styles", "logo.png"))
        pix = QPixmap(ruta_logo)
        if pix.isNull():
            self.logo.setText("MOON ACADEMY")
            self.logo.setStyleSheet("font-size: 28px; font-weight: 900;")
            return
        self.logo.setPixmap(pix.scaled(360, 180, Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def _mostrar_error(self, titulo: str, mensaje: str, detalles: str = ""):
        """Popup de error con detalles desplegables."""
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Critical)
        box.setWindowTitle(titulo)
        box.setText(mensaje)
        if detalles:
            box.setDetailedText(detalles)
        box.setMinimumWidth(680)
        box.exec()

    def do_login(self):
        """
        Login real:
        - valida inputs
        - obtiene token
        - lee site_info para userid
        - verifica permisos
        - crea Session y emite login_success
        """
        try:
            usuario = self.input_usuario.text().strip()
            password = self.input_password.text().strip()

            if not usuario or not password:
                raise RuntimeError("Introduce usuario y contraseña.")

            base_url = self._cfg["base_url"]
            service = self._cfg["service"]

            log_line(f"[LOGIN] base_url={base_url} service={service} username={usuario}")

            token = login_get_token(base_url, usuario, password, service)
            log_line("[LOGIN] token obtenido OK")

            cliente = MoodleClient(base_url, token)
            info = cliente.site_info()

            userid_raw = info.get("userid")
            if userid_raw is None:
                raise RuntimeError("No se pudo resolver userid desde site_info.")

            userid = int(userid_raw)

            if not cliente.can_read_participants_in_any_course(userid):
                raise RuntimeError("Acceso denegado: solo profesores.")

            firstname = info.get("firstname") or usuario

            sesion = Session(
                base_url=base_url,
                token=token,
                userid=userid,
                username=info.get("username", usuario),
                firstname=firstname,
            )

            self.login_success.emit(sesion)

        except Exception:
            detalles = traceback.format_exc()
            log_line("[ERROR] " + detalles.replace("\n", " | "))
            self._mostrar_error("Login fallido", "No se pudo iniciar sesión.", detalles)
