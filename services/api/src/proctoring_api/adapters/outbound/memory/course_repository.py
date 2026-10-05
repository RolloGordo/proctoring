"""Repositorio de cursos en memoria."""

from __future__ import annotations

import threading
from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import datetime
from uuid import UUID

from proctoring_api.domain.course import Course, CourseEnrollment


class InMemoryCourseRepository:
    """Implementacion de `CourseRepository` sobre diccionarios."""

    def __init__(self) -> None:
        self._courses: dict[UUID, Course] = {}
        #: (course_id, student_id) -> matricula. La misma clave unica que la tabla.
        self._enrollments: dict[tuple[UUID, UUID], CourseEnrollment] = {}
        self._lock = threading.Lock()

    def save(self, course: Course) -> None:
        with self._lock:
            self._courses[course.id] = course

    def find_by_id(self, course_id: UUID) -> Course | None:
        with self._lock:
            return self._courses.get(course_id)

    def list_by_teacher(self, teacher_id: UUID) -> Sequence[Course]:
        with self._lock:
            mine = [c for c in self._courses.values() if c.teacher_id == teacher_id]
        return sorted(mine, key=lambda c: c.created_at, reverse=True)

    def list_by_student(self, student_id: UUID) -> Sequence[Course]:
        with self._lock:
            ids = [e.course_id for e in self._enrollments.values() if e.student_id == student_id]
            courses = [self._courses[i] for i in ids if i in self._courses]
        return sorted(courses, key=lambda c: c.name.casefold())

    def enroll(self, course_id: UUID, student_id: UUID, enrolled_at: datetime) -> bool:
        with self._lock:
            key = (course_id, student_id)
            if key in self._enrollments:
                return False
            self._enrollments[key] = CourseEnrollment(
                course_id=course_id, student_id=student_id, enrolled_at=enrolled_at
            )
            return True

    def list_enrollments(self, course_id: UUID) -> Sequence[CourseEnrollment]:
        with self._lock:
            found = [e for e in self._enrollments.values() if e.course_id == course_id]
        return sorted(found, key=lambda e: e.enrolled_at)

    def count_enrollments(self, course_ids: Sequence[UUID]) -> Mapping[UUID, int]:
        wanted = set(course_ids)
        with self._lock:
            return dict(
                Counter(e.course_id for e in self._enrollments.values() if e.course_id in wanted)
            )
