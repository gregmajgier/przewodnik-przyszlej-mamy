import { useParams } from 'react-router-dom'
import PortalForm from './PortalForm'

/** Makieta eZUS/PUE (SYMULACJA) — pola wg `portal_schemas.json`. */
export default function EzusForm() {
  const { portalId = '' } = useParams()
  return <PortalForm portalId={portalId} kind="ezus" />
}
