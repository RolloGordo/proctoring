"""Pruebas de caja negra de la API (27/11/2026).

Se diseñan **desde fuera**: desde los criterios de aceptación de `specs/SPEC-00x`,
el contrato publicado (OpenAPI en `/docs`) y las reglas del producto en `CLAUDE.md`,
sin mirar cómo está implementado cada caso. Técnicas:

- **PE**: particiones de equivalencia (una entrada válida y una por cada clase inválida).
- **VL**: análisis de valores límite (el límite, uno por debajo y uno por encima).
- **TD**: tabla de decisión (combinaciones de condiciones → resultado esperado).
- **TE**: transición de estados (inscrito → en espera → admitido → entregado).
- **AE**: adivinación de errores (entradas que suelen romper APIs).

Cada docstring empieza con `ID | técnica | resultado esperado`, que el informe usa tal cual.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx
import pytest

from comun import V1, Examen, Persona, cliente, crear_examen, evento, ingresar, persona


@pytest.fixture()
def docente() -> Persona:
    # Uno por prueba: el límite de 120 escrituras por minuto es por persona, y un
    # docente compartido lo agotaría creando exámenes en las pruebas de límites.
    return persona("teacher")


@pytest.fixture(scope="module")
def c() -> httpx.Client:
    with cliente() as cli:
        yield cli


def sesion(docente: Persona, **campos: object) -> dict[str, object]:
    base: dict[str, object] = {
        "title": "Caja negra",
        "starts_at": datetime.now(UTC).isoformat(),
        "duration_minutes": 60,
        "preset": "standard",
    }
    base.update(campos)
    return base


# ---------------------------------------------------------------- SPEC-001: autenticación y roles


def test_cn01_sin_token(c: httpx.Client) -> None:
    """CN-01 | PE | Sin cabecera Authorization, un endpoint protegido responde 401 (SPEC-001 CA-2)."""
    assert c.get("/sessions").status_code == 401


def test_cn02_token_basura(c: httpx.Client) -> None:
    """CN-02 | PE | Un token que no es JWT responde 401 (SPEC-001 CA-3)."""
    assert c.get("/sessions", headers={"Authorization": "Bearer no-es-un-jwt"}).status_code == 401


def test_cn03_token_alg_none(c: httpx.Client) -> None:
    """CN-03 | AE | Un JWT con alg=none (sin firma) responde 401."""
    falso = "eyJhbGciOiJub25lIiwidHlwIjoiSldUIn0.eyJzdWIiOiJ4Iiwicm9sZSI6InRlYWNoZXIifQ."
    assert c.get("/sessions", headers={"Authorization": f"Bearer {falso}"}).status_code == 401


def test_cn04_token_vencido(c: httpx.Client) -> None:
    """CN-04 | VL | Un token bien firmado pero vencido hace 1 h responde 401 con un mensaje (SPEC-001 CA-3)."""
    from comun import firmador

    p = persona()
    vencido = firmador().token(p.id, p.email, horas=-1)
    r = c.get("/me/exams", headers={"Authorization": f"Bearer {vencido}"})
    assert r.status_code == 401
    assert r.json().get("detail"), "el 401 debe traer un mensaje claro"


def test_cn05_estudiante_en_panel_docente(c: httpx.Client) -> None:
    """CN-05 | PE | Un estudiante que pide la lista de exámenes del docente recibe 403 (SPEC-001 CA-1)."""
    assert c.get("/sessions", headers=persona().h).status_code == 403


def test_cn06_estudiante_no_crea_examen(c: httpx.Client) -> None:
    """CN-06 | PE | Un estudiante no puede crear un examen: 403."""
    assert c.post("/sessions", headers=persona().h, json=sesion(persona())).status_code == 403


def test_cn07_docente_ajeno(c: httpx.Client, docente: Persona) -> None:
    """CN-07 | PE | Un docente no ve la sala de espera del examen de otro docente (403 o 404)."""
    e = crear_examen(docente)
    otro = persona("teacher")
    assert c.get(f"/sessions/{e.id}/participants", headers=otro.h).status_code in (403, 404)


def test_cn08_docente_lista_sus_examenes(c: httpx.Client, docente: Persona) -> None:
    """CN-08 | PE | Un docente con token válido lista sus exámenes: 200 y el creado aparece."""
    e = crear_examen(docente)
    r = c.get("/sessions", headers=docente.h)
    assert r.status_code == 200
    assert e.id in {s["id"] for s in r.json()}


# ---------------------------------------------------------------- SPEC-002: crear sesión (límites)


@pytest.mark.parametrize(
    ("campo", "valor", "esperado"),
    [
        ("title", "", 422),
        ("title", "x", 201),
        ("title", "x" * 200, 201),
        ("title", "x" * 201, 422),
        ("duration_minutes", 0, 422),
        ("duration_minutes", 1, 201),
        ("duration_minutes", 600, 201),
        ("duration_minutes", 601, 422),
        ("entry_tolerance_minutes", -1, 422),
        ("entry_tolerance_minutes", 0, 201),
        ("entry_tolerance_minutes", 120, 201),
        ("entry_tolerance_minutes", 121, 422),
        ("max_attempts", 0, 422),
        ("max_attempts", 1, 201),
        ("max_attempts", 10, 201),
        ("max_attempts", 11, 422),
    ],
)
def test_cn09_limites_de_sesion(c: httpx.Client, docente: Persona, campo: str, valor: object, esperado: int) -> None:
    """CN-09 | VL | Título 1–200, duración 1–600 min, tolerancia 0–120 min, intentos 1–10: el límite se acepta (201) y uno más allá se rechaza (422)."""
    assert c.post("/sessions", headers=docente.h, json=sesion(docente, **{campo: valor})).status_code == esperado


@pytest.mark.parametrize("preset", ["strict", "standard", "basic", "intermedio", ""])
def test_cn10_presets(c: httpx.Client, docente: Persona, preset: str) -> None:
    """CN-10 | PE | Los presets strict, standard y basic se aceptan (201); un valor fuera del catálogo se rechaza (422)."""
    r = c.post("/sessions", headers=docente.h, json=sesion(docente, preset=preset))
    assert r.status_code == (201 if preset in ("strict", "standard", "basic") else 422)


def test_cn11_codigo_unico(c: httpx.Client, docente: Persona) -> None:
    """CN-11 | PE | Cada sesión recibe un access_code, distinto entre sesiones (SPEC-002 CA-1)."""
    codigos = {c.post("/sessions", headers=docente.h, json=sesion(docente)).json()["access_code"] for _ in range(5)}
    assert len(codigos) == 5 and all(codigos)


def test_cn12_modulos_guardados(c: httpx.Client, docente: Persona) -> None:
    """CN-12 | PE | Un examen custom guarda exactamente los módulos que eligió el docente (SPEC-002 CA-2)."""
    r = c.post(
        "/sessions",
        headers=docente.h,
        json=sesion(docente, preset="custom", modules={"gaze": {}, "focus_loss": {}}),
    )
    assert r.status_code == 201
    leido = c.get(f"/sessions/{r.json()['id']}", headers=docente.h).json()
    assert {"gaze", "focus_loss"} <= set(leido["modules"])
    assert "ai_voice" not in leido["modules"]


def test_cn13_campo_desconocido(c: httpx.Client, docente: Persona) -> None:
    """CN-13 | AE | Un JSON mal formado responde 422, no 500."""
    r = c.post("/sessions", headers={**docente.h, "Content-Type": "application/json"}, content=b"{titulo:")
    assert r.status_code == 422


# ---------------------------------------------------------------- SPEC-002: ingreso con código


@pytest.mark.parametrize(("codigo", "esperado"), [("abc", 422), ("x" * 17, 422), ("ZZZZ", 400), ("Z" * 16, 400)])
def test_cn14_codigo_limites(c: httpx.Client, codigo: str, esperado: int) -> None:
    """CN-14 | VL | El código tiene 4–16 caracteres: con 3 o 17 es 422; uno de longitud válida que no existe es 400 con un mensaje que dice qué hacer."""
    r = c.post("/sessions/join", headers=persona().h, json={"access_code": codigo})
    assert r.status_code == esperado
    if esperado == 400:
        assert "código" in r.json()["detail"]


def test_cn15_ingreso_valido(c: httpx.Client, docente: Persona) -> None:
    """CN-15 | PE | Con un código vigente el estudiante ve el examen sin las preguntas (200) (SPEC-002 CA-3)."""
    e = crear_examen(docente)
    r = c.post("/sessions/join", headers=persona().h, json={"access_code": e.codigo})
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["session_id"] == e.id and "questions" not in cuerpo


def test_cn16_examen_terminado(c: httpx.Client, docente: Persona) -> None:
    """CN-16 | TE | Un estudiante no puede entrar a una sesión que ya terminó (SPEC-002 CA-4)."""
    inicio = datetime.now(UTC) - timedelta(hours=3)
    e = crear_examen(docente, inicio=inicio, duracion=60, tolerancia=0)
    p = persona()
    r1 = c.post("/sessions/join", headers=p.h, json={"access_code": e.codigo})
    r2 = c.post(f"/exam/{e.id}/enroll", headers=p.h, json={"accepts_supervision": True})
    assert r1.status_code >= 400 or not r1.json()["can_enter_now"]
    assert r2.status_code >= 400


def test_cn17_examen_cancelado(c: httpx.Client, docente: Persona) -> None:
    """CN-17 | TE | Tras cancelar el examen, el código deja de servir para matricularse."""
    e = crear_examen(docente)
    assert c.post(f"/sessions/{e.id}/cancel", headers=docente.h).status_code in (200, 204)
    p = persona()
    c.post("/sessions/join", headers=p.h, json={"access_code": e.codigo})
    assert c.post(f"/exam/{e.id}/enroll", headers=p.h, json={"accepts_supervision": True}).status_code >= 400


def test_cn18_consentimiento_obligatorio(c: httpx.Client, docente: Persona) -> None:
    """CN-18 | TD | Sin aceptar la supervisión (false o ausente) no hay matrícula; con true sí."""
    e = crear_examen(docente)
    p = persona()
    c.post("/sessions/join", headers=p.h, json={"access_code": e.codigo})
    assert c.post(f"/exam/{e.id}/enroll", headers=p.h, json={}).status_code == 422
    assert c.post(f"/exam/{e.id}/enroll", headers=p.h, json={"accepts_supervision": False}).status_code >= 400
    assert c.post(f"/exam/{e.id}/enroll", headers=p.h, json={"accepts_supervision": True}).status_code in (200, 201)


def test_cn19_limite_intentos_codigo(c: httpx.Client) -> None:
    """CN-19 | VL | Hasta 10 intentos de código por minuto se atienden; el 11.º recibe 429 (protección de fuerza bruta)."""
    p = persona()
    codigos = [c.post("/sessions/join", headers=p.h, json={"access_code": f"NOEX{i:04d}"}).status_code for i in range(11)]
    assert all(x == 400 for x in codigos[:10]), codigos
    assert codigos[10] == 429


# ---------------------------------------------------------------- SPEC-004: rendición (transición de estados)


def test_cn20_sin_admision_no_hay_preguntas(c: httpx.Client, docente: Persona) -> None:
    """CN-20 | TE | Matriculado pero sin admitir: no puede descargar las preguntas (estado «en espera»)."""
    e = crear_examen(docente)
    p = persona()
    ingresar(e, p, admitir=False)
    estado = c.get(f"/exam/{e.id}/me", headers=p.h).json()
    assert estado["can_take_exam"] is False
    assert c.get(f"/exam/{e.id}/questions", headers=p.h).status_code >= 400


def test_cn21_admitido_rinde(c: httpx.Client, docente: Persona) -> None:
    """CN-21 | TE | Admitido: ve las preguntas sin las respuestas correctas y puede guardar respuestas."""
    e = crear_examen(docente)
    p = persona()
    ingresar(e, p)
    r = c.get(f"/exam/{e.id}/questions", headers=p.h)
    assert r.status_code == 200
    texto = r.text
    assert "is_correct" not in texto and "correct_numeric_answer" not in texto
    q = r.json()[0]
    g = c.put(f"/exam/{e.id}/answers", headers=p.h, json={"answers": [{"question_id": q["id"], "selected_option_id": q["options"][0]["id"]}]})
    assert g.status_code in (200, 201)


def test_cn22_entrega_unica(c: httpx.Client, docente: Persona) -> None:
    """CN-22 | TE | Tras entregar, no se puede volver a responder ni entregar de nuevo."""
    e = crear_examen(docente)
    p = persona()
    ingresar(e, p)
    q = c.get(f"/exam/{e.id}/questions", headers=p.h).json()[0]
    assert c.post(f"/exam/{e.id}/submit", headers=p.h).status_code == 200
    g = c.put(f"/exam/{e.id}/answers", headers=p.h, json={"answers": [{"question_id": q["id"], "selected_option_id": q["options"][0]["id"]}]})
    assert g.status_code >= 400
    assert c.post(f"/exam/{e.id}/submit", headers=p.h).status_code >= 400


def test_cn23_respuesta_a_pregunta_ajena(c: httpx.Client, docente: Persona) -> None:
    """CN-23 | AE | Responder con el id de una pregunta de otro examen se rechaza (4xx), no se guarda."""
    e1, e2 = crear_examen(docente), crear_examen(docente)
    p = persona()
    ingresar(e1, p)
    ajena = e2.preguntas[0]
    r = c.put(f"/exam/{e1.id}/answers", headers=p.h, json={"answers": [{"question_id": ajena["id"], "selected_option_id": ajena["options"][0]["id"]}]})
    assert 400 <= r.status_code < 500


def test_cn24_lote_respuestas_limites(c: httpx.Client, docente: Persona) -> None:
    """CN-24 | VL | Un lote de respuestas vacío (0) se rechaza con 422; el máximo es 200 y 201 se rechaza."""
    e = crear_examen(docente)
    p = persona()
    ingresar(e, p)
    q = e.preguntas[0]["id"]
    assert c.put(f"/exam/{e.id}/answers", headers=p.h, json={"answers": []}).status_code == 422
    assert c.put(f"/exam/{e.id}/answers", headers=p.h, json={"answers": [{"question_id": q}] * 201}).status_code == 422


# ---------------------------------------------------------------- Preguntas (límites)


@pytest.mark.parametrize(("n", "esperado"), [(0, 422), (1, 201), (50, 201), (51, 422)])
def test_cn25_cantidad_de_preguntas(c: httpx.Client, docente: Persona, n: int, esperado: int) -> None:
    """CN-25 | VL | Se agregan de 1 a 50 preguntas por petición: 0 y 51 se rechazan (422)."""
    s = c.post("/sessions", headers=docente.h, json=sesion(docente)).json()
    pregunta = {"question_type": "numeric", "statement": "¿2+2?", "points": "1", "correct_numeric_answer": "4"}
    r = c.post(f"/sessions/{s['id']}/questions", headers=docente.h, json={"questions": [pregunta] * n})
    assert (r.status_code in (200, 201)) == (esperado == 201) and (r.status_code != 422) == (esperado != 422)


@pytest.mark.parametrize(("puntos", "esperado"), [("-0.01", 422), ("0", 201), ("100", 201), ("100.01", 422)])
def test_cn26_puntaje(c: httpx.Client, docente: Persona, puntos: str, esperado: int) -> None:
    """CN-26 | VL | El puntaje de una pregunta va de 0 a 100: −0,01 y 100,01 se rechazan."""
    s = c.post("/sessions", headers=docente.h, json=sesion(docente)).json()
    pregunta = {"question_type": "numeric", "statement": "¿2+2?", "points": puntos, "correct_numeric_answer": "4"}
    r = c.post(f"/sessions/{s['id']}/questions", headers=docente.h, json={"questions": [pregunta]})
    assert (r.status_code == 422) == (esperado == 422)


# ---------------------------------------------------------------- Señales: tabla de decisión y severidad


@pytest.fixture(scope="module")
def custom_vista() -> tuple[Examen, Persona]:
    e = crear_examen(persona("teacher"), preset="custom", modules={"gaze": {}, "extra_person": {}})
    p = persona()
    ingresar(e, p)
    return e, p


@pytest.mark.parametrize(
    ("tipo", "vigilado"),
    [
        ("gaze_away", True),
        ("face_absent", True),
        ("extra_person", True),
        ("focus_lost", False),
        ("extra_display", False),
        ("suspicious_process", False),
        ("speech_detected", False),
        ("copy_attempt", False),
    ],
)
def test_cn27_modulo_apagado(c: httpx.Client, custom_vista: tuple[Examen, Persona], tipo: str, vigilado: bool) -> None:
    """CN-27 | TD | En un examen custom con solo mirada y persona adicional: sus señales se aceptan (201) y las de módulos apagados se rechazan (400)."""
    e, p = custom_vista
    r = c.post("/events", headers=p.h, json=evento(e, p, tipo, 2000))
    assert r.status_code == (201 if vigilado else 400), r.text


@pytest.fixture(scope="module")
def estricto() -> tuple[Examen, Persona]:
    e = crear_examen(persona("teacher"), preset="strict")
    p = persona()
    ingresar(e, p)
    return e, p


@pytest.mark.parametrize(
    ("tipo", "ms", "severidad"),
    [
        ("focus_lost", 4999, "low"),
        ("focus_lost", 5000, "medium"),
        ("focus_lost", 29999, "medium"),
        ("focus_lost", 30000, "high"),
        ("face_absent", 4999, "low"),
        ("face_absent", 5000, "medium"),
        ("face_absent", 14999, "medium"),
        ("face_absent", 15000, "high"),
        ("gaze_away", 9999, "low"),
        ("gaze_away", 10000, "medium"),
        ("extra_person", 0, "high"),
        ("suspicious_process", 0, "high"),
        ("extra_display", 0, "medium"),
        ("speech_detected", 1500, "medium"),
    ],
)
def test_cn28_severidad(c: httpx.Client, estricto: tuple[Examen, Persona], tipo: str, ms: int, severidad: str) -> None:
    """CN-28 | VL | La severidad cambia exactamente en los umbrales publicados: foco 5 s/30 s, rostro 5 s/15 s, mirada 10 s; persona adicional y procesos, alta; hablar, media."""
    e, p = estricto
    r = c.post("/events", headers=p.h, json=evento(e, p, tipo, ms))
    assert r.status_code == 201, r.text
    assert r.json()["severity"] == severidad


@pytest.mark.parametrize(
    ("cambio", "esperado"),
    [
        ({"duration_ms": -1}, 422),
        ({"event_type": "teletransporte"}, 422),
        ({"session_id": "no-uuid"}, 422),
        ({"started_at": "ayer"}, 422),
        ({"evidence_path": "x" * 5000}, 422),
    ],
)
def test_cn29_evento_invalido(c: httpx.Client, estricto: tuple[Examen, Persona], cambio: dict[str, object], esperado: int) -> None:
    """CN-29 | PE | Clases inválidas del contrato de evento: duración negativa, tipo fuera del catálogo, UUID mal formado, fecha no ISO-8601 o ruta de evidencia enorme dan 422."""
    e, p = estricto
    assert c.post("/events", headers=p.h, json={**evento(e, p, "focus_lost", 1000), **cambio}).status_code == esperado


def test_cn30_evento_suplantado(c: httpx.Client, estricto: tuple[Examen, Persona]) -> None:
    """CN-30 | AE | Un estudiante no puede mandar señales a nombre de otro (student_id ajeno): 403."""
    e, p = estricto
    otro = persona()
    r = c.post("/events", headers=otro.h, json=evento(e, p, "focus_lost", 1000))
    assert r.status_code == 403


def test_cn31_evento_sin_matricula(c: httpx.Client, estricto: tuple[Examen, Persona]) -> None:
    """CN-31 | TE | Un estudiante que no está matriculado en el examen no puede mandar señales (4xx)."""
    e, _ = estricto
    intruso = persona()
    assert 400 <= c.post("/events", headers=intruso.h, json=evento(e, intruso, "focus_lost", 1000)).status_code < 500


def test_cn32_eventos_inmutables(c: httpx.Client, estricto: tuple[Examen, Persona]) -> None:
    """CN-32 | PE | Los eventos no se editan ni se borran: PUT y DELETE sobre /events responden 405 (SPEC-009 CA-6)."""
    _, p = estricto
    assert c.put("/events", headers=p.h, json={}).status_code == 405
    assert c.delete("/events", headers=p.h).status_code == 405


# ---------------------------------------------------------------- SPEC-009: riesgo, alertas y decisión


def test_cn33_riesgo_desglosado(c: httpx.Client, docente: Persona) -> None:
    """CN-33 | PE | El riesgo del estudiante viene desglosado por señal, no como un número suelto (SPEC-009 CA-1)."""
    e = crear_examen(docente, preset="strict")
    p = persona()
    ingresar(e, p)
    for tipo, ms in [("extra_person", 0), ("focus_lost", 6000), ("focus_lost", 7000)]:
        assert c.post("/events", headers=p.h, json=evento(e, p, tipo, ms)).status_code == 201
    resumen = c.get(f"/sessions/{e.id}/risk", headers=docente.h)
    assert resumen.status_code == 200
    fila = next(x for x in resumen.json() if x["student_id"] == p.id)
    caso = c.get(f"/sessions/{e.id}/students/{p.id}/case", headers=docente.h)
    assert caso.status_code == 200
    riesgo = caso.json()["risk"]
    por_tipo = {s["event_type"]: s for s in riesgo["signals"]}
    assert set(por_tipo) >= {"extra_person", "focus_lost"}
    assert por_tipo["focus_lost"]["count"] == 2
    # El total es la suma de lo que aporta cada señal: el número se explica solo.
    assert riesgo["score"] == min(100, sum(s["points"] for s in riesgo["signals"])) == fila["score"]


def test_cn34_alerta_registrada(c: httpx.Client, docente: Persona) -> None:
    """CN-34 | PE | Una señal de severidad alta crea una alerta visible para el docente del examen."""
    e = crear_examen(docente, preset="strict")
    p = persona()
    ingresar(e, p)
    ev = c.post("/events", headers=p.h, json=evento(e, p, "suspicious_process", 0, metadata={"process": "anydesk"})).json()
    alertas = c.get(f"/sessions/{e.id}/alerts", headers=docente.h).json()
    assert any(a["event_id"] == ev["id"] and a["severity"] == "high" for a in alertas)


@pytest.mark.parametrize(("justificacion", "ok"), [("", False), ("123456789", False), ("1234567890", True), ("x" * 2000, True), ("x" * 2001, False)])
def test_cn35_justificacion(c: httpx.Client, docente: Persona, justificacion: str, ok: bool) -> None:
    """CN-35 | VL | La decisión exige justificación de al menos 10 caracteres (9 se rechaza, 10 se acepta) y como máximo 2000 (SPEC-009 CA-4)."""
    e = crear_examen(docente)
    p = persona()
    ingresar(e, p)
    r = c.post(f"/sessions/{e.id}/students/{p.id}/decision", headers=docente.h, json={"decision": "dismissed", "justification": justificacion})
    assert (r.status_code in (200, 201)) == ok, r.text


@pytest.mark.parametrize("decision", ["confirmed", "dismissed", "retake", "annulled"])
def test_cn36_tipos_de_decision(c: httpx.Client, docente: Persona, decision: str) -> None:
    """CN-36 | PE | Solo existen confirmed, dismissed y retake; cualquier otro valor (p. ej. annulled) da 422."""
    e = crear_examen(docente)
    p = persona()
    ingresar(e, p)
    r = c.post(f"/sessions/{e.id}/students/{p.id}/decision", headers=docente.h, json={"decision": decision, "justification": "Revisado con la evidencia completa."})
    assert (r.status_code == 422) == (decision == "annulled")


def test_cn37_estudiante_no_decide(c: httpx.Client, docente: Persona) -> None:
    """CN-37 | PE | Un estudiante no puede registrar decisiones sobre su propio caso: 403."""
    e = crear_examen(docente)
    p = persona()
    ingresar(e, p)
    r = c.post(f"/sessions/{e.id}/students/{p.id}/decision", headers=p.h, json={"decision": "dismissed", "justification": "Yo no hice nada malo."})
    assert r.status_code == 403


def test_cn38_nunca_anula_solo(c: httpx.Client, docente: Persona) -> None:
    """CN-38 | TE | Con 20 señales altas el estudiante sigue pudiendo entregar y no existe decisión: el sistema no anula por su cuenta (SPEC-009 CA-5)."""
    e = crear_examen(docente, preset="strict")
    p = persona()
    ingresar(e, p)
    for _ in range(20):
        c.post("/events", headers=p.h, json=evento(e, p, "extra_person", 0))
    decisiones = c.get(f"/sessions/{e.id}/decisions", headers=docente.h).json()
    assert not [d for d in decisiones if d["student_id"] == p.id]
    assert c.post(f"/exam/{e.id}/submit", headers=p.h).status_code == 200


# ---------------------------------------------------------------- Adivinación de errores generales


def test_cn39_uuid_mal_formado_en_ruta(c: httpx.Client, docente: Persona) -> None:
    """CN-39 | AE | Un id que no es UUID en la ruta responde 422, no 500."""
    assert c.get("/sessions/no-es-uuid", headers=docente.h).status_code == 422


def test_cn40_examen_inexistente(c: httpx.Client, docente: Persona) -> None:
    """CN-40 | AE | Un UUID válido que no existe responde 403, igual que uno ajeno: no revela si el examen existe."""
    inexistente = c.get("/sessions/00000000-0000-4000-8000-00000000dead", headers=docente.h)
    ajeno = c.get(f"/sessions/{crear_examen(persona('teacher')).id}", headers=docente.h)
    assert inexistente.status_code == ajeno.status_code == 403
    assert inexistente.json() == ajeno.json()


def test_cn41_inyeccion_sql_en_codigo(c: httpx.Client) -> None:
    """CN-41 | AE | Un código de acceso con inyección SQL se trata como texto: se responde «no existe» (400), nunca 500 ni un examen."""
    r = c.post("/sessions/join", headers=persona().h, json={"access_code": "' OR 1=1--"})
    assert r.status_code == 400 and "session_id" not in r.text


def test_cn42_titulo_con_html(c: httpx.Client, docente: Persona) -> None:
    """CN-42 | AE | Un título con <script> se guarda y se devuelve como texto, idéntico (la web lo escapa al mostrarlo)."""
    titulo = '<script>alert("x")</script> Ñandú ✓'
    r = c.post("/sessions", headers=docente.h, json=sesion(docente, title=titulo))
    assert r.status_code == 201 and r.json()["title"] == titulo


def test_cn43_salud(c: httpx.Client) -> None:
    """CN-43 | PE | /health responde 200 sin token e informa que la autenticación está activada."""
    r = httpx.get(V1.replace("/api/v1", "") + "/health", timeout=10)
    assert r.status_code == 200 and r.json().get("auth") == "enabled"
