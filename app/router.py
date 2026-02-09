import os
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QMainWindow, QStackedWidget

from app.utils import resource_path, load_locked_config
from app.session import Session

from app.screens.login_screen import LoginScreen
from app.screens.home_screen import HomeScreen
from app.screens.users_screen import UsersScreen
from app.screens.courses_screen import CoursesScreen
from app.screens.select_student_screen import SelectStudentScreen
from app.screens.students_screen import StudentsScreen


class MainWindow(QMainWindow):
    """
    Ventana principal de la aplicación.

    Se encarga de:
    - Crear pantallas
    - Gestionar navegación
    - Mantener la sesión activa
    """

    def __init__(self):
        super().__init__()

        self.setWindowTitle("Moon Academy - Gestión Académica")
        self.setMinimumSize(1100, 720)

        # ───────── Estilos e icono ─────────
        qss = resource_path(os.path.join("styles", "styles.qss"))
        if os.path.exists(qss):
            self.setStyleSheet(open(qss, encoding="utf-8").read())

        icono = resource_path(os.path.join("styles", "logo.png"))
        if os.path.exists(icono):
            self.setWindowIcon(QIcon(icono))

        # ───────── Configuración y sesión ─────────
        self.cfg = load_locked_config()
        self.session: Session | None = None

        # ───────── Stack de pantallas ─────────
        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        # ───────── Pantallas ─────────
        self.login = LoginScreen(self.cfg)
        self.home = HomeScreen()
        self.users = UsersScreen()
        self.courses = CoursesScreen()
        self.select_student = SelectStudentScreen()
        self.students = StudentsScreen()

        for pantalla in (
            self.login, self.home, self.users,
            self.courses, self.select_student, self.students
        ):
            self.stack.addWidget(pantalla)

        # ───────── Señales ─────────
        self.login.login_success.connect(self.on_login_success)
        self.home.go_users.connect(lambda: self.stack.setCurrentWidget(self.users))
        self.home.go_courses.connect(lambda: self.stack.setCurrentWidget(self.courses))
        self.home.go_students.connect(lambda: self.stack.setCurrentWidget(self.students))
        self.home.logout.connect(self.do_logout)

        self.users.back.connect(lambda: self.stack.setCurrentWidget(self.home))
        self.courses.back.connect(lambda: self.stack.setCurrentWidget(self.home))
        self.students.back.connect(lambda: self.stack.setCurrentWidget(self.home))
        self.select_student.back.connect(lambda: self.stack.setCurrentWidget(self.courses))

        self.courses.open_student_picker.connect(self.go_select_student)
        self.select_student.student_selected.connect(self.on_student_selected)

        self.stack.setCurrentWidget(self.login)

    def on_login_success(self, session: Session):
        """Login correcto: guardar sesión y preparar pantallas."""
        self.session = session
        self.home.set_welcome_name(session.firstname)

        for pantalla in (self.users, self.courses, self.select_student, self.students):
            pantalla.set_session(session)

        self.stack.setCurrentWidget(self.home)

    def go_select_student(self, courseid: int):
        """Abre selector de alumnos."""
        self.select_student.set_course_preselected(courseid)
        self.stack.setCurrentWidget(self.select_student)

    def on_student_selected(self, userid: int, username: str, fullname: str):
        """Alumno elegido: volver a cursos."""
        self.courses.set_selected_student(userid, username, fullname)
        self.stack.setCurrentWidget(self.courses)

    def do_logout(self):
        """Cerrar sesión."""
        self.session = None
        self.stack.setCurrentWidget(self.login)
