"""
Rate limiting simple en memoria para proteger el login de fuerza bruta.

Lleva la cuenta de intentos FALLIDOS por clave (IP + correo) dentro de una
ventana deslizante. Si se superan los intentos permitidos, se bloquea hasta
que la ventana expire.

Nota de alcance: es un limitador en memoria de proceso, suficiente para un
despliegue de un solo worker o como primera línea de defensa. Para varios
procesos/instancias conviene respaldarlo en Redis; la interfaz (`check`,
`register_failure`, `reset`) está pensada para poder sustituir la
implementación sin tocar el resto del código.
"""

import threading
import time
from collections import deque

from app.core.config import settings


class LoginRateLimiter:
    """Limita intentos de login fallidos por clave dentro de una ventana."""

    def __init__(self, max_attempts: int, window_seconds: int) -> None:
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        # clave -> deque de timestamps de intentos fallidos.
        self._fails: dict[str, deque] = {}
        self._lock = threading.Lock()

    def _purge(self, dq: deque, now: float) -> None:
        """Elimina los intentos que ya quedaron fuera de la ventana."""
        limite = now - self.window_seconds
        while dq and dq[0] < limite:
            dq.popleft()

    def check(self, key: str) -> tuple[bool, int]:
        """
        Comprueba si la clave puede intentar login.

        Returns:
            (permitido, segundos_para_reintentar). Si `permitido` es True, el
            segundo valor es 0.
        """
        now = time.monotonic()
        with self._lock:
            dq = self._fails.get(key)
            if not dq:
                return True, 0
            self._purge(dq, now)
            if len(dq) < self.max_attempts:
                return True, 0
            # Bloqueado: el reintento es posible cuando expire el más antiguo.
            retry_after = int(self.window_seconds - (now - dq[0])) + 1
            return False, max(retry_after, 1)

    def register_failure(self, key: str) -> None:
        """Registra un intento fallido para la clave."""
        now = time.monotonic()
        with self._lock:
            dq = self._fails.setdefault(key, deque())
            self._purge(dq, now)
            dq.append(now)

    def reset(self, key: str) -> None:
        """Limpia los intentos de la clave (tras un login exitoso)."""
        with self._lock:
            self._fails.pop(key, None)


# Instancia única compartida, configurada desde settings.
login_rate_limiter = LoginRateLimiter(
    max_attempts=settings.LOGIN_MAX_ATTEMPTS,
    window_seconds=settings.LOGIN_WINDOW_SECONDS,
)
