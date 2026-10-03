# Control de silencio de SP-007

`results/silence.json` registra una ejecución real con `base` sobre tres segundos
de silencio digital. No contiene voz humana ni sintética. El audio no se guarda
en Git; el siguiente código reproduce sus bytes con la biblioteca estándar de
Python. Ejecutarlo desde `services/ai`:

```python
from pathlib import Path
import wave

folder = Path("datasets/controls")
folder.mkdir(parents=True, exist_ok=True)
with wave.open(str(folder / "silence.wav"), "wb") as audio:
    audio.setnchannels(1)
    audio.setsampwidth(2)
    audio.setframerate(16000)
    audio.writeframes(b"\x00\x00" * 16000 * 3)
(folder / "silence.txt").write_text("", encoding="utf-8")
```

SHA-256 esperado del WAV:
`d303811b8c84619667cd0501342f84ec6cbe69f7aa3856dcf52fabda374c92b8`.
La prueba `test_silence_control_can_be_recreated_from_documented_parameters`
verifica este hash sin descargar modelos. Para una nueva ejecución:

```console
uv run python -m spikes.transcribe datasets/controls/silence.wav --model base --reference datasets/controls/silence.txt --output results/silence-local.json --offline
```

El modo `--offline` requiere que `base` ya esté descargado. La referencia vacía
produce WER `null`: este control observa posibles palabras inventadas, no mide
exactitud de transcripción ni valida detección de fraude.
