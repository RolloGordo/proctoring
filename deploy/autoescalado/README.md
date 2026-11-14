# Autoescalado horizontal de la API

Pedido del profesor en la reunión del 07/11: que el sistema levante servicios según la carga. Las
réplicas de la API ya escalaban en horizontal (ADR-0011), pero su número lo fijaba una persona. Con
esto lo decide la carga.

## Cómo decide

Cada 15 s mide la CPU de cada réplica (`docker stats`, 100 % = un núcleo, que es el tope de cada una):

| Regla | Valor | Por qué |
|---|---|---|
| Sube una réplica | CPU media > 70 % en las últimas 3 mediciones (45 s) | una ráfaga corta no basta |
| Baja una réplica | CPU < 25 % en todas las últimas 12 mediciones (3 min) | bajar con prisa y volver a subir es peor que sobrar un rato |
| Espera tras subir | 45 s | la réplica nueva arranca y el balanceador la incluye antes de volver a medir |
| Espera tras bajar | 120 s | |
| Mínimo / máximo | 2 / 5 | con 2 sigue habiendo servicio si una réplica cae; 5 es lo que cabe en 6 vCPU dejando sitio al worker de IA |

La política es una función pura (`Estado.decidir`) con sus pruebas en `test_autoescalador.py`:

```bash
uv run --no-project --with pytest python -m pytest deploy/autoescalado
```

## Dónde corre

En el VPS, como servicio de systemd (`proctoring-autoescalado.service`). Escala el servicio Swarm de la
API con `docker service scale`; Traefik reparte entre las réplicas nuevas sin configuración extra.

El número de réplicas que guarda Dokploy (3) no cambia: tras un redespliegue la API arranca con 3 y el
autoescalador la ajusta en los siguientes minutos.

Cada medición queda en `/home/ubuntu/autoescalado/produccion.csv`: hora, réplicas, CPU media y máxima,
y la decisión.

## Lo que no hace

- **No añade máquinas.** Todas las réplicas comparten los 6 vCPU del VPS. Pasar de ~300 estudiantes a
  1.000 con buen tiempo de respuesta necesita un segundo nodo (`docs/carga/vps-contabo-2026-11-13.md`).
- **No escala el worker de IA**, que tiene 2 réplicas fijas: cada una carga Whisper `small` en memoria
  (~500 MB) y tarda en arrancar. La cola de Redis absorbe los picos.
