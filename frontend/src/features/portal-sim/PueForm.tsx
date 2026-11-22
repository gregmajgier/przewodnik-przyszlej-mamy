import { useParams } from 'react-router-dom'
import PortalForm from './PortalForm'

/** Makieta PUE ZUS — pola wg `portal_schemas.json`. */
export default function PueForm() {
  const { portalId = '' } = useParams()
  return <PortalForm portalId={portalId} kind="pue" />
}
