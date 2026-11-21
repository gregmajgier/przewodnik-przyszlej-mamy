import type { RouteObject } from 'react-router-dom'
import ContractsPage from './ContractsPage'

const routes: RouteObject[] = [
  { path: '/umowy', element: <ContractsPage /> },
  // opcjonalny krok onboardingu (OnboardingPage planu 01 nie jest edytowany — trasa jest osobna)
  { path: '/start/umowy', element: <ContractsPage onboarding /> },
]

export default routes
