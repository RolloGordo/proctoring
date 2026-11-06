"""Prepara el escenario de la prueba de carga contra Supabase **local**.

1. `api.env`: las claves de Supabase local para las réplicas (`supabase status`).
2. Docentes y estudiantes de prueba en Auth local; los perfiles los crea el
   mismo disparador que en producción, y a los docentes se les sube el rol.
3. Un examen por grupo de estudiantes, creado **por la API**, como lo haría un
   docente: así pasa por las mismas validaciones, con preguntas reales.
4. Un token por persona, firmado con la clave ES256 local, igual que los que
   emite Auth (mismo `kid`, emisor y audiencia).

Nunca toca el proyecto de la nube: se niega a correr si la URL no es local.

    uv run python preparar.py clave               # una vez, antes de `supabase start`
    uv run python preparar.py env                 # antes de levantar la pila
    uv run python preparar.py datos --examenes 17 --por-examen 60
"""

from __future__ import annotations

import argparse
import json
import os
import secrets
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
import jwt

AQUI = Path(__file__).resolve().parent
DATOS = AQUI / ".datos"
CLAVE = AQUI.parent / "supabase" / "signing_keys.json"
AUTH_LOCAL = "http://127.0.0.1:54321"
#: Kong de Supabase local visto desde la red de Docker de Supabase: así llegan
#: las réplicas, sin pasar por el puente de puertos del equipo, que bajo picos
#: de conexiones las cortaba y falseaba la medida (ADR-0011).
KONG_EN_DOCKER = "http://supabase_kong_proctoring:8000"
#: El emisor configurado en supabase/config.toml, el mismo que ve la API.
EMISOR = f"{KONG_EN_DOCKER}/auth/v1"
API = "http://localhost:8080/api/v1"
CONTRASENA = "Carga-Local-2026!"


def estado_supabase() -> dict[str, str]:
    # En el CI la CLI está instalada como `supabase`; en local, por npx.
    cli = os.environ.get("SUPABASE_CLI", "npx -y supabase@2")
    salida = subprocess.run(
        f"{cli} status -o json",
        shell=True,
        capture_output=True,
        text=True,
        cwd=AQUI.parent,
        check=True,
    ).stdout
    datos: dict[str, str] = json.loads(salida[salida.index("{") : salida.rindex("}") + 1])
    if not datos["API_URL"].startswith(("http://127.0.0.1", "http://localhost")):
        sys.exit(f"Supabase no es local ({datos['API_URL']}): no se prueba carga contra la nube.")
    return datos


