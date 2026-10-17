"""Cursos y matriculas sobre `public.courses` y `public.course_enrollments`."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any, cast
from uuid import UUID

from supabase import Client

from proctoring_api.domain.course import Course, CourseEnrollment

COURSES_TABLE = "courses"
ENROLLMENTS_TABLE = "course_enrollments"
COLUMNS = "id, teacher_id, name, section, created_at"


class SupabaseCourseRepository:
    """Implementacion de `CourseRepository` contra PostgreSQL via PostgREST."""

    def __init__(self, client: Client) -> None:
        self._client = client

    def save(self, course: Course) -> None:
        self._client.table(COURSES_TABLE).insert(
            {
                "id": str(course.id),
                "teacher_id": str(course.teacher_id),
                "name": course.name,
                "section": course.section,
                "created_at": course.created_at.isoformat(),
            }
        ).execute()

    def find_by_id(self, course_id: UUID) -> Course | None:
        response = (
            self._client.table(COURSES_TABLE)
            .select(COLUMNS)
            .eq("id", str(course_id))
            .limit(1)
            .execute()
        )
        rows = cast("list[dict[str, Any]]", response.data)
        return _to_course(rows[0]) if rows else None

    def list_by_teacher(self, teacher_id: UUID) -> Sequence[Course]:
        response = (
            self._client.table(COURSES_TABLE)
            .select(COLUMNS)
            .eq("teacher_id", str(teacher_id))
            .order("created_at", desc=True)
            .execute()
        )
        return [_to_course(row) for row in cast("list[dict[str, Any]]", response.data)]

    def list_by_student(self, student_id: UUID) -> Sequence[Course]:
        enrolled = (
            self._client.table(ENROLLMENTS_TABLE)
            .select("course_id")
            .eq("student_id", str(student_id))
            .execute()
        )
        ids = [row["course_id"] for row in cast("list[dict[str, Any]]", enrolled.data)]
        if not ids:
            return []

        response = (
            self._client.table(COURSES_TABLE)
            .select(COLUMNS)
            .in_("id", ids)
            .order("name", desc=False)
            .execute()
        )
        return [_to_course(row) for row in cast("list[dict[str, Any]]", response.data)]

    def enroll(self, course_id: UUID, student_id: UUID, enrolled_at: datetime) -> bool:
        existing = (
            self._client.table(ENROLLMENTS_TABLE)
            .select("course_id")
            .eq("course_id", str(course_id))
            .eq("student_id", str(student_id))
            .limit(1)
            .execute()
        )
        if cast("list[dict[str, Any]]", existing.data):
            return False

        self._client.table(ENROLLMENTS_TABLE).insert(
            {
                "course_id": str(course_id),
                "student_id": str(student_id),
                "enrolled_at": enrolled_at.isoformat(),
            }
        ).execute()
        return True

    def list_enrollments(self, course_id: UUID) -> Sequence[CourseEnrollment]:
        response = (
            self._client.table(ENROLLMENTS_TABLE)
            .select("course_id, student_id, enrolled_at")
            .eq("course_id", str(course_id))
            .order("enrolled_at", desc=False)
            .execute()
        )
        return [
            CourseEnrollment(
                course_id=UUID(row["course_id"]),
                student_id=UUID(row["student_id"]),
                enrolled_at=datetime.fromisoformat(row["enrolled_at"]),
            )
            for row in cast("list[dict[str, Any]]", response.data)
        ]

    def count_enrollments(self, course_ids: Sequence[UUID]) -> Mapping[UUID, int]:
        if not course_ids:
            return {}

        # Solo la columna del curso, de todos a la vez: una consulta para todo el
        # listado y no una por curso.
        response = (
            self._client.table(ENROLLMENTS_TABLE)
            .select("course_id")
            .in_("course_id", [str(i) for i in course_ids])
            .execute()
        )
        rows = cast("list[dict[str, Any]]", response.data)
        return dict(Counter(UUID(row["course_id"]) for row in rows))


def _to_course(row: dict[str, Any]) -> Course:
    return Course(
        id=UUID(row["id"]),
        teacher_id=UUID(row["teacher_id"]),
        name=row["name"],
        section=row.get("section"),
        created_at=datetime.fromisoformat(row["created_at"]),
    )
