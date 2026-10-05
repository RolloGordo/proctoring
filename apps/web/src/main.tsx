import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App'
import './styles/tokens.css'
import './styles/base.css'
import './styles/estructura.css'

const raiz = document.getElementById('root')
if (!raiz) throw new Error('Falta el elemento #root en index.html')

createRoot(raiz).render(
  <StrictMode>
    <App />
  </StrictMode>
)
