"""
Cliente REST para Moodle (Moon Academy)

Este módulo centraliza TODA la comunicación con Moodle mediante
la API REST oficial.

Incluye:
- Login y token
- Llamadas REST genéricas
- site_info
- Cursos/usuarios
- Lectura de calificaciones
- Escritura de calificaciones (core_grades_update_grades)
- Admin: crear usuarios, matricular

IMPORTANTE (guardar notas):
- Moodle exige grades[0][studentid]
- activityid NO siempre es iteminstance: en muchos Moodles es cmid/coursemoduleid
  -> Por eso probamos varios candidatos (como en tu fichero ORIGINAL).
"""

import math
import requests
from typing import Any, Dict, List, Optional, Tuple


# =========================================================
# Helper: obtener token sin crear cliente manualmente
# =========================================================
def login_get_token(
    base_url: str,
    username: str,
    password: str,
    service: str,
    timeout: int = 25,
) -> str:
    cliente = MoodleClient(
        base_url=base_url,
        token="",
        service=service,
        timeout=timeout,
    )
    return cliente.login_get_token(username=username, password=password, service=service)


class MoodleClient:
    """
    Cliente REST de Moodle sin plugin local.
    """

    def __init__(
        self,
        base_url: str,
        token: str = "",
        service: str = "",
        timeout: int = 25,
    ):
        self.base_url = (base_url or "").rstrip("/")
        self.token = (token or "").strip()
        self.service = (service or "").strip()
        self.timeout = timeout

        # Caché de gradeitems: (courseid, userid, gradeitemid) -> gradeitem dict
        self._cache_gradeitems: Dict[Tuple[int, int, int], Dict[str, Any]] = {}

    # =====================================================
    # URLs internas
    # =====================================================
    def _url_server(self) -> str:
        return f"{self.base_url}/webservice/rest/server.php"

    def _url_token(self) -> str:
        return f"{self.base_url}/login/token.php"

    # =====================================================
    # Helpers HTTP + errores
    # =====================================================
    def _lanza_error_moodle(self, data: Any) -> None:
        """
        Moodle puede devolver error dentro del JSON aunque HTTP=200.
        """
        if isinstance(data, dict) and (data.get("errorcode") or data.get("exception")):
            codigo = data.get("errorcode") or data.get("exception") or "moodle_error"
            mensaje = data.get("message") or ""
            debug = data.get("debuginfo") or ""
            if debug:
                raise RuntimeError(f"{codigo}: {mensaje}\n{debug}")
            raise RuntimeError(f"{codigo}: {mensaje}")

    def _post(self, payload: Dict[str, Any]) -> Any:
        r = requests.post(self._url_server(), data=payload, timeout=self.timeout)
        r.raise_for_status()
        data = r.json()
        self._lanza_error_moodle(data)
        return data

    def call(
        self,
        wsfunction: str,
        params: Optional[Dict[str, Any]] = None,
        token: Optional[str] = None,
    ) -> Any:
        """
        Llamada genérica a cualquier función REST de Moodle.
        """
        token_uso = (token or self.token or "").strip()
        if not token_uso:
            raise RuntimeError("No hay token configurado para llamar a Moodle.")

        payload: Dict[str, Any] = {
            "wstoken": token_uso,
            "wsfunction": wsfunction,
            "moodlewsrestformat": "json",
        }
        if params:
            payload.update(params)

        return self._post(payload)

    # =====================================================
    # LOGIN / INFO
    # =====================================================
    def login_get_token(self, username: str, password: str, service: Optional[str] = None) -> str:
        servicio = (service or self.service or "").strip()
        if not servicio:
            raise RuntimeError("Falta 'service' para pedir token.")

        payload = {"username": username, "password": password, "service": servicio}
        r = requests.post(self._url_token(), data=payload, timeout=self.timeout)
        r.raise_for_status()
        data = r.json()
        self._lanza_error_moodle(data)

        tok = (data.get("token") or "").strip()
        if not tok:
            raise RuntimeError(f"Respuesta inesperada obteniendo token: {data}")
        return tok

    def site_info(self) -> Dict[str, Any]:
        """
        Info del sitio + usuario asociado al token.
        """
        return self.call("core_webservice_get_site_info", {})

    def can_read_participants_in_any_course(self, userid: int) -> bool:
        """
        Heurística: intenta leer participantes en alguno de sus cursos.
        """
        try:
            courses = self.list_my_courses(int(userid))
        except Exception:
            return False

        for c in (courses or [])[:5]:
            cid = c.get("id")
            if not cid:
                continue
            try:
                _ = self.get_course_users(int(cid))
                return True
            except Exception:
                continue
        return False

    # =====================================================
    # CURSOS / USUARIOS
    # =====================================================
    def get_user_courses(self, userid: int) -> List[Dict[str, Any]]:
        return self.call("core_enrol_get_users_courses", {"userid": int(userid)})

    def list_my_courses(self, userid: int) -> List[Dict[str, Any]]:
        return self.get_user_courses(userid)

    def get_course_users(self, courseid: int) -> List[Dict[str, Any]]:
        return self.call("core_enrol_get_enrolled_users", {"courseid": int(courseid)})

    def list_course_users(self, courseid: int) -> List[Dict[str, Any]]:
        return self.get_course_users(courseid)

    # =====================================================
    # NOTAS (leer)
    # =====================================================
    def get_user_grades(self, courseid: int, userid: int) -> List[Dict[str, Any]]:
        res = self.call(
            "gradereport_user_get_grade_items",
            {"courseid": int(courseid), "userid": int(userid)},
        )
        try:
            return res["usergrades"][0]["gradeitems"]
        except Exception:
            raise RuntimeError(f"Respuesta inesperada leyendo calificaciones: {res}")

    def get_grade_items(self, courseid: int, userid: int) -> Dict[str, Any]:
        courseid = int(courseid)
        userid = int(userid)

        items = self.get_user_grades(courseid, userid)

        # Cacheamos por (courseid, userid, gradeitemid)
        for it in items or []:
            try:
                gid = int(it.get("id"))
                self._cache_gradeitems[(courseid, userid, gid)] = it
            except Exception:
                continue

        # Total del curso
        course_total = None
        for it in items or []:
            if it.get("itemtype") == "course":
                course_total = it.get("graderaw")
                break

        return {"items": items, "course_total": course_total}

    # =====================================================
    # NOTAS (guardar)  ✅ (misma lógica que el ORIGINAL)
    # =====================================================
    def _a_float(self, v: Any) -> float:
        """
        Convierte a float aceptando '6,5'.
        """
        if isinstance(v, str):
            v = v.strip().replace(",", ".")
        g = float(v)
        if math.isnan(g) or math.isinf(g):
            raise RuntimeError("Nota inválida.")
        return g

    def _normalizar_nota(self, gi: Dict[str, Any], grade_in: Any) -> Any:
        """
        Normaliza la nota para el gradeitem:
        - clamp min/max si existen
        - escalas: gradetype==2 o scaleid>0 -> int
        - si es entero lógico -> int
        """
        g = self._a_float(grade_in)

        # clamp
        try:
            gmin = gi.get("grademin")
            gmax = gi.get("grademax")
            if gmin is not None:
                g = max(g, float(gmin))
            if gmax is not None and float(gmax) > 0:
                g = min(g, float(gmax))
        except Exception:
            pass

        # escalas
        try:
            gradetype = int(gi.get("gradetype") or 0)
            scaleid = int(gi.get("scaleid") or 0)
            if gradetype == 2 or scaleid > 0:
                return int(round(g))
        except Exception:
            pass

        if float(g).is_integer():
            return int(g)

        return float(g)

    def _formatear_nota(self, grade_value: Any) -> str:
        """
        Formatea:
        - 6.0 -> "6"
        - 6.5000000000 -> "6.5"
        - acepta coma
        """
        if isinstance(grade_value, int):
            return str(grade_value)

        if isinstance(grade_value, float):
            if grade_value.is_integer():
                return str(int(grade_value))
            s = f"{grade_value:.10f}".rstrip("0").rstrip(".")
            return s if s else "0"

        s = str(grade_value).strip()
        return s.replace(",", ".")

    def _actualizar_nota_core(
        self,
        courseid: int,
        component: str,
        activityid: int,
        itemnumber: int,
        studentid: int,
        grade_value_str: str,
    ) -> Any:
        """
        Ejecuta core_grades_update_grades con los parámetros ya formateados.
        """
        return self.call(
            "core_grades_update_grades",
            {
                "source": "moon_academy",
                "courseid": int(courseid),
                "component": component,
                "activityid": int(activityid),
                "itemnumber": int(itemnumber),
                "grades[0][studentid]": int(studentid),
                "grades[0][grade]": grade_value_str,
            },
        )

    def _candidatos_activityid(self, gi: Dict[str, Any]) -> List[int]:
        """
        En tu Moodle activityid válido NO siempre es iteminstance.
        Probamos los candidatos típicos (como en el ORIGINAL).
        """
        keys = ["iteminstance", "cmid", "coursemoduleid", "course_module_id", "cmidnumber"]
        vistos = set()
        out: List[int] = []

        for k in keys:
            v = gi.get(k)
            try:
                if v is None:
                    continue
                iv = int(v)
                if iv > 0 and iv not in vistos:
                    vistos.add(iv)
                    out.append(iv)
            except Exception:
                continue

        return out

    def academy_set_grade(self, courseid: int, gradeitemid: int, userid: int, grade: float) -> Any:
        """
        Guarda la nota de un gradeitem para un alumno.

        Pasos:
        1) Obtener gradeitem (caché o recarga)
        2) Validar que es itemtype='mod'
        3) Preparar component, itemnumber
        4) Normalizar/formatear nota
        5) Probar activityid candidates hasta que Moodle acepte
        """
        courseid = int(courseid)
        gradeitemid = int(gradeitemid)
        userid = int(userid)

        gi = self._cache_gradeitems.get((courseid, userid, gradeitemid))
        if not gi:
            _ = self.get_grade_items(courseid, userid)
            gi = self._cache_gradeitems.get((courseid, userid, gradeitemid))

        if not gi:
            raise RuntimeError("No se encontró el gradeitem. Pulsa 'Cargar calificaciones' y reintenta.")

        if gi.get("itemtype") != "mod":
            raise RuntimeError("Solo se pueden modificar actividades (itemtype='mod').")

        itemmodule = gi.get("itemmodule")
        itemnumber = gi.get("itemnumber", 0)
        if not itemmodule:
            raise RuntimeError("Gradeitem sin itemmodule (no se puede actualizar).")

        component = f"mod_{itemmodule}"
        itemnumber = int(itemnumber) if itemnumber is not None else 0

        grade_norm = self._normalizar_nota(gi, grade)
        grade_str = self._formatear_nota(grade_norm)

        candidates = self._candidatos_activityid(gi)
        if not candidates:
            info = (
                f"DEBUG gradeitem:\n"
                f"  gradeitemid={gradeitemid}\n"
                f"  component={component}\n"
                f"  itemnumber={itemnumber}\n"
                f"  iteminstance={gi.get('iteminstance')} cmid={gi.get('cmid')} coursemoduleid={gi.get('coursemoduleid')}\n"
                f"  gradetype={gi.get('gradetype')} scaleid={gi.get('scaleid')}\n"
                f"  min={gi.get('grademin')} max={gi.get('grademax')}\n"
                f"  value_sent={grade_str}\n"
            )
            raise RuntimeError("No hay activityid candidato (iteminstance/cmid/...) en el gradeitem.\n" + info)

        last_err: Optional[Exception] = None
        for actid in candidates:
            try:
                return self._actualizar_nota_core(courseid, component, actid, itemnumber, userid, grade_str)
            except RuntimeError as e:
                emsg = str(e).lower()
                # Si el id no corresponde al módulo del curso, Moodle devuelve esto:
                if ("invalidparameter" in emsg) or ("invalidcoursemodule" in emsg):
                    last_err = e
                    continue
                raise

        info = (
            f"{last_err}\n\nDEBUG gradeitem:\n"
            f"  gradeitemid={gradeitemid}\n"
            f"  component={component}\n"
            f"  candidates(activityid)={candidates}\n"
            f"  itemnumber={itemnumber}\n"
            f"  iteminstance={gi.get('iteminstance')} cmid={gi.get('cmid')} coursemoduleid={gi.get('coursemoduleid')}\n"
            f"  gradetype={gi.get('gradetype')} scaleid={gi.get('scaleid')}\n"
            f"  min={gi.get('grademin')} max={gi.get('grademax')}\n"
            f"  value_sent={grade_str}\n"
        )
        raise RuntimeError(info)

    # =====================================================
    # BUSCAR USUARIO
    # =====================================================
    def get_user_by_username(self, username: str, token: Optional[str] = None) -> Optional[Dict[str, Any]]:
        username = (username or "").strip()
        if not username:
            return None

        data = self.call(
            "core_user_get_users",
            {"criteria[0][key]": "username", "criteria[0][value]": username},
            token=token,
        )
        users = data.get("users", []) if isinstance(data, dict) else []
        return users[0] if users else None

    # =====================================================
    # ADMIN: crear usuario + matricular
    # =====================================================
    def create_user_with_admin(
        self,
        admin_token: str,
        username: str,
        password: str,
        firstname: str,
        lastname: str,
        email: str,
    ) -> int:
        admin_token = (admin_token or "").strip()
        if not admin_token:
            raise RuntimeError("No hay token admin configurado.")

        payload = {
            "wstoken": admin_token,
            "wsfunction": "core_user_create_users",
            "moodlewsrestformat": "json",
            "users[0][username]": username,
            "users[0][password]": password,
            "users[0][firstname]": firstname,
            "users[0][lastname]": lastname,
            "users[0][email]": email,
            "users[0][auth]": "manual",
        }

        data = self._post(payload)
        if not isinstance(data, list) or not data or "id" not in data[0]:
            raise RuntimeError(f"Respuesta inesperada creando usuario: {data}")
        return int(data[0]["id"])

    def enrol_manual(self, courseid: int, userid: int, roleid: int, admin_token: Optional[str] = None) -> None:
        token = (admin_token or self.token or "").strip()
        if not token:
            raise RuntimeError("No hay token admin para matricular.")

        payload = {
            "wstoken": token,
            "wsfunction": "enrol_manual_enrol_users",
            "moodlewsrestformat": "json",
            "enrolments[0][courseid]": int(courseid),
            "enrolments[0][userid]": int(userid),
            "enrolments[0][roleid]": int(roleid),
        }
        self._post(payload)
