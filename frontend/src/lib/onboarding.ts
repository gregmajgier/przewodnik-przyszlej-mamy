/**
 * Czy ten użytkownik przeszedł już onboarding NA TYM URZĄDZENIU.
 *
 * Celowo lokalnie (localStorage), a nie na serwerze: aplikacja jest demem i na każdym nowym urządzeniu / w nowej
 * przeglądarce każda persona ma zobaczyć cały proces od początku — nawet jeśli jej rodzina już istnieje w bazie.
 * Klucz jest per użytkownik, więc zmiana persony na tym samym urządzeniu też pokazuje onboarding.
 */
const PREFIX = 'mrodzina:onboarded:'
const memory = new Set<string>() // gdy localStorage jest niedostępny (np. tryb prywatny)

export function isOnboarded(userId: string | null | undefined): boolean {
  if (!userId) return false
  try {
    return localStorage.getItem(PREFIX + userId) === '1'
  } catch {
    return memory.has(userId)
  }
}

export function markOnboarded(userId: string): void {
  try {
    localStorage.setItem(PREFIX + userId, '1')
  } catch {
    memory.add(userId) // zostaje w pamięci do końca sesji karty
  }
}

export function resetOnboarding(userId: string): void {
  memory.delete(userId)
  try {
    localStorage.removeItem(PREFIX + userId)
  } catch {
    // brak localStorage — wystarczy pamięć
  }
}
