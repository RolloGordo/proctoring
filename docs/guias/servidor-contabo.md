# Servidor de producción en Contabo

Desde el 11/11/2026 la API y el worker de IA corren en un VPS propio (decisión de la reunión del
07/11 con el profesor, para poder escalar y medir con carga real). Render queda como respaldo hasta
terminar el corte. La web sigue en Vercel y los datos en Supabase Cloud.

| | |
|---|---|
| Plan | Contabo Cloud VPS 6: 6 vCPU, 12 GB, 200 GB SSD, EE. UU. Este. Mes a mes |
| Sistema | Ubuntu 24.04, Docker 28 en Swarm, Dokploy v0.31 (Traefik en 80/443) |
| API | `https://api.86-48-18-81.sslip.io` — 3 réplicas, 1 CPU y 768 MB cada una |
| Worker de IA | 2 réplicas, 2 CPU y 2 GB cada una. Whisper `small`, similitud ONNX int8, motor facial OpenCV |
| Redis | 1 instancia interna, con contraseña. Cola de trabajos y límite de peticiones compartido |

## Qué se despliega y desde dónde

Dokploy construye desde este repositorio con los Dockerfile de `services/api` y `services/ai`.
El worker se construye con `PERFIL=ligero` y `ASR_MODELO=small`: el perfil ligero no lleva torch ni
insightface, y con `small` pide ~1,1 GB en vez de los 1,7 GB del completo.

Las réplicas se actualizan una a una, arrancando la nueva antes de parar la vieja (`start-first`), y
si la nueva falla se vuelve atrás sola.

## Seguridad del servidor

- SSH solo con llave, usuario `ubuntu`; sin contraseña ni root. `fail2ban` y `auditd` activos.
- Firewall: solo 22, 80 y 443. Comprobado desde fuera: 3000, 6379, 8000, 8001, 5432 y los puertos de
  Swarm están cerrados.
- **El panel de Dokploy (3000) no se abre a internet.** Docker se salta `ufw`, así que lo cierra una
  regla en la cadena `DOCKER-USER` (`proctoring-firewall.service`). Se entra por túnel:
  `ssh -L 3000:localhost:3000 ubuntu@86.48.18.81` y luego `http://localhost:3000`.
- HTTPS con Let's Encrypt, HTTP redirige a HTTPS, TLS 1.1 rechazado. Traefik añade HSTS,
  `X-Content-Type-Options`, `X-Frame-Options` y quita la cabecera `Server`.
- Traefik pasa la IP real del cliente y la API solo se la cree a él (`TRUSTED_PROXIES`), así que el
  límite de peticiones cuenta por persona y no por proxy.
- Los secretos viven en Dokploy y en archivos `600` del servidor. Ninguno está en el repositorio.
- Actualizaciones de seguridad automáticas; los logs de los contenedores rotan (20 MB × 3).

## Lo que todavía no tiene

- **Respaldo:** no hay datos propios en el VPS (están en Supabase y GitHub); se reconstruye entero.
- **Un solo servidor:** si cae, cae la API. Dokploy admite sumar un segundo nodo.
- **Despliegue automático al hacer merge:** el webhook de Dokploy vive en el panel, que está cerrado.
  Hoy se despliega desde el panel o por su API a través de SSH.
