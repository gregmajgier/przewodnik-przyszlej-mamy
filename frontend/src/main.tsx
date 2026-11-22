// Fonty hostowane lokalnie (bez Google Fonts: działa offline i nie ujawnia adresu IP użytkownika Google).
// Wagi jak wcześniej z Google Fonts; polskie znaki wymagają podzbioru latin-ext.
import '@fontsource/nunito/latin-400.css'
import '@fontsource/nunito/latin-ext-400.css'
import '@fontsource/nunito/latin-600.css'
import '@fontsource/nunito/latin-ext-600.css'
import '@fontsource/nunito/latin-700.css'
import '@fontsource/nunito/latin-ext-700.css'
import '@fontsource/nunito/latin-800.css'
import '@fontsource/nunito/latin-ext-800.css'
import '@fontsource/sniglet/latin-400.css'
import '@fontsource/sniglet/latin-ext-400.css'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './theme.css'
import App from './App.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
