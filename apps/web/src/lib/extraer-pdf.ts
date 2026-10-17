import * as pdfjs from 'pdfjs-dist'
import workerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url'

pdfjs.GlobalWorkerOptions.workerSrc = workerUrl

export async function extraerTextoPdf(archivo: File): Promise<string> {
  const carga = pdfjs.getDocument({ data: new Uint8Array(await archivo.arrayBuffer()) })
  const documento = await carga.promise
  const lineas: string[] = []

  try {
    for (let numeroPagina = 1; numeroPagina <= documento.numPages; numeroPagina += 1) {
      const pagina = await documento.getPage(numeroPagina)
      const contenido = await pagina.getTextContent()
      const items = contenido.items.filter(
        (item): item is typeof item & { str: string; transform: number[] } =>
          'str' in item && 'transform' in item
      )
      const renglones: { y: number; partes: { x: number; texto: string }[] }[] = []

      for (const item of items) {
        const x = item.transform[4] ?? 0
        const y = item.transform[5] ?? 0
        let renglon = renglones.find((actual) => Math.abs(actual.y - y) < 3)
        if (!renglon) {
          renglon = { y, partes: [] }
          renglones.push(renglon)
        }
        renglon.partes.push({ x, texto: item.str })
      }

      lineas.push(
        ...renglones
          .sort((a, b) => b.y - a.y)
          .map((renglon) =>
            renglon.partes
              .sort((a, b) => a.x - b.x)
              .map((parte) => parte.texto.trim())
              .filter(Boolean)
              .join(' ')
          )
      )
      lineas.push('')
    }
  } finally {
    await carga.destroy()
  }

  return lineas.join('\n').trim()
}
