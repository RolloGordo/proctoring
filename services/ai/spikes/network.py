"""Use OS trust roots for model downloads without disabling TLS validation."""

import os
import ssl


def configure_model_downloads() -> None:
    # Route downloads through the configured HTTP client, including large files.
    os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
    import httpx
    import truststore
    from huggingface_hub import set_client_factory

    def client_factory() -> httpx.Client:
        return httpx.Client(
            verify=truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT),
            follow_redirects=True,
            timeout=120,
        )

    set_client_factory(client_factory)
