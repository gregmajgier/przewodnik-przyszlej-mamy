import type { RouteObject } from 'react-router-dom'
import ContractsPage from './ContractsPage'
import OnboardingContracts from './OnboardingContracts'

const routes: RouteObject[] = [
  { path: '/umowy', element: <ContractsPage /> },
  { path: '/start/umowy', element: <OnboardingContracts />, handle: { flow: true } },
]

export default routes
