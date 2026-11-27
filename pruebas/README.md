# Baterías de pruebas (27/11/2026)

Ocho tipos de prueba, cada uno con su informe en PDF generado desde los resultados de la corrida
(`pruebas/informes/`). Ninguna cifra de un informe se escribe a mano.

| Carpeta | Tipo | Contra qué corre |
|---|---|---|
| (suites de cada servicio) | Unitarias | Cada componente aislado: `services/api`, `services/ai`, `apps/web`, `apps/desktop`, `deploy/autoescalado` |
| `caja_negra/` | Caja negra | La API desde fuera: particiones, valores límite, tablas de decisión, estados |
| `e2e/` | Extremo a extremo | Navegadores reales (`test_e2e_web.py`) y la app Electron real (`escritorio.mjs`) |
| `integracion/` | Integración | Las fronteras reales: Auth, PostgreSQL/RLS, Storage, Redis, workers de IA, Realtime |
| `humo/` | Humo | **Producción**, solo lectura: se repite tras cada despliegue |
| `funcional/` | Funcionales | Cada funcionalidad contra su requisito |
| `caja_blanca/` | Caja blanca | Caminos básicos de las reglas críticas; con cobertura de ramas, radon y mutmut |
| (agentes de IA) | Exploratorias con agentes | Tres agentes autónomos con perfiles distintos sobre el entorno aislado |

Todo lo que escribe datos corre contra el **entorno aislado** de `loadtests/` (Supabase local, réplicas
de la API, Redis, workers de IA), nunca contra producción: crea sus propias cuentas con
`comun.persona()`. Cada prueba documenta en su docstring `ID | técnica | resultado esperado`, y
`conftest.py` lo vuelca a JSON (`RESULTADOS=…`) para el informe.

```bash
# entorno aislado arriba (loadtests/README.md), desde pruebas/
RESULTADOS=caja-negra.json uv run --project ../loadtests --with pytest python -m pytest caja_negra
RESULTADOS=integracion.json uv run --project ../loadtests --with pytest --with websockets python -m pytest integracion
RESULTADOS=funcional.json uv run --project ../loadtests --with pytest python -m pytest funcional
CAPTURAS=capturas RESULTADOS=e2e-web.json uv run --project ../loadtests --with playwright --with pytest python -m pytest e2e/test_e2e_web.py

# producción, solo lectura
uv run --no-project --with pytest --with httpx --with websockets --with playwright python -m pytest humo

# caja blanca, con el entorno de la API
cd ../services/api && uv run pytest ../../pruebas/caja_blanca --cov=proctoring_api.domain --cov-branch
```
