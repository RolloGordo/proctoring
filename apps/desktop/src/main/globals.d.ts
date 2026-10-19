/** La direccion de la web del examen, horneada al construir por electron-vite.
 *  Cadena vacia si no se definio: solo pasa en desarrollo, porque el
 *  empaquetado se niega a correr sin ella. */
declare const __PROCTORING_WEB_URL__: string
/** Respaldo para asociar eventos locales al alumno ficticio de desarrollo. */
declare const __PROCTORING_STUDENT_ID__: string
/** Endpoint de eventos, embebido al construir el instalador. */
declare const __PROCTORING_API_URL__: string
