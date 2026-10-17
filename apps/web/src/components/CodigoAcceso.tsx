/**
 * El código de acceso de un examen, o la explicación de por qué todavía no está.
 *
 * Un examen puede **guardar** su código hasta la hora de inicio
 * (`reveal_code_at_start`). En ese caso la API no lo manda —no es que esta
 * pantalla lo esconda— y aquí hay que decir qué pasa, porque un hueco en blanco
 * donde debería haber un código se lee como un error.
 */
export function CodigoAcceso({
  codigo,
  etiqueta = 'Código de acceso'
}: {
  codigo: string | null
  /** El texto de debajo. `null` para no poner ninguno. */
  etiqueta?: string | null
}) {
  if (codigo === null) {
    return (
      <div className="codigo-bloque">
        <span className="codigo-acceso codigo-guardado">· · · · · ·</span>
        {etiqueta !== null && <p className="ayuda">Se revela al empezar</p>}
      </div>
    )
  }

  return (
    <div className="codigo-bloque">
      <span className="codigo-acceso">{codigo}</span>
      {etiqueta !== null && <p className="ayuda">{etiqueta}</p>}
    </div>
  )
}
