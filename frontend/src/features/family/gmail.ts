import { api } from '../../lib/api'

/**
 * Skrzynka pocztowa rodzica do śledzenia odpowiedzi w sprawie wniosków (SYMULACJA).
 *
 * Do wyboru Gmail, Outlook albo dowolny inny adres e-mail. W demo nie logujemy się do prawdziwej poczty:
 * backend ma symulowaną skrzynkę, a wybór dostawcy i adres zapamiętujemy tylko na tym urządzeniu.
 */
const KEY = 'mr-mailbox'
const LEGACY_KEY = 'mr-gmail' // wcześniej: sam adres Gmaila

export type MailProviderKey = 'gmail' | 'outlook' | 'other'

export interface Mailbox {
  provider: MailProviderKey
  address: string
}

interface MailStatus {
  connected: boolean
  address: string
}

export const PROVIDER_LABEL: Record<MailProviderKey, string> = { gmail: 'Gmail', outlook: 'Outlook', other: 'Poczta' }

/** Prosta kontrola adresu przed „połączeniem” (np. anna@wp.pl). */
export function isEmail(value: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(value.trim())
}

/** Łączy skrzynkę wybranego dostawcy. Dla Gmaila i Outlooka adres pochodzi z symulowanej skrzynki backendu. */
export async function connectMailbox(provider: MailProviderKey, customAddress?: string): Promise<Mailbox> {
  let address: string
  if (provider === 'other') {
    address = (customAddress ?? '').trim()
  } else {
    const s = await api<MailStatus>('/api/mail/status')
    const local = s.address.split('@')[0]
    address = provider === 'gmail' ? s.address : `${local}@outlook.com`
  }
  const box: Mailbox = { provider, address }
  try {
    localStorage.setItem(KEY, JSON.stringify(box))
  } catch {
    // bez localStorage — połączenie i tak działa po stronie serwera
  }
  return box
}

export function connectedMailbox(): Mailbox | null {
  try {
    const raw = localStorage.getItem(KEY)
    if (raw) {
      const box = JSON.parse(raw) as Partial<Mailbox>
      if (box.address && box.provider && box.provider in PROVIDER_LABEL) return box as Mailbox
    }
    const legacy = localStorage.getItem(LEGACY_KEY)
    return legacy ? { provider: 'gmail', address: legacy } : null
  } catch {
    return null
  }
}

/** „Gmail połączony”, „Outlook połączony”, „Poczta połączona”. */
export function mailboxConnectedText(box: Mailbox): string {
  return box.provider === 'other' ? 'Poczta połączona' : `${PROVIDER_LABEL[box.provider]} połączony`
}
