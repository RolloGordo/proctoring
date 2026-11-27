"""Lo que comparten las baterías de `pruebas/`: el entorno aislado y sus personas.

Todas corren contra el **entorno aislado** de `loadtests/` (Supabase local, réplicas
de la API detrás de nginx en :8080, Redis), nunca contra producción: crean
cuentas, exámenes y señales. `preparar.py` se niega a tocar otra cosa que
Supabase local, y esto lo reutiliza.

Cada prueba pide lo que necesita (un docente, un examen, un estudiante admitido)
a estas funciones, con correos únicos por corrida, así que las pruebas no
dependen del orden ni de datos que dejó otra.
"""

from __future__ import annotations

import os
import sys
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "loadtests"))
from preparar import AUTH_LOCAL, PREGUNTAS, Firmador, crear_usuario, estado_supabase  # noqa: E402

API = os.environ.get("API_URL", "http://localhost:8080").rstrip("/")
V1 = f"{API}/api/v1"
MARCA = f"{int(time.time())}{uuid4().hex[:4]}"

_firmador: Firmador | None = None
_admin: httpx.Client | None = None


def firmador() -> Firmador:
    global _firmador
    if _firmador is None:
        _firmador = Firmador()
    return _firmador


def admin() -> httpx.Client:
    """Cliente de Auth local con la service role (solo para crear personas)."""
    global _admin
    if _admin is None:
        s = estado_supabase()
        clave = s["SERVICE_ROLE_KEY"]
        _admin = httpx.Client(
            base_url=AUTH_LOCAL,
            headers={"apikey": clave, "Authorization": f"Bearer {clave}"},
            timeout=30,
        )
    return _admin


@dataclass
class Persona:
    id: str
    email: str
    token: str
    rol: str

    @property
    def h(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"}


_contador = 0


def persona(rol: str = "student", nombre: str | None = None) -> Persona:
    """Crea una cuenta real en Auth local (el disparador crea su perfil)."""
    global _contador
    _contador += 1
    email = f"{rol}.{_contador}.{MARCA}@pruebas.test"
    uid = crear_usuario(admin(), email, nombre or f"{rol.title()} de prueba {_contador}")
    if rol == "teacher":
        admin().patch(
            "/rest/v1/profiles", params={"id": f"eq.{uid}"}, json={"role": "teacher"}
        ).raise_for_status()
    return Persona(uid, email, firmador().token(uid, email, horas=4), rol)


def cliente() -> httpx.Client:
    return httpx.Client(base_url=V1, timeout=30)


@dataclass
class Examen:
    id: str
    codigo: str
    docente: Persona
    datos: dict[str, Any]
    preguntas: list[dict[str, Any]] = field(default_factory=list)


def crear_examen(
    docente: Persona,
    *,
    preset: str = "standard",
    modules: dict[str, Any] | None = None,
    inicio: datetime | None = None,
    duracion: int = 120,
    tolerancia: int = 60,
    preguntas: list[dict[str, Any]] | None = None,
    **extra: Any,
) -> Examen:
    cuerpo: dict[str, Any] = {
        "title": f"Examen de prueba {MARCA}",
        "starts_at": (inicio or datetime.now(UTC) - timedelta(minutes=1)).isoformat(),
        "duration_minutes": duracion,
        "entry_tolerance_minutes": tolerancia,
        "preset": preset,
        **extra,
    }
    if modules is not None:
        cuerpo["modules"] = modules
    with cliente() as c:
        r = c.post("/sessions", headers=docente.h, json=cuerpo)
        assert r.status_code == 201, r.text
        s = r.json()
        lista = preguntas if preguntas is not None else PREGUNTAS[:3] + PREGUNTAS[-1:]
        if not lista:
            # Un examen que tomará sus preguntas de un banco.
            return Examen(s["id"], s["access_code"], docente, s, [])
        q = c.post(f"/sessions/{s['id']}/questions", headers=docente.h, json={"questions": lista})
        assert q.status_code in (200, 201), q.text
    return Examen(s["id"], s["access_code"], docente, s, q.json())


def ingresar(e: Examen, alumno: Persona, *, admitir: bool = True) -> None:
    """Código, matrícula con consentimiento y (opcional) admisión del docente."""
    with cliente() as c:
        r = c.post("/sessions/join", headers=alumno.h, json={"access_code": e.codigo})
        assert r.status_code == 200, r.text
        r = c.post(f"/exam/{e.id}/enroll", headers=alumno.h, json={"accepts_supervision": True})
        assert r.status_code in (200, 201), r.text
        if admitir:
            r = c.post(
                f"/sessions/{e.id}/participants/{alumno.id}/identity",
                headers=e.docente.h,
                json={"approve": True},
            )
            assert r.status_code == 200, r.text


def evento(e: Examen, alumno: Persona, tipo: str, ms: int = 0, **extra: Any) -> dict[str, Any]:
    return {
        "session_id": e.id,
        "student_id": alumno.id,
        "question_id": e.preguntas[0]["id"] if e.preguntas else None,
        "event_type": tipo,
        "started_at": (datetime.now(UTC) - timedelta(seconds=1)).isoformat(),
        "duration_ms": ms,
        "metadata": {"origen": "pruebas"},
        **extra,
    }
