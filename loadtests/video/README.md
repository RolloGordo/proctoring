# Carga con video (pedido del 14/11/2026)

El profesor pidió una prueba con **video**: grabar a alguien con comportamientos anómalos y
transmitirlo muchas veces hacia el servidor, como si fueran muchos estudiantes a la vez.

Nuestro sistema no manda video continuo al servidor (es una regla del proyecto). Lo que sí viaja:

- las **señales** que detectan MediaPipe y el VAD en el navegador de cada estudiante;
- las **capturas** de evidencia y los **fragmentos de voz**, a Storage;
- los **fotogramas en vivo** (`live_monitoring`) que ve el docente, por Supabase Realtime. Esto
  sí es streaming: JPEG a 8 fps mientras el docente mira la cámara.

Por eso la prueba usa **navegadores reales** (Chromium con Playwright) cuya cámara es la
grabación. No se simula nada: cada navegador inicia sesión, entra al examen y la supervisión
corre igual que en el equipo de un estudiante.

## 1. Grabar el video (lo hace una persona del equipo)

Con la webcam, de frente, a la distancia de un examen, **90 segundos**, en este orden:

| Segundo | Qué hacer | Qué debería detectar |
|---|---|---|
| 0–15 | Mirar la pantalla, quieto, hombros a la vista | nada (control) |
| 15–25 | Mirar a un lado (izquierda), sostenido | mirada fuera |
| 25–30 | Volver a mirar la pantalla | — |
| 30–42 | Salir del cuadro (levantarse) | rostro ausente |
| 42–50 | Volver a sentarse | — |
| 50–62 | Otra persona entra al cuadro y se queda | persona adicional |
| 62–70 | La otra persona se va | — |
| 70–80 | Mostrar un celular a la cámara | objeto prohibido |
| 80–90 | Hablar en voz alta, como dictando una pregunta | voz detectada |

Sirve un `.mp4` del celular o de la cámara de Windows. Se convierte así (en el VPS hay ffmpeg):

```bash
ffmpeg -i grabacion.mp4 -vf "scale=640:360,fps=15" -pix_fmt yuv420p video/anomalias.y4m
ffmpeg -i grabacion.mp4 -vn -ac 1 -ar 48000 video/voz.wav
```

El `.y4m` es grande (~300 MB por 90 s a 640×360): **no se sube al repositorio**.

## 2. Levantar el entorno aislado

En el VPS (`~/levantar-video.sh` hace todo esto):

```bash
supabase start && supabase db reset --local
docker compose -f loadtests/docker-compose.carga.yml -p carga up -d --build --scale api=3
uv run python preparar.py datos --examenes 1 --por-examen 20 --docentes 1
bash video/web-local.sh          # la web en 127.0.0.1:5173, contra la API y Supabase locales
uv run --with playwright python -m playwright install --with-deps chromium
```

## 3. Correr

```bash
uv run --with playwright python video/carga_video.py --estudiantes 10 --minutos 4 \
    --video video/anomalias.y4m --audio video/voz.wav
```

Sin `--video` usa la cámara de prueba de Chromium, que no tiene rostro: solo sirve para probar
el arnés (produce «rostro ausente»).

## Qué mide

- **Señales por tipo** que llegaron al servidor: con la grabación de arriba, cada vuelta del
  video debería producir una de cada tipo por estudiante. Cuántas llegan frente a cuántas
  debían es la tasa de detección.
- **Detección → alerta**: desde que el detector cerró la señal en el navegador hasta que la
  alerta quedó guardada. La meta del proyecto es < 5 s.
- **`POST /events`** desde el navegador: p50, p95 y errores.
- **FPS que recibe el docente** en la cuadrícula de cámaras en vivo (envían a 8 fps).

Resultado en `resultados/video.json`.

## Límite que hay que tener presente

Cada navegador corre MediaPipe y el VAD, que es CPU de verdad: en el VPS (6 vCPU compartidos con
producción) caben del orden de 10 a 20 estudiantes simulados. Para 60 hay que repartir los
navegadores entre varias máquinas (por ejemplo, los PC del equipo) apuntando al mismo servidor.
