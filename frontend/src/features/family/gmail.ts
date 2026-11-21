import { api } from '../../lib/api'

const KEY = 'mr-gmail'

interface MailStatus {
  connected: boolean
  address: string
}

/** Łączy skrzynkę rodzica (adres zwraca backend) i zapamiętuje go na tym urządzeniu. */
export async function connectGmail(): Promise<string> {
  const s = await api<MailStatus>('/api/mail/status')
  try {
    localStorage.setItem(KEY, s.address)
  } catch {
    // bez localStorage — połączenie i tak działa po stronie serwera
  }
  return s.address
}

export function connectedGmail(): string | null {
  try {
    return localStorage.getItem(KEY)
  } catch {
    return null
  }
}
