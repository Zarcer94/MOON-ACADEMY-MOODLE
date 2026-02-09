from dataclasses import dataclass

@dataclass
class Session:
    """
    Representa la sesión activa del usuario.

    Esta clase NO tiene lógica.
    Solo transporta datos entre pantallas.
    """
    base_url: str
    token: str
    userid: int
    username: str
    firstname: str
