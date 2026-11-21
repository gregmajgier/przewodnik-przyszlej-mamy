import { useParams } from 'react-router-dom'
import ApplicationWizard from './ApplicationWizard'

/** Trasa `/wnioski/:id` — kontynuacja szkicu albo podgląd złożonego wniosku. */
export default function ApplicationWizardPage() {
  const { id = '' } = useParams()
  return <ApplicationWizard key={id} applicationId={id} />
}
