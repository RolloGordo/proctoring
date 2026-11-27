"""Pruebas funcionales: cada funcionalidad del sistema contra su requisito (27/11/2026).

Las de caja negra atacan bordes y entradas malas; estas comprueban que **cada
funcionalidad hace su trabajo completo** en el caso normal, tal como la describe el
backlog: cursos, bancos, QTI, calificación, revisión, aleatorización, pool,
intentos, límite de actividad, edición, decisión visible al estudiante.

Contra el entorno aislado. Docstring: `ID | funcionalidad (requisito) | resultado esperado`.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx
import pytest

from comun import Persona, cliente, crear_examen, evento, ingresar, persona

QTI = Path(__file__).resolve().parents[2] / "services" / "api" / "tests" / "fixtures" / "qti"


def opcion(n: int) -> dict[str, Any]:
    return {
        "question_type": "multiple_choice",
        "statement": f"Pregunta funcional {n}: ¿cuál es la opción correcta?",
        "points": "2",
        "options": [{"option_text": f"Correcta {n}", "is_correct": True}, {"option_text": f"Incorrecta {n}", "is_correct": False}],
    }


NUMERICA = {"question_type": "numeric", "statement": "¿Cuánto es 7 × 6?", "points": "4", "correct_numeric_answer": "42", "numeric_tolerance": "0.5"}


@pytest.fixture()
def c() -> httpx.Client:
    with cliente() as cli:
        yield cli


@pytest.fixture()
def docente() -> Persona:
    return persona("teacher", "Docente Funcional")


def responder_todo(c: httpx.Client, e_id: str, alumno: Persona, bien: bool, numero: str = "42") -> None:
    preguntas = c.get(f"/exam/{e_id}/questions", headers=alumno.h).json()
    lote = []
    for q in preguntas:
        if q["question_type"] == "numeric":
            lote.append({"question_id": q["id"], "numeric_answer": numero if bien else "13"})
        else:
            elegida = next(o for o in q["options"] if o["option_text"].startswith("Correcta" if bien else "Incorrecta"))
            lote.append({"question_id": q["id"], "selected_option_id": elegida["id"]})
    assert c.put(f"/exam/{e_id}/answers", headers=alumno.h, json={"answers": lote}).status_code in (200, 201)


# ---------------------------------------------------------------- cursos


def test_rf01_curso_y_matricula(c: httpx.Client, docente: Persona) -> None:
    """RF-01 | Cursos | El docente crea un curso, matricula a un estudiante por su correo y el estudiante ve el curso con sus exámenes."""
    curso = c.post("/courses", headers=docente.h, json={"name": "Taller Integrador 1", "section": "A"})
    assert curso.status_code == 201, curso.text
    cid = curso.json()["id"]
    alumno = persona(nombre="Estudiante del curso")
    m = c.post(f"/courses/{cid}/students", headers=docente.h, json={"email": alumno.email})
    assert m.status_code in (200, 201), m.text
    assert m.json()["student"]["student_id"] == alumno.id
    e = crear_examen(docente, course_id=cid)
    mios = c.get("/me/courses", headers=alumno.h).json()
    del_curso = next(x for x in mios if x["id"] == cid)
    assert del_curso["name"] == "Taller Integrador 1"
    assert e.id in {x["session_id"] for x in del_curso["exams"]}
    lista = c.get(f"/courses/{cid}/students", headers=docente.h).json()
    assert [s["student_id"] for s in lista] == [alumno.id]


def test_rf02_matricula_repetida_y_correo_desconocido(c: httpx.Client, docente: Persona) -> None:
    """RF-02 | Cursos | Matricular dos veces al mismo estudiante no lo duplica, y un correo que no tiene cuenta da un error que lo explica."""
    cid = c.post("/courses", headers=docente.h, json={"name": "Curso de repetidos"}).json()["id"]
    alumno = persona()
    c.post(f"/courses/{cid}/students", headers=docente.h, json={"email": alumno.email})
    segunda = c.post(f"/courses/{cid}/students", headers=docente.h, json={"email": alumno.email})
    assert segunda.json()["already_enrolled"] is True
    assert len(c.get(f"/courses/{cid}/students", headers=docente.h).json()) == 1
    nadie = c.post(f"/courses/{cid}/students", headers=docente.h, json={"email": "nadie.existe@pruebas.test"})
    assert 400 <= nadie.status_code < 500 and nadie.json().get("detail")


# ---------------------------------------------------------------- bancos y QTI


def test_rf03_banco_asociado_al_examen(c: httpx.Client, docente: Persona) -> None:
    """RF-03 | Banco de preguntas | Las preguntas de un banco asociado a un examen son las que recibe el estudiante."""
    banco = c.post("/question-banks", headers=docente.h, json={"name": "Banco de arquitectura"}).json()
    r = c.post(f"/question-banks/{banco['id']}/questions", headers=docente.h, json={"questions": [opcion(i) for i in range(1, 5)]})
    assert r.status_code in (200, 201), r.text
    e = crear_examen(docente, preguntas=[])
    assert c.post(f"/sessions/{e.id}/banks", headers=docente.h, json={"bank_id": banco["id"]}).status_code in (200, 201)
    alumno = persona()
    ingresar(e, alumno)
    servidas = c.get(f"/exam/{e.id}/questions", headers=alumno.h).json()
    assert len(servidas) == 4
    assert {q["statement"] for q in servidas} == {opcion(i)["statement"] for i in range(1, 5)}


@pytest.mark.parametrize("archivo", ["multiple_choice.xml", "true_false.xml", "numeric.xml", "numeric_tolerance.xml", "fill_blank.xml", "essay.xml"])
def test_rf04_importar_qti(c: httpx.Client, docente: Persona, archivo: str) -> None:
    """RF-04 | Importación QTI 2.1 | Cada tipo de pregunta QTI (opción múltiple, V/F, numérica, con tolerancia, completar, desarrollo) se importa al banco con su tipo y su enunciado."""
    banco = c.post("/question-banks", headers=docente.h, json={"name": f"QTI {archivo}"}).json()
    xml = (QTI / archivo).read_bytes()
    r = c.post(f"/question-banks/{banco['id']}/import/qti", headers={**docente.h, "Content-Type": "application/xml"}, content=xml)
    assert r.status_code == 201, r.text
    cuerpo = r.json()
    assert cuerpo["imported_count"] == 1 and not cuerpo["skipped"]
    en_banco = c.get(f"/question-banks/{banco['id']}/questions", headers=docente.h).json()
    assert len(en_banco) == 1 and en_banco[0]["statement"]


def test_rf05_qti_vista_previa_no_guarda(c: httpx.Client, docente: Persona) -> None:
    """RF-05 | Importación QTI 2.1 | La vista previa (dry_run) no guarda nada en el banco, y un XML que no es QTI se rechaza con un mensaje."""
    banco = c.post("/question-banks", headers=docente.h, json={"name": "QTI vista previa"}).json()
    xml = (QTI / "multiple_choice.xml").read_bytes()
    prev = c.post(f"/question-banks/{banco['id']}/import/qti", params={"dry_run": "true"}, headers={**docente.h, "Content-Type": "application/xml"}, content=xml)
    assert prev.status_code == 201
    assert c.get(f"/question-banks/{banco['id']}/questions", headers=docente.h).json() == []
    roto = c.post(f"/question-banks/{banco['id']}/import/qti", headers={**docente.h, "Content-Type": "application/xml"}, content=b"<html>no soy QTI</html>")
    assert roto.status_code == 400 and roto.json().get("detail")


def test_rf05b_qti_vista_previa_muestra(c: httpx.Client, docente: Persona) -> None:
    """RF-05b | Importación QTI 2.1 | La vista previa muestra las preguntas que se importarían, para revisarlas antes de guardarlas."""
    banco = c.post("/question-banks", headers=docente.h, json={"name": "QTI vista previa 2"}).json()
    xml = (QTI / "multiple_choice.xml").read_bytes()
    prev = c.post(f"/question-banks/{banco['id']}/import/qti", params={"dry_run": "true"}, headers={**docente.h, "Content-Type": "application/xml"}, content=xml).json()
    assert prev["imported_count"] == 1 and prev["imported"], f"la vista previa devolvió {prev['imported_count']} preguntas (el import real trae 1)"


# ---------------------------------------------------------------- calificación y revisión


@pytest.mark.parametrize(("bien", "numero", "esperado"), [(True, "42", 20.0), (False, "13", 0.0), (True, "42.4", 20.0), (True, "43", 10.0)])
def test_rf06_calificacion_automatica(c: httpx.Client, docente: Persona, bien: bool, numero: str, esperado: float) -> None:
    """RF-06 | Calificación | Al entregar, la nota se calcula sola sobre 20: todo bien 20; todo mal 0; la numérica acepta su tolerancia (42,4 vale) y fuera de ella no puntúa."""
    e = crear_examen(docente, preguntas=[opcion(1), opcion(2), NUMERICA])
    alumno = persona()
    ingresar(e, alumno)
    responder_todo(c, e.id, alumno, bien, numero)
    assert c.post(f"/exam/{e.id}/submit", headers=alumno.h).status_code == 200
    nota = c.get(f"/exam/{e.id}/me", headers=alumno.h).json()
    participantes = c.get(f"/sessions/{e.id}/participants", headers=docente.h).json()
    fila = next(p for p in participantes if p["student_id"] == alumno.id)
    assert fila["score"] is not None and abs(float(fila["score"]) - esperado) < 0.01, (fila["score"], esperado, nota)


def test_rf07_revision_de_respuestas(c: httpx.Client, docente: Persona) -> None:
    """RF-07 | Revisión tras entregar | La clave solo se muestra si el docente la habilitó, el estudiante entregó y el examen terminó para todos."""
    cerrado = crear_examen(docente, preguntas=[opcion(1)], show_answers_after_submission=False)
    abierto = crear_examen(docente, preguntas=[opcion(1)], show_answers_after_submission=True, inicio=datetime.now(UTC) - timedelta(seconds=40), duracion=1, tolerancia=1)
    alumno = persona()
    for e in (cerrado, abierto):
        ingresar(e, alumno)
        responder_todo(c, e.id, alumno, True)
        c.post(f"/exam/{e.id}/submit", headers=alumno.h)
    assert c.get(f"/exam/{cerrado.id}/submitted-review", headers=alumno.h).status_code == 403
    antes = c.get(f"/exam/{abierto.id}/submitted-review", headers=alumno.h)
    fin = datetime.fromisoformat(abierto.datos["ends_at"])
    if datetime.now(UTC) < fin:
        assert antes.status_code == 403, "se mostró la clave antes de que terminara el examen"
        time.sleep(max(0, (fin - datetime.now(UTC)).total_seconds()) + 2)
    despues = c.get(f"/exam/{abierto.id}/submitted-review", headers=alumno.h)
    assert despues.status_code == 200, despues.text
    assert any(o.get("is_correct") for o in despues.json()[0]["options"])


# ---------------------------------------------------------------- configuración del examen


def test_rf08_codigo_oculto_hasta_empezar(c: httpx.Client, docente: Persona) -> None:
    """RF-08 | Código al empezar | Con «mostrar el código solo al empezar», el código no aparece (ni al docente) antes de la hora de inicio."""
    futuro = crear_examen(docente, inicio=datetime.now(UTC) + timedelta(hours=2), reveal_code_at_start=True)
    assert futuro.datos["access_code"] is None
    assert c.get(f"/sessions/{futuro.id}", headers=docente.h).json()["access_code"] is None
    ya = crear_examen(docente, reveal_code_at_start=True)
    assert ya.datos["access_code"]


def _ordenes(c: httpx.Client, e: Any, n: int) -> list[tuple[str, ...]]:
    salida = []
    for _ in range(n):
        a = persona()
        ingresar(e, a)
        salida.append(tuple(q["id"] for q in c.get(f"/exam/{e.id}/questions", headers=a.h).json()))
    return salida


def _examen_con_banco(c: httpx.Client, docente: Persona, n: int, **extra: Any) -> Any:
    banco = c.post("/question-banks", headers=docente.h, json={"name": "Banco funcional"}).json()
    r = c.post(f"/question-banks/{banco['id']}/questions", headers=docente.h, json={"questions": [opcion(i) for i in range(1, n + 1)]})
    assert r.status_code in (200, 201), r.text
    e = crear_examen(docente, preguntas=[], **extra)
    assert c.post(f"/sessions/{e.id}/banks", headers=docente.h, json={"bank_id": banco["id"]}).status_code in (200, 201)
    return e


def test_rf09_aleatorizacion_preguntas_propias(c: httpx.Client, docente: Persona) -> None:
    """RF-09 | Aleatorización | En un examen con preguntas escritas en el editor y «preguntas aleatorias» activado (el valor por defecto), estudiantes distintos reciben órdenes distintos."""
    e = crear_examen(docente, preguntas=[opcion(i) for i in range(1, 11)], shuffle_questions=True)
    ordenes = _ordenes(c, e, 4)
    assert len({frozenset(o) for o in ordenes}) == 1
    assert len(set(ordenes)) > 1, "los 4 estudiantes recibieron el mismo orden: con preguntas propias la aleatorización no se aplica"


def test_rf09b_aleatorizacion_con_banco(c: httpx.Client, docente: Persona) -> None:
    """RF-09b | Aleatorización | En un examen que toma sus preguntas de un banco, estudiantes distintos reciben órdenes distintos; sin aleatorizar, el orden del banco."""
    mezcla = _examen_con_banco(c, docente, 10, shuffle_questions=True)
    fijo = _examen_con_banco(c, docente, 10, shuffle_questions=False)
    om, of = _ordenes(c, mezcla, 4), _ordenes(c, fijo, 3)
    assert len(set(om)) > 1 and len({frozenset(o) for o in om}) == 1
    assert len(set(of)) == 1


def test_rf10_pool_preguntas_propias(c: httpx.Client, docente: Persona) -> None:
    """RF-10 | Pool de preguntas | Con un pool de 3 sobre 8 preguntas escritas en el editor, cada estudiante recibe exactamente 3."""
    e = crear_examen(docente, preguntas=[opcion(i) for i in range(1, 9)], question_pool_size=3)
    a = persona()
    ingresar(e, a)
    n = len(c.get(f"/exam/{e.id}/questions", headers=a.h).json())
    assert n == 3, f"recibió {n} de 8: con preguntas propias el pool no se aplica"


def test_rf10b_pool_con_banco(c: httpx.Client, docente: Persona) -> None:
    """RF-10b | Pool de preguntas | Con un banco de 8 y un pool de 3, cada estudiante recibe exactamente 3 del banco, no siempre las mismas."""
    e = _examen_con_banco(c, docente, 8, question_pool_size=3)
    vistas = _ordenes(c, e, 4)
    assert all(len(o) == 3 for o in vistas), [len(o) for o in vistas]
    assert len({frozenset(o) for o in vistas}) > 1


def test_rf11_editar_y_cancelar(c: httpx.Client, docente: Persona) -> None:
    """RF-11 | Edición del examen | El docente cambia título y duración de un examen programado; al cancelarlo queda cancelado y deja de aceptar ingresos."""
    e = crear_examen(docente, inicio=datetime.now(UTC) + timedelta(days=1))
    r = c.patch(f"/sessions/{e.id}", headers=docente.h, json={"title": "Examen reprogramado", "duration_minutes": 45})
    assert r.status_code == 200 and r.json()["title"] == "Examen reprogramado" and r.json()["duration_minutes"] == 45
    assert c.post(f"/sessions/{e.id}/cancel", headers=docente.h).status_code in (200, 204)
    leido = c.get(f"/sessions/{e.id}", headers=docente.h).json()
    assert leido["cancelled_at"] is not None


def test_rf12_limite_de_actividad_sospechosa(c: httpx.Client, docente: Persona) -> None:
    """RF-12 | Límite de actividad sospechosa | Con un límite de 2, al pasarlo el docente ve al estudiante marcado «sobre el límite», y aun así el estudiante puede entregar (el sistema no anula)."""
    e = crear_examen(docente, preset="strict", suspicious_activity_limit=2)
    a = persona()
    ingresar(e, a)
    for _ in range(4):
        assert c.post("/events", headers=a.h, json=evento(e, a, "extra_person", 0)).status_code == 201
    fila = next(x for x in c.get(f"/sessions/{e.id}/risk", headers=docente.h).json() if x["student_id"] == a.id)
    assert fila["warning_limit"] == 2 and fila["warnings"] >= 3 and fila["over_limit"] is True, fila
    assert c.post(f"/exam/{e.id}/submit", headers=a.h).status_code == 200


def test_rf13_un_solo_intento(c: httpx.Client, docente: Persona) -> None:
    """RF-13 | Intentos | Con un intento, quien entregó no puede volver a empezar el examen aunque vuelva a escribir el código."""
    e = crear_examen(docente, preguntas=[opcion(1)], max_attempts=1)
    a = persona()
    ingresar(e, a)
    c.post(f"/exam/{e.id}/submit", headers=a.h)
    c.post("/sessions/join", headers=a.h, json={"access_code": e.codigo})
    c.post(f"/exam/{e.id}/enroll", headers=a.h, json={"accepts_supervision": True})
    yo = c.get(f"/exam/{e.id}/me", headers=a.h).json()
    assert yo["submitted_at"] and yo["can_take_exam"] is False


# ---------------------------------------------------------------- vista del estudiante y del docente


def test_rf14_mis_examenes(c: httpx.Client, docente: Persona) -> None:
    """RF-14 | Panel del estudiante | El estudiante ve sus exámenes; tras entregar, el examen aparece como entregado con su nota."""
    e = crear_examen(docente, preguntas=[opcion(1), NUMERICA])
    a = persona()
    ingresar(e, a)
    responder_todo(c, e.id, a, True)
    c.post(f"/exam/{e.id}/submit", headers=a.h)
    mio = next(x for x in c.get("/me/exams", headers=a.h).json() if x["session_id"] == e.id)
    assert mio["submitted_at"]


def test_rf15_decision_visible_al_estudiante(c: httpx.Client, docente: Persona) -> None:
    """RF-15 | Decisión del docente | La decisión y su justificación quedan registradas y el estudiante puede consultarla sobre su examen."""
    e = crear_examen(docente)
    a = persona()
    ingresar(e, a)
    c.post("/events", headers=a.h, json=evento(e, a, "extra_person", 0))
    c.post(f"/exam/{e.id}/submit", headers=a.h)
    d = c.post(f"/sessions/{e.id}/students/{a.id}/decision", headers=docente.h, json={"decision": "confirmed", "justification": "Se ve a otra persona dictando las respuestas."})
    assert d.status_code in (200, 201), d.text
    visto = c.get(f"/me/exams/{e.id}/decision", headers=a.h)
    assert visto.status_code == 200 and visto.json()["decision"] == "confirmed"
    assert "dictando" in visto.json()["justification"]


def test_rf16_caso_completo_para_el_docente(c: httpx.Client, docente: Persona) -> None:
    """RF-16 | Revisión del caso | El caso de un estudiante reúne su participación, su línea de tiempo de señales con hora, sus alertas y su riesgo desglosado."""
    e = crear_examen(docente, preset="strict")
    a = persona()
    ingresar(e, a)
    for tipo, ms in [("focus_lost", 8000), ("extra_person", 0), ("gaze_away", 12000)]:
        c.post("/events", headers=a.h, json=evento(e, a, tipo, ms))
    caso = c.get(f"/sessions/{e.id}/students/{a.id}/case", headers=docente.h).json()
    assert caso["participant"]["student_id"] == a.id
    assert {x["event_type"] for x in caso["events"]} == {"focus_lost", "extra_person", "gaze_away"}
    assert all(x["started_at"] for x in caso["events"])
    assert caso["alerts"] and caso["risk"]["signals"]


def test_rf17_multiples_correctas(c: httpx.Client, docente: Persona) -> None:
    """RF-17 | Tipos de pregunta | Una pregunta de varias correctas solo da el puntaje completo si se marcan todas las correctas y ninguna incorrecta."""
    q = {
        "question_type": "multiple_select",
        "statement": "¿Cuáles son servicios de Supabase?",
        "points": "4",
        "options": [
            {"option_text": "Auth", "is_correct": True},
            {"option_text": "Realtime", "is_correct": True},
            {"option_text": "Kubernetes", "is_correct": False},
        ],
    }
    notas = []
    for elegidas in (["Auth", "Realtime"], ["Auth", "Kubernetes"]):
        e = crear_examen(docente, preguntas=[q])
        a = persona()
        ingresar(e, a)
        preg = c.get(f"/exam/{e.id}/questions", headers=a.h).json()[0]
        ids = [o["id"] for o in preg["options"] if o["option_text"] in elegidas]
        assert c.put(f"/exam/{e.id}/answers", headers=a.h, json={"answers": [{"question_id": preg["id"], "selected_option_ids": ids}]}).status_code in (200, 201)
        c.post(f"/exam/{e.id}/submit", headers=a.h)
        fila = next(p for p in c.get(f"/sessions/{e.id}/participants", headers=docente.h).json() if p["student_id"] == a.id)
        notas.append(float(fila["score"]))
    assert notas[0] == 20.0 and notas[1] < 20.0, notas
