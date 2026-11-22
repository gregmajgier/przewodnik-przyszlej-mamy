/**
 * Ostatnia rozmowa z asystentem — żeby można było do niej wrócić z każdego ekranu (karta nad „Zapytaj”).
 *
 * Zapisujemy tylko identyfikator rozmowy (bez treści), osobno dla każdego użytkownika na tym urządzeniu.
 * Treść i podgląd zawsze pochodzą z API (`/api/chat/sessions`), które zwraca wyłącznie własne rozmowy.
 */
const PREFIX = 'mrodzina:last-chat:'
const EVENT = 'mrodzina:last-chat'
const memory = new Map<string, string>() // gdy localStorage jest niedostępny (np. tryb prywatny)

export function getLastChat(userId: string | null | undefined): string | null {
  if (!userId) return null
  try {
    return localStorage.getItem(PREFIX + userId)
  } catch {
    return memory.get(userId) ?? null
  }
}

function notify() {
  window.dispatchEvent(new Event(EVENT))
}

export function setLastChat(userId: string | null | undefined, sessionId: string): void {
  if (!userId) return
  try {
    localStorage.setItem(PREFIX + userId, sessionId)
  } catch {
    memory.set(userId, sessionId)
  }
  notify()
}

export function clearLastChat(userId: string | null | undefined): void {
  if (!userId) return
  memory.delete(userId)
  try {
    localStorage.removeItem(PREFIX + userId)
  } catch {
    // brak localStorage — wystarczy pamięć
  }
  notify()
}

/** Subskrypcja zmian (np. karta „Ostatnia rozmowa” odświeża się po nowej odpowiedzi). */
export function onLastChatChange(fn: () => void): () => void {
  window.addEventListener(EVENT, fn)
  return () => window.removeEventListener(EVENT, fn)
}
