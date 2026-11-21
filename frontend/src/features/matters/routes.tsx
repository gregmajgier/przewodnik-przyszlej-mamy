import type { RouteObject } from 'react-router-dom'
import MattersPage from './MattersPage'

const routes: RouteObject[] = [{ path: '/sprawy/:who', element: <MattersPage /> }]

export default routes
