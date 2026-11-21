import { Link, useLocation } from 'react-router-dom'
import { Icon } from '../../ui/Icon'

/** Pływający przycisk „Zapytaj mRodzinę” — z każdego ekranu otwiera czat. Kontekst ekranu trafia do czatu. */
export function AskFab() {
  const { pathname } = useLocation()
  return (
    <Link to="/czat" state={{ from: pathname }} className="ask-fab" aria-label="Zapytaj mRodzinę">
      <span className="ask-fab-icon">
        <Icon name="sparkle" size={24} />
      </span>
      <span className="ask-fab-label">Zapytaj</span>
    </Link>
  )
}
