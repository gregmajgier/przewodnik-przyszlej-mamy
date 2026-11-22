import type { RouteObject } from 'react-router-dom'
import EmpatiaForm from './EmpatiaForm'
import PueForm from './PueForm'

// Trasy publiczne (bez powłoki aplikacji) — ładowane w <iframe> przez agenta. Schemat pól i tak pobierany jest
// z API z tokenem sesji, więc bez zalogowania makieta pokazuje tylko prośbę o logowanie.
const routes: RouteObject[] = [
  { path: '/sim/pue/:portalId', element: <PueForm />, handle: { public: true } },
  { path: '/sim/empatia/:portalId', element: <EmpatiaForm />, handle: { public: true } },
]

export default routes
