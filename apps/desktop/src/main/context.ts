// Identificadores de la sesion de examen y del estudiante.
// Cuando existan el login y el enlace de la sesion (HU-001, EN-010) los
// entregan ellos. Mientras tanto se leen de variables de entorno para
// poder probar. El UUID nulo solo sirve para el panel local: la API
// lo rechazaria porque no existe en la base de datos.
const NIL_UUID = '00000000-0000-0000-0000-000000000000'

export const examContext = {
  session_id: process.env['PROCTORING_SESSION_ID'] ?? NIL_UUID,
  student_id: process.env['PROCTORING_STUDENT_ID'] ?? NIL_UUID
}

export type ExamContext = typeof examContext
