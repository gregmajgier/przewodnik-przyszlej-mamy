import type { RouteObject } from 'react-router-dom'
import JaskolkaHome from './JaskolkaHome'

// Lista „Dla Was” jest też stroną główną w trybie jaskółki (AppShell podstawia ją pod „/”).
const routes: RouteObject[] = [{ path: '/dla-was', element: <JaskolkaHome /> }]

export default routes
