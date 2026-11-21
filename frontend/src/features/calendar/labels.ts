import type { IconName } from '../../ui/Icon'
import { humanizeTitle } from '../applications/useApplications'
import type { CalendarEvent } from './types'

/** Kod wniosku → nazwa; roboczą nazwę dziecka w drodze zamieniamy na tę samą, co w „Waszych sprawach”. */
export const tidy = (text: string) => humanizeTitle(text).replace(/Dziecko w drodze/g, 'Maleństwo')

type PillTone = 'neutral' | 'pink' | 'green' | 'amber' | 'blue' | 'violet'

export const KIND_META: Record<CalendarEvent['kind'], { icon: IconName; tone: PillTone }> = {
  deadline: { icon: 'clock', tone: 'amber' },
  application: { icon: 'doc', tone: 'blue' },
  child: { icon: 'baby', tone: 'green' },
  warning: { icon: 'alert', tone: 'pink' },
}
