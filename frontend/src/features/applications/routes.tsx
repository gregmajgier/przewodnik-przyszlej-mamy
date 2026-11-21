import type { RouteObject } from 'react-router-dom'
import ApplicationWizardPage from './ApplicationWizardPage'
import ApplicationsPage from './ApplicationsPage'
import NewApplicationPage from './NewApplicationPage'

const routes: RouteObject[] = [
  { path: '/wnioski', element: <ApplicationsPage /> },
  { path: '/wnioski/nowy', element: <NewApplicationPage /> },
  { path: '/wnioski/:id', element: <ApplicationWizardPage /> },
]

export default routes
