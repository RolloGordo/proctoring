import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App'
import './styles/tokens.css'
import './styles/base.css'
import './styles/estructura.css'
// La tipografía de la parte pública. Va en el paquete y se sirve desde nuestro
// dominio: el navegador solo la descarga cuando algo de `.publica` la usa.
import './styles/fuentes.css'
import './styles/publica.css'
import './styles/aviso-almacenamiento.css'
import './styles/avisos-supervision.css'
import './styles/panel-oscuro.css'

const raiz = document.getElementById('root')
if (!raiz) throw new Error('Falta el elemento #root en index.html')

createRoot(raiz).render(
  <StrictMode>
    <App />
  </StrictMode>
)
