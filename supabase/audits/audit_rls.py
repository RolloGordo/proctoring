"""SPEC-006/J5: verifica aislamiento RLS con una clave publicable y JWT estudiante.

Solo ejecutar contra un proyecto autorizado con datos de prueba. La escritura
requiere --allow-write y se ejecuta con payload deliberadamente falsificado.
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

import httpx


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default=os.getenv('SUPABASE_URL'))
    parser.add_argument('--publishable-key', default=os.getenv('SUPABASE_PUBLISHABLE_KEY'))
    parser.add_argument('--student-token', default=os.getenv('AUDIT_STUDENT_JWT'))
    parser.add_argument('--student-id', required=True, help='ID del alumno autenticado')
    parser.add_argument('--other-student-id', required=True)
    parser.add_argument('--other-participant-id', required=True)
    parser.add_argument('--session-id', required=True)
    parser.add_argument('--allow-write', action='store_true', help='Solamente entorno de prueba')
    parser.add_argument('--output', type=Path, default=Path('supabase/audits/results/rls.json'))
    args = parser.parse_args()
    if not args.url or not args.publishable_key or not args.student_token:
        parser.error('Faltan SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY o AUDIT_STUDENT_JWT')
    if args.student_id == args.other_student_id:
        parser.error('Los dos estudiantes deben ser distintos')
    base = args.url.rstrip('/') + '/rest/v1/'
    headers = {
        'apikey': args.publishable_key,
        'Authorization': f'Bearer {args.student_token}',
        'Accept': 'application/json',
    }
    checks = {}

    def check_read(name: str, table: str, **params: str) -> None:
        with httpx.Client(headers=headers, timeout=15) as client:
            try:
                response = client.get(base + quote(table), params={'select': '*', **params})
                safe_rows = response.json() if response.status_code == 200 else None
                # No almacenar respuestas, datos personales ni tokens en el reporte.
                count = len(safe_rows) if isinstance(safe_rows, list) else None
                checks[name] = {
                    'http_status': response.status_code,
                    'returned_rows': count,
                    'pass': response.status_code in (200, 401, 403) and (count == 0 or count is None),
                }
            except httpx.HTTPError as exc:
                checks[name] = {'pass': False, 'error_type': type(exc).__name__}

    check_read('events_other_student', 'events', student_id='eq.' + args.other_student_id)
    check_read('answers_other_student', 'answers', participant_id='eq.' + args.other_participant_id)
    # La columna is_correct se guarda en question_options, no en questions.
    check_read('question_options_is_correct', 'question_options', select='is_correct')
    # Se permite leer decisiones propias; siguen ocultas las de otro estudiante.
    check_read('decisions_other_student', 'decisions', student_id='eq.' + args.other_student_id)
    if args.allow_write:
        payload = {
            'session_id': args.session_id, 'student_id': args.other_student_id,
            'event_type': 'focus_lost', 'started_at': datetime.now(timezone.utc).isoformat(),
            'duration_ms': 1000, 'metadata': {'source': 'spec006-audit'},
        }
        with httpx.Client(headers={**headers, 'Content-Type': 'application/json', 'Prefer': 'return=representation'}, timeout=15) as client:
            try:
                response = client.post(base + 'events', json=payload)
                checks['forge_event_as_other_student'] = {'http_status': response.status_code, 'pass': response.status_code in (401, 403)}
                # La inserción exitosa indica fuga y exige limpieza manual en el entorno de prueba.
            except httpx.HTTPError as exc:
                checks['forge_event_as_other_student'] = {'pass': False, 'error_type': type(exc).__name__}
    else:
        checks['forge_event_as_other_student'] = {'status': 'not_run_use_allow_write_on_test_only'}
    out = {
        'task': 'SPEC-006', 'environment_url': args.url,
        'tested_at': datetime.now(timezone.utc).isoformat(),
        'checks': checks,
        'result': 'complete' if args.allow_write and all(item.get('pass') for item in checks.values()) else 'incomplete_or_failure',
        'warnings': ['Asegurar fixtures que tengan eventos/respuestas/decisiones para que los resultados 0 sean concluyentes.']
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
