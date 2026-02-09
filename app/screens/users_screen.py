import traceback
from typing import Optional, Dict, Any, List

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QComboBox, QMessageBox, QGridLayout, QFrame
)

from app.session import Session
from app.moodle_client import MoodleClient
from app.utils import load_locked_config


ROLEID_ESTUDIANTE_PRESENCIAL = 11


def _nombre_rol(roleid: int) -> str:
    """Nombre humano para el rol."""
    rid = int(roleid)
    if rid == ROLEID_ESTUDIANTE_PRESENCIAL:
        return "Estudiante Presencial"
    if rid == 5:
        return "Estudiante"
    return f"Rol {rid}"


class UsersScreen(QWidget):
    """
    Crear usuario + matricular.

    Requisitos:
    - admin_token en config/config.json para crear y matricular.
    """
    back = Signal()

    def __init__(self):
        super().__init__()

        self._session: Optional[Session] = None
        self._client: Optional[MoodleClient] = None
        self._cfg: Dict[str, Any] = {}

        layout_raiz = QVBoxLayout(self)
        layout_raiz.setContentsMargins(0, 0, 0, 0)
        layout_raiz.setSpacing(0)

        layout_raiz.addStretch(1)

        contenedor = QFrame()
        contenedor.setMaximumWidth(980)
        layout_contenedor = QVBoxLayout(contenedor)
        layout_contenedor.setContentsMargins(48, 36, 48, 32)
        layout_contenedor.setSpacing(18)

        layout_raiz.addWidget(contenedor, alignment=Qt.AlignHCenter)
        layout_raiz.addStretch(1)

        titulo = QLabel("Registro de usuarios (Estudiante por defecto)")
        titulo.setAlignment(Qt.AlignCenter)
        titulo.setStyleSheet("font-size: 22px; font-weight: 800; color: white;")
        layout_contenedor.addWidget(titulo)

        grid = QGridLayout()
        grid.setHorizontalSpacing(22)
        grid.setVerticalSpacing(14)
        layout_contenedor.addLayout(grid)

        self.ed_usuario = QLineEdit()
        self.ed_usuario.setPlaceholderText("usuario (sin espacios)")

        self.ed_password = QLineEdit()
        self.ed_password.setPlaceholderText("Obligatoria si el usuario no existe")
        self.ed_password.setEchoMode(QLineEdit.Password)

        self.ed_nombre = QLineEdit()
        self.ed_apellidos = QLineEdit()

        self.ed_email = QLineEdit()
        self.ed_email.setPlaceholderText("nombre@dominio.com")

        self.ed_rol = QLineEdit()
        self.ed_rol.setReadOnly(True)

        self.cb_curso = QComboBox()

        ANCHO_CAMPO = 640
        ALTO_CAMPO = 44
        for w in (self.ed_usuario, self.ed_password, self.ed_nombre, self.ed_apellidos, self.ed_email, self.ed_rol):
            w.setMinimumWidth(ANCHO_CAMPO)
            w.setMinimumHeight(ALTO_CAMPO)
        self.cb_curso.setMinimumWidth(ANCHO_CAMPO)
        self.cb_curso.setMinimumHeight(ALTO_CAMPO)

        fila = 0

        def add_row(etiqueta: str, widget):
            nonlocal fila
            lab = QLabel(etiqueta)
            lab.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            grid.addWidget(lab, fila, 0)
            grid.addWidget(widget, fila, 1)
            fila += 1

        add_row("Usuario:", self.ed_usuario)
        add_row("Contraseña (si es nuevo):", self.ed_password)
        add_row("Nombre:", self.ed_nombre)
        add_row("Apellidos:", self.ed_apellidos)
        add_row("Email:", self.ed_email)
        add_row("Rol:", self.ed_rol)
        add_row("Curso:", self.cb_curso)

        self.btn_crear = QPushButton("Crear e Inscribir")
        self.btn_crear.setObjectName("GreenButton")
        self.btn_crear.clicked.connect(self.create_and_enrol)

        btn_volver = QPushButton("Volver al panel")
        btn_volver.setObjectName("RedButton")
        btn_volver.clicked.connect(self.back.emit)

        layout_contenedor.addSpacing(8)

        fila_botones = QHBoxLayout()
        fila_botones.setSpacing(18)
        fila_botones.addStretch(1)
        fila_botones.addWidget(self.btn_crear)
        fila_botones.addStretch(1)
        layout_contenedor.addLayout(fila_botones)

        layout_contenedor.addWidget(btn_volver, alignment=Qt.AlignCenter)

        self._recargar_config_y_rol()

    def set_session(self, session: Session, client: Optional[MoodleClient] = None):
        """Inyecta sesión (router) y carga cursos."""
        self._session = session
        self._client = client if client is not None else MoodleClient(session.base_url, session.token)
        self._recargar_config_y_rol()
        self.load_courses()

    def _recargar_config_y_rol(self):
        """Carga config y fija rol en UI."""
        try:
            self._cfg = load_locked_config()
        except Exception as e:
            self._cfg = {}
            self._mostrar_aviso("Config", str(e))
        self.ed_rol.setText(_nombre_rol(ROLEID_ESTUDIANTE_PRESENCIAL))

    def load_courses(self):
        """Carga cursos (admin si existe, si no cursos del usuario)."""
        try:
            self.cb_curso.clear()

            if not self._client or not self._session:
                return

            admin_token = (self._cfg.get("admin_token") or "").strip()

            cursos: List[Dict[str, Any]] = []
            if admin_token:
                try:
                    cursos = self._client.call("core_course_get_courses", {}, token=admin_token)
                except Exception:
                    cursos = []

            if not cursos:
                cursos = self._client.get_user_courses(self._session.userid)

            for c in cursos:
                cid = c.get("id")
                nombre = c.get("fullname") or c.get("shortname") or str(cid)
                if cid is None:
                    continue
                self.cb_curso.addItem(str(nombre), int(cid))

        except Exception:
            self._mostrar_error("Error", "No se pudieron cargar los cursos.", traceback.format_exc())

    def create_and_enrol(self):
        """
        1) valida sesión y admin_token
        2) valida campos
        3) crea usuario si no existe
        4) matricula con rol 11
        """
        try:
            if not self._client or not self._session:
                raise RuntimeError("No hay sesión activa.")

            admin_token = (self._cfg.get("admin_token") or "").strip()
            if not admin_token:
                raise RuntimeError(
                    "No hay token admin configurado para crear usuarios.\n\n"
                    "Añade 'admin_token' en config/config.json."
                )

            roleid = ROLEID_ESTUDIANTE_PRESENCIAL
            courseid = self.cb_curso.currentData()
            if not courseid:
                raise RuntimeError("Selecciona un curso.")

            username = (self.ed_usuario.text() or "").strip().lower()
            password = (self.ed_password.text() or "").strip()
            firstname = (self.ed_nombre.text() or "").strip()
            lastname = (self.ed_apellidos.text() or "").strip()
            email = (self.ed_email.text() or "").strip()

            if not username:
                raise RuntimeError("El usuario es obligatorio.")
            if " " in username:
                raise RuntimeError("El usuario no puede contener espacios.")
            if not firstname:
                raise RuntimeError("El nombre es obligatorio.")
            if not lastname:
                raise RuntimeError("Los apellidos son obligatorios.")
            if not email or "@" not in email or " " in email:
                raise RuntimeError("Email inválido.")

            existente = self._client.get_user_by_username(username, token=admin_token)
            if existente:
                userid = int(existente["id"])
            else:
                if not password:
                    raise RuntimeError("La contraseña es obligatoria si el usuario es nuevo.")
                userid = self._client.create_user_with_admin(
                    admin_token=admin_token,
                    username=username,
                    password=password,
                    firstname=firstname,
                    lastname=lastname,
                    email=email,
                )

            self._client.enrol_manual(int(courseid), int(userid), int(roleid), admin_token=admin_token)

            self._mostrar_info(
                "OK",
                f"Usuario listo.\n\nUsuario: {username}\nCurso: {self.cb_curso.currentText()}\nRol: {_nombre_rol(roleid)}",
            )
            self.ed_password.clear()

        except Exception as e:
            self._mostrar_error("Error", str(e), traceback.format_exc())

    def _mostrar_info(self, title: str, msg: str):
        QMessageBox.information(self, title, msg)

    def _mostrar_aviso(self, title: str, msg: str):
        QMessageBox.warning(self, title, msg)

    def _mostrar_error(self, title: str, msg: str, details: str = ""):
        box = QMessageBox(QMessageBox.Critical, title, msg)
        if details:
            box.setDetailedText(details)
        box.exec()
