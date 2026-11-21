import type { RouteObject } from 'react-router-dom'
import ChatPage from './ChatPage'

const routes: RouteObject[] = [{ path: '/czat', element: <ChatPage />, handle: { flow: true } }]

export default routes
