"""SEC-07: un token rechazado no cuenta detalles internos en la respuesta."""

from __future__ import annotations

import base64
import json

import jwt
import pytest

from proctoring_api.adapters.outbound.supabase.token_verifier import SupabaseTokenVerifier
from proctoring_api.domain.errors import AuthenticationError


def _b64(datos: dict[str, object]) -> str:
    return base64.urlsafe_b64encode(json.dumps(datos).encode()).rstrip(b"=").decode()


@pytest.fixture
def verificador() -> SupabaseTokenVerifier:
    return SupabaseTokenVerifier("https://abc.supabase.co")


def test_un_token_ilegible_no_cuenta_por_que(verificador: SupabaseTokenVerifier) -> None:
    with pytest.raises(AuthenticationError) as error:
        verificador.verify("abc.def.ghi")

    # Antes: «Token invalido: Invalid header string: 'utf-8' codec can't decode…»
    assert str(error.value) == "Sesion invalida; vuelve a iniciar sesion"


def test_un_token_sin_clave_conocida_no_parece_un_fallo_pasajero(
    verificador: SupabaseTokenVerifier, monkeypatch: pytest.MonkeyPatch
) -> None:
    def sin_clave(_token: str) -> None:
        raise jwt.PyJWKClientError('Unable to find a signing key that matches: "None"')

    monkeypatch.setattr(verificador._jwks_client, "get_signing_key_from_jwt", sin_clave)
    falso = f"{_b64({'alg': 'none'})}.{_b64({'sub': 'x'})}."

    with pytest.raises(AuthenticationError) as error:
        verificador.verify(falso)

    # Antes: «No se pudo verificar el token en este momento».
    assert str(error.value) == "Sesion invalida; vuelve a iniciar sesion"


def test_si_supabase_no_responde_se_dice(
    verificador: SupabaseTokenVerifier, monkeypatch: pytest.MonkeyPatch
) -> None:
    def sin_red(_token: str) -> None:
        raise jwt.PyJWKClientConnectionError("timeout")

    monkeypatch.setattr(verificador._jwks_client, "get_signing_key_from_jwt", sin_red)

    with pytest.raises(AuthenticationError, match="en este momento"):
        verificador.verify("a.b.c")
