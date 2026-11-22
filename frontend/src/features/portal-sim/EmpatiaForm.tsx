import { useParams } from 'react-router-dom'
import PortalForm from './PortalForm'

/** Makieta Emp@tia — pola wg `portal_schemas.json`. */
export default function EmpatiaForm() {
  const { portalId = '' } = useParams()
  return <PortalForm portalId={portalId} kind="empatia" />
}
