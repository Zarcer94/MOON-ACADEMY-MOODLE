import traceback
from typing import Optional, Dict, Any, List

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QLineEdit, QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox, QInputDialog
)

from app.moodle_client import MoodleClient
from app.session import Session


class CoursesScreen(QWidget):
    """
    Gestión de cursos y calificaciones de un alumno.
    """
    back = Signal()
    open_student_picker = Signal(int)  # courseid

    def __init__(self):
        super().__init__()

        self._session: Optional[Session] = None
        self._client: Optional[MoodleClient] = None

        self._alumno_userid: Optional[int] = None
        self._alumno_username: str = ""
        self._alumno_nombre: str = ""

        self._filas_gradeitems: List[Dict[str, Any]] = []

        layout_raiz = QVBoxLayout(self)
        layout_raiz.setContentsMargins(24, 24, 24, 24)
        layout_raiz.setSpacing(12)

        titulo = QLabel("Gestión de mis cursos y calificaciones")
        titulo.setStyleSheet("font-size: 18px; font-weight: 900;")
        layout_raiz.addWidget(titulo)

        barra = QHBoxLayout()

        self.input_alumno = QLineEdit()
        self.input_alumno.setPlaceholderText("Selecciona un alumno…")
        self.input_alumno.setReadOnly(True)

        self.cb_curso = QComboBox()
        self.cb_curso.setObjectName("CourseCombo")

        self.btn_seleccionar_alumno = QPushButton("Seleccionar alumno…")
        self.btn_refrescar_cursos = QPushButton("Recargar curso")
        self.btn_cargar_notas = QPushButton("Cargar calificaciones")
        self.btn_volver = QPushButton("Volver al panel")

        self.btn_cargar_notas.setObjectName("GreenButton")
        self.btn_volver.setObjectName("RedButton")

        barra.addWidget(QLabel("Alumno:"))
        barra.addWidget(self.input_alumno, 2)
        barra.addWidget(self.btn_seleccionar_alumno)

        barra.addWidget(QLabel("Curso:"))
        barra.addWidget(self.cb_curso, 3)
        barra.addWidget(self.btn_refrescar_cursos)
        barra.addWidget(self.btn_cargar_notas)
        barra.addWidget(self.btn_volver)

        layout_raiz.addLayout(barra)

        self.tabla = QTableWidget(0, 4)
        self.tabla.setHorizontalHeaderLabels(["Actividad", "Nota Max", "Nota actual", "Nueva nota"])
        self.tabla.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tabla.setSelectionBehavior(QTableWidget.SelectRows)
        self.tabla.setSelectionMode(QTableWidget.SingleSelection)

        self.tabla.setShowGrid(True)
        self.tabla.setGridStyle(Qt.SolidLine)
        self.tabla.verticalHeader().setDefaultSectionSize(44)
        self.tabla.horizontalHeader().setFixedHeight(44)

        header = self.tabla.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        self.tabla.setColumnWidth(1, 110)
        self.tabla.setColumnWidth(2, 130)
        self.tabla.setColumnWidth(3, 180)

        layout_raiz.addWidget(self.tabla, 1)

        self.lbl_total = QLabel("Total del curso: -")
        layout_raiz.addWidget(self.lbl_total)

        # Conexiones
        self.btn_volver.clicked.connect(self.back.emit)
        self.btn_cargar_notas.clicked.connect(self.load_grades)
        self.btn_seleccionar_alumno.clicked.connect(self._emitir_selector_alumno)
        self.btn_refrescar_cursos.clicked.connect(self.refresh_courses)

    def set_session(self, session: Session):
        self._session = session
        self._client = MoodleClient(session.base_url, session.token)
        self.refresh_courses()

    def set_selected_student(self, userid: int, username: str, fullname: str):
        self._alumno_userid = int(userid)
        self._alumno_username = username or ""
        self._alumno_nombre = fullname or username or str(userid)
        self.input_alumno.setText(self._alumno_nombre)

    def _mostrar_error(self, titulo: str, msg: str, detalles: str = ""):
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Critical)
        box.setWindowTitle(titulo)
        box.setText(msg)
        if detalles:
            box.setDetailedText(detalles)
        box.setMinimumWidth(780)
        box.exec()

    def refresh_courses(self):
        try:
            if not self._client or not self._session:
                raise RuntimeError("No hay sesión.")

            curso_anterior = self.cb_curso.currentData()

            cursos = self._client.list_my_courses(self._session.userid)
            self.cb_curso.clear()

            for c in cursos:
                cid = c.get("id")
                nombre = (c.get("fullname") or f"Curso {cid}").strip()
                if cid:
                    self.cb_curso.addItem(nombre, int(cid))

            if curso_anterior:
                for i in range(self.cb_curso.count()):
                    if self.cb_curso.itemData(i) == curso_anterior:
                        self.cb_curso.setCurrentIndex(i)
                        break

        except Exception:
            self._mostrar_error("Error", "No se pudieron cargar los cursos.", traceback.format_exc())

    def _emitir_selector_alumno(self):
        cid = self.cb_curso.currentData()
        self.open_student_picker.emit(int(cid) if cid else 0)

    def load_grades(self):
        try:
            if not self._client:
                raise RuntimeError("No hay sesión.")
            courseid = self.cb_curso.currentData()
            if not courseid:
                raise RuntimeError("Selecciona un curso.")
            courseid = int(courseid)

            if not self._alumno_userid:
                raise RuntimeError("Selecciona un alumno.")

            data = self._client.get_grade_items(courseid, int(self._alumno_userid))
            items = data.get("items", [])
            total = data.get("course_total", None)
            self.lbl_total.setText(f"Total del curso: {total if total is not None else '-'}")

            filas: List[Dict[str, Any]] = []
            for it in items:
                if it.get("itemtype") == "course":
                    continue
                nombre = (it.get("itemname") or "").strip()
                grademax = it.get("grademax", None)
                if not nombre:
                    continue
                if grademax in (None, "", 0, 0.0):
                    continue
                filas.append(it)

            self._filas_gradeitems = filas
            self.tabla.setRowCount(len(filas))

            for r, it in enumerate(filas):
                self._poner_celda_texto(r, 0, str(it.get("itemname", "")))
                self._poner_celda_texto(r, 1, str(it.get("grademax", "")))
                self._poner_celda_texto(r, 2, str(it.get("graderaw", "")))

                boton = QPushButton("Modificar")
                boton.setCursor(Qt.PointingHandCursor)
                boton.setFixedHeight(37)
                boton.setFixedWidth(130)
                boton.clicked.connect(lambda _=False, rr=r: self.modify_grade(rr))

                contenedor = QWidget()
                lay = QHBoxLayout(contenedor)
                lay.setContentsMargins(0, 0, 0, 0)
                lay.setAlignment(Qt.AlignCenter)
                lay.addWidget(boton)
                self.tabla.setCellWidget(r, 3, contenedor)

        except Exception:
            self._mostrar_error("Error", "No se pudieron cargar las calificaciones.", traceback.format_exc())

    def _poner_celda_texto(self, fila: int, col: int, texto: str):
        item = QTableWidgetItem(texto)
        item.setFlags(item.flags() & ~Qt.ItemIsSelectable)
        self.tabla.setItem(fila, col, item)

    def modify_grade(self, row: int):
        try:
            if not self._client:
                raise RuntimeError("No hay sesión.")
            if not self._alumno_userid:
                raise RuntimeError("No hay alumno seleccionado.")

            courseid = self.cb_curso.currentData()
            if not courseid:
                raise RuntimeError("Selecciona un curso.")
            courseid = int(courseid)

            if row < 0 or row >= len(self._filas_gradeitems):
                raise RuntimeError("Fila inválida.")

            it = self._filas_gradeitems[row]
            gradeitemid = int(it.get("id"))

            try:
                vmax = float(it.get("grademax", 0) or 0)
            except Exception:
                vmax = 999999.0

            current = it.get("graderaw", None)
            try:
                vcur = float(current) if current not in (None, "", "-") else 0.0
            except Exception:
                vcur = 0.0

            val, ok = QInputDialog.getDouble(
                self,
                "Modificar nota",
                f"Introduce la nueva nota (0 - {vmax:g}):",
                vcur,
                0.0,
                vmax,
                2
            )
            if not ok:
                return

            self._client.academy_set_grade(courseid, gradeitemid, int(self._alumno_userid), float(val))
            QMessageBox.information(self, "OK", "Nota guardada.")

            self.load_grades()
            if self.tabla.rowCount() > row:
                self.tabla.selectRow(row)

        except Exception:
            self._mostrar_error("Error", "No se pudo modificar la nota.", traceback.format_exc())

    def save_selected_grade(self):
        row = self.tabla.currentRow()
        if row < 0:
            QMessageBox.information(self, "Info", "Selecciona una fila para modificar.")
            return
        self.modify_grade(row)

    def save_all_changed(self):
        pass
