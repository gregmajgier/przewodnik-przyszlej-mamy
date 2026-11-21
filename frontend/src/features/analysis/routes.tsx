import type { RouteObject } from 'react-router-dom'
import AnalysisPage from './AnalysisPage'

const routes: RouteObject[] = [{ path: '/analiza', element: <AnalysisPage />, handle: { flow: true } }]

export default routes
