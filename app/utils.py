import os
import sys
import json
from typing import Dict, Any

LOG_FILE = "moonacademy.log"


def log_line(mensaje: str) -> None:
    """
    Escribe una línea en el fichero de log.
    Nunca debe romper la app.
    """
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(mensaje + "\n")
    except Exception:
        pass


def resource_path(rel_path: str) -> str:
    """
    Devuelve la ruta absoluta a un recurso.
    Compatible con PyInstaller.
    """
    base = getattr(sys, "_MEIPASS", os.path.abspath("."))
    return os.path.join(base, rel_path)


def normalize_base_url(url: str) -> str:
    """
    Limpia la URL base de Moodle.
    """
    url = (url or "").strip()
    for sufijo in ("/login/token.php", "/webservice/rest/server.php"):
        if url.endswith(sufijo):
            url = url[:-len(sufijo)]
    return url.rstrip("/")


def load_locked_config() -> Dict[str, Any]:
    """
    Carga y valida config/config.json.
    """
    ruta = resource_path(os.path.join("config", "config.json"))
    if not os.path.exists(ruta):
        raise RuntimeError("No existe el fichero de configuración.")

    with open(ruta, "r", encoding="utf-8") as f:
        data = json.load(f)

    base_url = normalize_base_url(data.get("base_url", ""))
    service = data.get("service", "").strip()

    if not base_url or not service:
        raise RuntimeError("Config inválida.")

    return {
        "base_url": base_url,
        "service": service,
        "admin_service": data.get("admin_service", service),
        "admin_token": data.get("admin_token", ""),
        "default_roleid": int(data.get("default_roleid", 5)),
    }
