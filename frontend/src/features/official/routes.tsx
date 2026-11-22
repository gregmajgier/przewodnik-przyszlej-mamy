import type { RouteObject } from 'react-router-dom'
import BenefitEditor from './BenefitEditor'
import BenefitsList from './BenefitsList'
import OfficialLayout from './OfficialLayout'
import OfficialLogin from './OfficialLogin'
import NationalParameters from './NationalParameters'

// Panel urzędnika ma własną powłokę i strażnika sesji (OfficialLayout), więc trasy są poza AppShell rodzica.
const routes: RouteObject[] = [
  { path: '/urzednik/logowanie', element: <OfficialLogin />, handle: { public: true } },
  {
    path: '/urzednik',
    element: <OfficialLayout />,
    handle: { public: true },
    children: [
      { index: true, element: <BenefitsList /> },
      { path: 'swiadczenia/:id', element: <BenefitEditor /> },
      { path: 'parametry', element: <NationalParameters /> },
    ],
  },
]

export default routes
