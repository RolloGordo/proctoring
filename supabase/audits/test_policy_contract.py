"""Pruebas ESTÁTICAS del contrato RLS; no reemplazan una auditoría con JWT."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / 'migrations'


def test_decision_restored_only_for_owner():
    sql = (MIGRATIONS / '20261009120000_restore_decisions_student_select.sql').read_text()
    assert 'create policy decisions_student_select on public.decisions' in sql
    assert 'for select to authenticated' in sql
    assert 'student_id = (select auth.uid())' in sql


def test_protective_migration_still_present_and_unchanged():
    sql = (MIGRATIONS / '20261009010000_harden_student_direct_rls.sql').read_text()
    assert 'drop policy if exists session_participants_student_update' in sql
    assert 'revoke update on public.answers from authenticated' in sql
    assert 'revoke insert on public.answers from authenticated' in sql


def test_audit_checks_only_other_students_decisions():
    source = (ROOT / 'audits/audit_rls.py').read_text()
    assert "check_read('decisions_other_student', 'decisions'" in source
    assert "student_id='eq.' + args.other_student_id" in source
