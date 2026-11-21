import type { RouteObject } from 'react-router-dom'
import FamilyPage from './FamilyPage'
import JoinPage from './JoinPage'
import OnboardingPage from './OnboardingPage'

const routes: RouteObject[] = [
  { path: '/start', element: <OnboardingPage /> },
  { path: '/rodzina', element: <FamilyPage /> },
  { path: '/dolacz', element: <JoinPage /> },
]

export default routes
