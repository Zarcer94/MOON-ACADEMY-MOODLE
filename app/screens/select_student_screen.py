import traceback
from typing import Optional, List, Dict, Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox
)

from app.session import Session
from app.moodle_client import MoodleClient


ROLEID_ESTUDIANTE_PRESENCIAL = 11


class SelectStudentScreen(QWidget):
    back = Signal()
    student_selected = Signal(int, str, str)

    def __init__(self):
        super().__init__()

        self._session: Optional[Session] = None
        self._client: Optional[MoodleClient] = None
        self._alumnos: List[Dict[str, Any]] = []

        layout_raiz = QVBoxLayout(self)
        layout_raiz.setContentsMargins(24, 24, 24, 24)
        layout_raiz.setSpacing(12)

        titulo = QLabel("Seleccionar alumno")
        titulo.setStyleSheet("font-size: 18px; font-weight: 900;")
        layout_raiz.addWidget(titulo)

        barra = QHBoxLayout()
        barra.setSpacing(14)

        self.cb_curso = QComboBox()
        self.cb_curso.setMinimumWidth(520)

        self.btn_cargar = QPushButton("Cargar alumnos")

        self.btn_volver = QPushButton("Volver")
        self.btn_volver.setObjectName("RedButton")  # 👈 QSS

        barra.addWidget(QLabel("Curso:"))
        barra.addWidget(self.cb_curso, 2)
        barra.addWidget(self.btn_cargar)
        barra.addStretch(1)
        barra.addWidget(self.btn_volver)
        layout_raiz.addLayout(barra)

        self.tabla = QTableWidget(0, 1)
        self.tabla.setHorizontalHeaderLabels(["Alumno"])
        self.tabla.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tabla.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tabla.setSelectionBehavior(QTableWidget.SelectRows)
        self.tabla.setSelectionMode(QTableWidget.SingleSelection)
        layout_raiz.addWidget(self.tabla, 1)

        bottom = QHBoxLayout()
        bottom.setSpacing(14)

        self.lbl_status = QLabel("Alumnos cargados: 0")

        self.btn_seleccionar = QPushButton("Seleccionar alumno")
        self.btn_seleccionar.setObjectName("GreenButton")

        bottom.addWidget(self.lbl_status)
        bottom.addStretch(1)
        bottom.addWidget(self.btn_seleccionar)
        layout_raiz.addLayout(bottom)

        self.btn_volver.clicked.connect(self.back.emit)
        self.btn_cargar.clicked.connect(self.load_students)
        self.btn_seleccionar.clicked.connect(self.select_current_student)
        self.tabla.itemDoubleClicked.connect(lambda *_: self.select_current_student())

    def set_session(self, session: Session):
        self._session = session
        self._client = MoodleClient(session.base_url, session.token)
        self.refresh_courses()

    def set_course_preselected(self, courseid: int):
        for i in range(self.cb_curso.count()):
            if self.cb_curso.itemData(i) == int(courseid):
                self.cb_curso.setCurrentIndex(i)
                break

    def refresh_courses(self):
        try:
            if not self._client or not self._session:
                return

            curso_anterior = self.cb_curso.currentData()
            cursos = self._client.list_my_courses(self._session.userid)

            self.cb_curso.clear()
            for c in cursos:
                cid = c.get("id")
                nombre = (c.get("fullname") or c.get("shortname") or f"Curso {cid}").strip()
                if cid:
                    self.cb_curso.addItem(nombre, int(cid))

            if curso_anterior:
                for i in range(self.cb_curso.count()):
                    if self.cb_curso.itemData(i) == curso_anterior:
                        self.cb_curso.setCurrentIndex(i)
                        break

        except Exception:
            self._mostrar_error("Error", "No se pudieron cargar los cursos.", traceback.format_exc())

    def _tiene_rol_11(self, roles: List[Dict[str, Any]]) -> bool:
        for r in roles or []:
            rid = r.get("roleid", r.get("id"))
            try:
                if int(rid) == ROLEID_ESTUDIANTE_PRESENCIAL:
                    return True
            except Exception:
                pass
        return False

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

            filtrados: List[Dict[str, Any]] = []
            sin_roles = 0

            for u in usuarios:
                roles = u.get("roles", []) or []
                if not roles:
                    sin_roles += 1
                    continue
                if self._tiene_rol_11(roles):
                    filtrados.append(u)

            self._alumnos = filtrados

            self.tabla.setRowCount(len(filtrados))
            for row, u in enumerate(filtrados):
                fullname = (u.get("fullname") or f"{u.get('firstname','')} {u.get('lastname','')}".strip()).strip()
                if not fullname:
                    fullname = u.get("username", "") or ""
                self.tabla.setItem(row, 0, QTableWidgetItem(fullname))

            extra = " (algunos usuarios no traen roles y no se muestran)" if sin_roles else ""
            self.lbl_status.setText(f"Alumnos cargados: {len(filtrados)}{extra}")

            if filtrados:
                self.tabla.selectRow(0)

        except Exception:
            self._mostrar_error("Error", "No se pudieron cargar los alumnos.", traceback.format_exc())

    def select_current_student(self):
        row = self.tabla.currentRow()
        if row < 0 or row >= len(self._alumnos):
            QMessageBox.information(self, "Info", "Selecciona un alumno.")
            return

        u = self._alumnos[row]
        userid = int(u.get("id"))
        username = u.get("username", "") or ""
        fullname = (u.get("fullname") or f"{u.get('firstname','')} {u.get('lastname','')}".strip()).strip()
        if not fullname:
            fullname = username or str(userid)

        self.student_selected.emit(userid, username, fullname)

    def _mostrar_error(self, title: str, msg: str, details: str = ""):
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Critical)
        box.setWindowTitle(title)
        box.setText(msg)
        if details:
            box.setDetailedText(details)
        box.setMinimumWidth(720)
        box.exec()
