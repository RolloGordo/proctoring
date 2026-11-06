/**
 * Cada cuánto volver a preguntar, con un margen al azar (ADR-0011).
 *
 * Los estudiantes de un examen entran casi a la vez. Con un intervalo fijo, los
 * que llegaron en el mismo segundo vuelven a preguntar en el mismo segundo,
 * cada diez, durante toda la espera: la prueba de carga lo mostró como picos
 * sincronizados contra la API. Repartir cada consulta en ±20 % los desfasa
 * solos en pocas vueltas, sin que nadie espere más de media.
 */
export function conMargen(ms: number, fraccion = 0.2, azar: () => number = Math.random): number {
  return Math.round(ms * (1 - fraccion + 2 * fraccion * azar()))
}

/**
 * Llama a `consultar` ahora y después cada `ms` con margen, hasta que se pare.
 * Con `setTimeout` encadenado y no `setInterval`: cada vuelta sortea su espera.
 */
export function sondear(consultar: () => void, ms: number): () => void {
  let temporizador: ReturnType<typeof setTimeout> | undefined
  let parado = false
  const programar = (): void => {
    temporizador = setTimeout(() => {
      if (parado) return
      consultar()
      programar()
    }, conMargen(ms))
  }
  consultar()
  programar()
  return () => {
    parado = true
    clearTimeout(temporizador)
  }
}
