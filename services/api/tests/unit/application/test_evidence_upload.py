"""Permiso de subida de evidencia."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from proctoring_api.adapters.outbound.memory.evidence_storage import InMemoryEvidenceStorage
from proctoring_api.application.use_cases.create_evidence_upload_url import (
    CreateEvidenceUploadUrl,
    EvidenceUploadRequest,
)
from proctoring_api.domain.errors import AuthorizationError, InvalidEventError
from proctoring_api.domain.evidence import EvidenceKind
from proctoring_api.domain.user import AuthenticatedUser, UserRole

SESSION = uuid4()
ANA = AuthenticatedUser(id=uuid4(), role=UserRole.STUDENT)
LUIS = AuthenticatedUser(id=uuid4(), role=UserRole.STUDENT)
DOCENTE = AuthenticatedUser(id=uuid4(), role=UserRole.TEACHER)

BUCKETS = {
    EvidenceKind.IMAGE: "evidences",
    EvidenceKind.AUDIO: "audio-segments",
    EvidenceKind.REFERENCE_FACE: "reference-faces",
}


@pytest.fixture
def storage() -> InMemoryEvidenceStorage:
    return InMemoryEvidenceStorage()


@pytest.fixture
def use_case(storage: InMemoryEvidenceStorage) -> CreateEvidenceUploadUrl:
    return CreateEvidenceUploadUrl(storage, BUCKETS)


def a_request(
    kind: EvidenceKind = EvidenceKind.IMAGE,
    extension: str = "jpg",
    student_id: UUID | None = None,
) -> EvidenceUploadRequest:
    return EvidenceUploadRequest(
        session_id=SESSION,
        student_id=student_id or ANA.id,
        kind=kind,
        extension=extension,
    )


class TestPath:
    def test_follows_the_agreed_structure(self, use_case: CreateEvidenceUploadUrl) -> None:
        # {session_id}/{student_id}/{uuid}.{ext}: tener sesion y estudiante en el
        # prefijo permite borrar la evidencia de un examen con un solo prefijo, y
        # hace evidente de quien es cada archivo al auditarlo.
        upload = use_case.execute(a_request())

        prefix, _, filename = upload.path.rpartition("/")
        assert prefix == f"{SESSION}/{ANA.id}"
        assert filename.endswith(".jpg")
        UUID(filename.removesuffix(".jpg"))  # el nombre es un uuid valido

    def test_each_request_gets_its_own_name(self, use_case: CreateEvidenceUploadUrl) -> None:
        assert use_case.execute(a_request()).path != use_case.execute(a_request()).path

    def test_extension_is_normalised(self, use_case: CreateEvidenceUploadUrl) -> None:
        assert use_case.execute(a_request(extension=".JPG")).path.endswith(".jpg")


class TestBucket:
    @pytest.mark.parametrize(
        ("kind", "extension", "bucket"),
        [
            (EvidenceKind.IMAGE, "jpg", "evidences"),
            (EvidenceKind.AUDIO, "webm", "audio-segments"),
            (EvidenceKind.REFERENCE_FACE, "png", "reference-faces"),
        ],
    )
    def test_each_kind_goes_to_its_bucket(
        self,
        use_case: CreateEvidenceUploadUrl,
        storage: InMemoryEvidenceStorage,
        kind: EvidenceKind,
        extension: str,
        bucket: str,
    ) -> None:
        use_case.execute(a_request(kind=kind, extension=extension))

        assert storage.issued[0][0] == bucket


class TestExtensions:
    @pytest.mark.parametrize("extension", ["jpg", "jpeg", "png", "webp"])
    def test_accepted_images(self, use_case: CreateEvidenceUploadUrl, extension: str) -> None:
        assert use_case.execute(a_request(extension=extension)).path

    @pytest.mark.parametrize("extension", ["webm", "wav", "ogg", "mp3"])
    def test_accepted_audio(self, use_case: CreateEvidenceUploadUrl, extension: str) -> None:
        assert use_case.execute(a_request(EvidenceKind.AUDIO, extension)).path

    def test_rejects_an_extension_the_bucket_would_refuse(
        self, use_case: CreateEvidenceUploadUrl
    ) -> None:
        # Los buckets tienen allowed_mime_types en la migracion. Dar una URL para
        # un tipo que el bucket rechaza haria fallar la subida lejos de su causa.
        with pytest.raises(InvalidEventError, match="no permitida"):
            use_case.execute(a_request(extension="exe"))

    def test_audio_extension_is_not_valid_for_an_image(
        self, use_case: CreateEvidenceUploadUrl
    ) -> None:
        with pytest.raises(InvalidEventError, match="no permitida"):
            use_case.execute(a_request(EvidenceKind.IMAGE, "webm"))

    def test_nothing_is_issued_when_rejected(
        self, use_case: CreateEvidenceUploadUrl, storage: InMemoryEvidenceStorage
    ) -> None:
        with pytest.raises(InvalidEventError):
            use_case.execute(a_request(extension="exe"))

        assert storage.issued == []


class TestAuthorization:
    def test_a_student_uploads_their_own(self, use_case: CreateEvidenceUploadUrl) -> None:
        assert use_case.execute(a_request(), actor=ANA).path

    def test_a_student_cannot_upload_for_another(
        self, use_case: CreateEvidenceUploadUrl, storage: InMemoryEvidenceStorage
    ) -> None:
        # Si no, cualquiera consigue permiso de escritura en la carpeta de otro
        # estudiante y planta una captura falsa que termina delante de un docente.
        with pytest.raises(AuthorizationError, match="otro estudiante"):
            use_case.execute(a_request(student_id=LUIS.id), actor=ANA)

        assert storage.issued == []

    def test_a_teacher_cannot_upload(self, use_case: CreateEvidenceUploadUrl) -> None:
        with pytest.raises(AuthorizationError, match="docente"):
            use_case.execute(a_request(), actor=DOCENTE)

    def test_without_actor_nothing_is_checked(self, use_case: CreateEvidenceUploadUrl) -> None:
        assert use_case.execute(a_request(student_id=LUIS.id), actor=None).path
