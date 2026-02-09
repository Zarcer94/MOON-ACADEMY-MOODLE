import traceback
from typing import Optional, List, Dict, Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QComboBox, QTableWidget,
    QTableWidgetItem, QHeaderView, QMessageBox
)

from app.moodle_client import MoodleClient
from app.session import Session


ROLEID_ESTUDIANTE_PRESENCIAL = 11


class StudentsScreen(QWidget):
    """
    Lista de alumnos por curso (filtrando rol 11).
    """
    back = Signal()

    def __init__(self):
        super().__init__()

        self._session: Optional[Session] = None
        self._client: Optional[MoodleClient] = None

        layout_raiz = QVBoxLayout(self)
        layout_raiz.setContentsMargins(24, 24, 24, 24)
        layout_raiz.setSpacing(12)

        titulo = QLabel("Alumnos por curso")
        titulo.setStyleSheet("font-size: 18px; font-weight: 900;")
        layout_raiz.addWidget(titulo)

        barra = QHBoxLayout()

        self.cb_curso = QComboBox()

        self.btn_refrescar = QPushButton("Refrescar cursos")

        self.btn_cargar = QPushButton("Cargar alumnos")
        self.btn_cargar.setObjectName("GreenButton")

        self.btn_volver = QPushButton("Volver al panel")
        self.btn_volver.setObjectName("RedButton")

        barra.addWidget(QLabel("Curso:"))
        barra.addWidget(self.cb_curso, 2)
        barra.addWidget(self.btn_refrescar)
        barra.addWidget(self.btn_cargar)
        barra.addStretch(1)
        barra.addWidget(self.btn_volver)
        layout_raiz.addLayout(barra)

        self.tabla = QTableWidget(0, 4)
        self.tabla.setHorizontalHeaderLabels(["Usuario", "Nombre", "Apellidos", "Email"])
        self.tabla.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tabla.setEditTriggers(QTableWidget.NoEditTriggers)
        layout_raiz.addWidget(self.tabla, 1)

        self.lbl_status = QLabel("")
        layout_raiz.addWidget(self.lbl_status)

        self.btn_volver.clicked.connect(self.back.emit)
        self.btn_refrescar.clicked.connect(self.refresh_courses)
        self.btn_cargar.clicked.connect(self.load_students)

    def set_session(self, session: Session):
        self._session = session
        self._client = MoodleClient(session.base_url, session.token)
        self.refresh_courses()

    def _mostrar_error(self, title: str, msg: str, details: str = ""):
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Critical)
        box.setWindowTitle(title)
        box.setText(msg)
        if details:
            box.setDetailedText(details)
        box.setMinimumWidth(680)
        box.exec()

    def _tiene_rol_11(self, roles: List[Dict[str, Any]]) -> bool:
        for r in roles or []:
            rid = r.get("roleid", r.get("id"))
            try:
                if int(rid) == ROLEID_ESTUDIANTE_PRESENCIAL:
                    return True
            except Exception:
                pass
        return False

    def refresh_courses(self):
        try:
            if not self._client or not self._session:
                raise RuntimeError("No hay sesión.")

            cursos = self._client.list_my_courses(self._session.userid)

            self.cb_curso.clear()
            for c in cursos:
                cid = c.get("id")
                nombre = (c.get("fullname") or f"Curso {cid}").strip()
                if cid:
                    self.cb_curso.addItem(nombre, int(cid))

            self.lbl_status.setText(f"Cursos cargados: {len(cursos)}")

        except Exception:
            self._mostrar_error("Error", "No se pudieron cargar los cursos.", traceback.format_exc())

    def load_students(self):
        try:
            if not self._client:
                raise RuntimeError("No hay sesión.")
            courseid = self.cb_curso.currentData()
            if not courseid:
                raise RuntimeError("Selecciona un curso.")

            usuarios = self._client.call("core_enrol_get_enrolled_users", {"courseid": int(courseid)})
            if not isinstance(usuarios, list):
                raise RuntimeError("Respuesta no válida al cargar alumnos.")

            alumnos: List[Dict[str, Any]] = []
            sin_roles = 0

            for u in usuarios:
                roles = u.get("roles", []) or []
                if roles:
                    if self._tiene_rol_11(roles):
                        alumnos.append(u)
                else:
                    sin_roles += 1

            self.tabla.setRowCount(len(alumnos))
            for row, u in enumerate(alumnos):
                self.tabla.setItem(row, 0, QTableWidgetItem(u.get("username", "") or ""))
                self.tabla.setItem(row, 1, QTableWidgetItem(u.get("firstname", "") or ""))
                self.tabla.setItem(row, 2, QTableWidgetItem(u.get("lastname", "") or ""))
                self.tabla.setItem(row, 3, QTableWidgetItem(u.get("email", "") or ""))

            extra = " (avisos: algunos usuarios no traen roles y no se han mostrado)" if sin_roles else ""
            self.lbl_status.setText(f"Usuarios cargados (rol 11): {len(alumnos)}{extra}")

        except Exception:
            self._mostrar_error("Error", "No se pudieron cargar los alumnos.", traceback.format_exc())
