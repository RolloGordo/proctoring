"""Los adaptadores usan columnas que existen de verdad en la migracion.

Este es el fallo que de verdad nos puede morder: alguien renombra una columna en
`supabase/migrations`, nadie toca la API, todo sigue en verde porque las pruebas
usan un cliente de mentira, y el fallo aparece en la demo con PostgREST
devolviendo un 400.

Aqui se lee el SQL real y se comprueba contra el. Si Limay cambia el esquema, esta
prueba se pone roja en su propio pull request.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from proctoring_api.adapters.outbound.supabase import alert_repository, event_repository

MIGRATION = (
    Path(__file__).resolve().parents[5]
    / "supabase"
    / "migrations"
    / "20261003120000_initial_schema.sql"
)

#: `  nombre_columna tipo ...` al principio de linea dentro de un create table.
COLUMN = re.compile(r"^\s{2}([a-z_]+)\s+[a-z]", re.IGNORECASE)
#: Lineas que son restricciones, no columnas.
NOT_A_COLUMN = ("primary", "unique", "foreign", "check", "constraint")


def columns_of(table: str) -> set[str]:
    """Columnas declaradas para `public.<table>` en la migracion inicial."""
    sql = MIGRATION.read_text(encoding="utf-8")
    match = re.search(rf"create table public\.{table} \((.*?)^\);", sql, re.DOTALL | re.MULTILINE)
    assert match, f"No se encontro la tabla {table} en {MIGRATION.name}"

    columns = set()
    for line in match.group(1).splitlines():
        found = COLUMN.match(line)
        if found and found.group(1).lower() not in NOT_A_COLUMN:
            columns.add(found.group(1))
    return columns


def selected_columns(constant: str) -> set[str]:
    return {column.strip() for column in constant.split(",")}


def test_the_migration_file_is_where_we_think() -> None:
    assert MIGRATION.is_file(), f"No existe {MIGRATION}"


class TestEventsTable:
    def test_the_adapter_selects_existing_columns(self) -> None:
        assert selected_columns(event_repository.COLUMNS) <= columns_of("events")

    def test_the_adapter_writes_existing_columns(self) -> None:
        from datetime import UTC, datetime
        from uuid import uuid4

        from proctoring_api.domain.event import EventType, ProctoringEvent

        row = event_repository._to_row(
            ProctoringEvent.create(
                session_id=uuid4(),
                student_id=uuid4(),
                event_type=EventType.FOCUS_LOST,
                started_at=datetime(2026, 10, 3, tzinfo=UTC),
            )
        )

        assert set(row) <= columns_of("events")


class TestAlertsTable:
    def test_the_adapter_selects_existing_columns(self) -> None:
        assert selected_columns(alert_repository.COLUMNS) <= columns_of("alerts")

    def test_the_adapter_writes_existing_columns(self) -> None:
        from datetime import UTC, datetime
        from uuid import uuid4

        from proctoring_api.domain.alert import Alert
        from proctoring_api.domain.severity import Severity

        row = alert_repository._to_row(
            Alert(
                id=uuid4(),
                event_id=uuid4(),
                session_id=uuid4(),
                student_id=uuid4(),
                severity=Severity.HIGH,
                reason="motivo",
                created_at=datetime(2026, 10, 3, tzinfo=UTC),
            )
        )

        assert set(row) <= columns_of("alerts")


@pytest.mark.parametrize(
    ("table", "used"),
    [
        ("profiles", {"id", "role"}),
        ("questions", {"id", "session_id"}),
    ],
)
def test_lookup_adapters_use_existing_columns(table: str, used: set[str]) -> None:
    assert used <= columns_of(table)


def test_event_type_enum_matches_the_database() -> None:
    """Los 9 valores del enum de PostgreSQL y los del dominio son los mismos.

    Si divergen, un POST valido para la API falla al insertar con un error de
    enum que no dice nada util.
    """
    from proctoring_api.domain.event import EventType

    sql = MIGRATION.read_text(encoding="utf-8")
    match = re.search(r"create type public\.event_type as enum \((.*?)\);", sql, re.DOTALL)
    assert match

    in_database = set(re.findall(r"'([a-z_]+)'", match.group(1)))
    assert in_database == {event_type.value for event_type in EventType}


def test_alert_severity_enum_matches_the_database() -> None:
    from proctoring_api.domain.severity import Severity

    sql = MIGRATION.read_text(encoding="utf-8")
    match = re.search(r"create type public\.alert_severity as enum \((.*?)\);", sql, re.DOTALL)
    assert match

    assert set(re.findall(r"'([a-z_]+)'", match.group(1))) == {s.value for s in Severity}


def test_user_role_enum_matches_the_database() -> None:
    from proctoring_api.domain.user import UserRole

    sql = MIGRATION.read_text(encoding="utf-8")
    match = re.search(r"create type public\.user_role as enum \((.*?)\);", sql, re.DOTALL)
    assert match

    assert set(re.findall(r"'([a-z_]+)'", match.group(1))) == {r.value for r in UserRole}


class TestExamSessionsTable:
    def test_the_adapter_selects_existing_columns(self) -> None:
        from proctoring_api.adapters.outbound.supabase import exam_session_repository

        assert selected_columns(exam_session_repository.COLUMNS) <= columns_of("exam_sessions")

    def test_the_adapter_writes_existing_columns(self) -> None:
        from datetime import UTC, datetime
        from uuid import uuid4

        from proctoring_api.adapters.outbound.supabase import exam_session_repository
        from proctoring_api.domain.exam_session import ExamSession

        row = exam_session_repository._to_row(
            ExamSession.create(
                teacher_id=uuid4(),
                title="Examen",
                starts_at=datetime(2026, 10, 10, tzinfo=UTC),
                duration_minutes=60,
            )
        )

        assert set(row) <= columns_of("exam_sessions")

    def test_session_modules_columns(self) -> None:
        assert {"session_id", "module", "enabled", "settings"} <= columns_of("session_modules")


@pytest.mark.parametrize(
    ("enum_name", "domain_values"),
    [
        ("session_status", "SessionStatus"),
        ("supervision_preset", "SupervisionPreset"),
        ("supervision_module", "SupervisionModule"),
    ],
)
def test_session_enums_match_the_database(enum_name: str, domain_values: str) -> None:
    """Los enums del dominio y los de PostgreSQL son los mismos.

    `supervision_module` importa especialmente: si el dominio activa un modulo
    que el enum de la base no conoce, crear la sesion falla al insertar en
    session_modules con un error que no dice nada util.
    """
    import proctoring_api.domain.exam_session as exam_session

    sql = MIGRATION.read_text(encoding="utf-8")
    match = re.search(rf"create type public\.{enum_name} as enum \((.*?)\);", sql, re.DOTALL)
    assert match, f"No se encontro el enum {enum_name}"

    in_database = set(re.findall(r"'([a-z_]+)'", match.group(1)))
    in_domain = {member.value for member in getattr(exam_session, domain_values)}

    assert in_database == in_domain
