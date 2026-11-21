import type { RouteObject } from 'react-router-dom'
import DashboardPage from './DashboardPage'

// Zastępuje tymczasowe przekierowanie „/” → „/rodzina” z App.tsx (App pomija je, gdy trasa „/” istnieje).
const routes: RouteObject[] = [{ path: '/', element: <DashboardPage /> }]

export default routes