def generar_clave() -> None:
    """La clave ES256 de pruebas de Supabase local, en la lista que espera Auth."""
    if CLAVE.exists():
        print(f"Ya existe {CLAVE}; no se reemplaza.")
        return
    cli = os.environ.get("SUPABASE_CLI", "npx -y supabase@2")
    salida = subprocess.run(
        f"{cli} gen signing-key --algorithm ES256",
        shell=True,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    jwk = json.loads(salida[salida.index("{") : salida.rindex("}") + 1])
    CLAVE.write_text(json.dumps([jwk]), encoding="utf-8")
    print(f"Escrita {CLAVE} (clave privada de pruebas, fuera de git).")


def escribir_env() -> None:
    s = estado_supabase()
    DATOS.mkdir(exist_ok=True)
    (DATOS / "api.env").write_text(
        f"SUPABASE_URL={KONG_EN_DOCKER}\n"
        f"SUPABASE_SERVICE_ROLE_KEY={s['SERVICE_ROLE_KEY']}\n"
        f"SUPABASE_PUBLISHABLE_KEY={s['ANON_KEY']}\n"
        # Producción exige el secreto entre la API y el worker de IA.
        f"INTERNAL_API_TOKEN={secrets.token_urlsafe(32)}\n",
        encoding="utf-8",
    )
    print("Escrito loadtests/.datos/api.env (claves de Supabase local, fuera de git).")


class Firmador:
    """Firma tokens como Auth local: ES256 con la misma clave y el mismo `kid`."""

    def __init__(self) -> None:
        jwk = json.loads(CLAVE.read_text(encoding="utf-8"))[0]
        self._kid = jwk["kid"]
        self._clave = jwt.PyJWK(jwk).key

    def token(self, sub: str, email: str, horas: int = 6) -> str:
        ahora = datetime.now(UTC)
        return jwt.encode(
            {
                "iss": EMISOR,
                "sub": sub,
                "aud": "authenticated",
                "role": "authenticated",
                "email": email,
                "iat": int(ahora.timestamp()),
                "exp": int((ahora + timedelta(hours=horas)).timestamp()),
                "session_id": str(uuid4()),
            },
            self._clave,
            algorithm="ES256",
            headers={"kid": self._kid},
        )


def crear_usuario(admin: httpx.Client, email: str, nombre: str) -> str:
    r = admin.post(
        "/auth/v1/admin/users",
        json={
            "email": email,
            "password": CONTRASENA,
            "email_confirm": True,
            "user_metadata": {"full_name": nombre},
        },
    )
    if r.status_code == 422 and "already" in r.text:
        # Ya existe de una corrida anterior: se busca su id.
        lista = admin.get("/auth/v1/admin/users", params={"per_page": 2000}).json()
        return next(u["id"] for u in lista["users"] if u["email"] == email)
    r.raise_for_status()
    return str(r.json()["id"])


PREGUNTAS = (
    [
        {
            "question_type": "multiple_choice",
            "statement": f"Pregunta de opción múltiple número {i}: ¿qué capa no importa frameworks?",
            "points": "1",
            "options": [
                {"option_text": "Dominio", "is_correct": True},
                {"option_text": "Adaptadores", "is_correct": False},
                {"option_text": "Routers", "is_correct": False},
            ],
        }
        for i in range(1, 15)
    ]
    + [
        {
            "question_type": "true_false",
            "statement": f"Afirmación {i}: Redis desacopla el análisis de audio de la API.",
            "points": "1",
            "options": [
                {"option_text": "Verdadero", "is_correct": True},
                {"option_text": "Falso", "is_correct": False},
            ],
        }
        for i in range(1, 5)
    ]
    + [
        {
            "question_type": "numeric",
            "statement": "¿Cuántos segundos como máximo puede tardar la alerta de IA por voz?",
            "points": "2",
            "correct_numeric_answer": "10",
        }
    ]
)


def preparar_datos(examenes: int, por_examen: int, docentes: int) -> None:
    s = estado_supabase()
    firmador = Firmador()
    cabeceras = {
        "apikey": s["SERVICE_ROLE_KEY"],
        "Authorization": f"Bearer {s['SERVICE_ROLE_KEY']}",
    }
    marca = int(time.time())

    with httpx.Client(base_url=AUTH_LOCAL, headers=cabeceras, timeout=30) as admin:
        print(f"Creando {docentes} docentes y {examenes * por_examen} estudiantes en Auth local…")
        ids_docentes = [
            crear_usuario(admin, f"docente{d}.{marca}@carga.test", f"Docente {d}")
            for d in range(docentes)
        ]
        # Los perfiles nacen como estudiante (el disparador no deja elegir el
        # rol); a los docentes se les sube con la service role, como en la nube.
        admin.patch(
            "/rest/v1/profiles",
            params={"id": f"in.({','.join(ids_docentes)})"},
            json={"role": "teacher"},
        ).raise_for_status()

        correos = [f"alumno{n}.{marca}@carga.test" for n in range(examenes * por_examen)]
        with ThreadPoolExecutor(max_workers=16) as hilos:
            ids_estudiantes = list(
                hilos.map(lambda c: crear_usuario(admin, c, c.split("@")[0]), correos)
            )

    tokens_docentes = [
        firmador.token(i, f"docente{d}.{marca}@carga.test") for d, i in enumerate(ids_docentes)
    ]
    ahora = datetime.now(UTC)
    escenario: dict[str, Any] = {"creado": ahora.isoformat(), "examenes": []}

    with httpx.Client(base_url=API, timeout=30) as api:
        for e in range(examenes):
            token_docente = tokens_docentes[e % docentes]
            h = {"Authorization": f"Bearer {token_docente}"}
            sesion = api.post(
                "/sessions",
                headers=h,
                json={
                    "title": f"Carga · examen {e + 1}",
                    # Empezó hace un minuto y admite entrar durante una hora:
                    # la prueba decide el ritmo, no el reloj del examen.
                    "starts_at": (ahora - timedelta(minutes=1)).isoformat(),
                    "duration_minutes": 120,
                    "entry_tolerance_minutes": 60,
                },
            )
            sesion.raise_for_status()
            sid = sesion.json()["id"]
            api.post(
                f"/sessions/{sid}/questions", headers=h, json={"questions": PREGUNTAS}
            ).raise_for_status()
            grupo = range(e * por_examen, (e + 1) * por_examen)
            escenario["examenes"].append(
                {
                    "id": sid,
                    "codigo": sesion.json()["access_code"],
                    "docente_token": token_docente,
                    "estudiantes": [
                        {
                            "id": ids_estudiantes[n],
                            "token": firmador.token(ids_estudiantes[n], correos[n]),
                        }
                        for n in grupo
                    ],
                }
            )
            print(f"  examen {e + 1}/{examenes}: {sid} · código {sesion.json()['access_code']}")

    (DATOS / "escenario.json").write_text(json.dumps(escenario), encoding="utf-8")
    total = sum(len(x["estudiantes"]) for x in escenario["examenes"])
    print(
        f"Listo: {len(escenario['examenes'])} exámenes, {total} estudiantes -> .datos/escenario.json"
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    sub = p.add_subparsers(dest="paso", required=True)
    sub.add_parser("clave")
    sub.add_parser("env")
    d = sub.add_parser("datos")
    d.add_argument("--examenes", type=int, default=17)
    d.add_argument("--por-examen", type=int, default=60)
    d.add_argument("--docentes", type=int, default=6)
    a = p.parse_args()
    if a.paso == "clave":
        generar_clave()
    elif a.paso == "env":
        escribir_env()
    else:
        preparar_datos(a.examenes, a.por_examen, a.docentes)
