import type { RouteObject } from 'react-router-dom'
import MailPage from './MailPage'
import MailSettings from './MailSettings'

const routes: RouteObject[] = [
  { path: '/poczta', element: <MailPage /> },
  { path: '/poczta/ustawienia', element: <MailSettings /> },
]

export default routes
