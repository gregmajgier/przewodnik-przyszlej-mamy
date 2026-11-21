/**
 * Protokół `postMessage` między aplikacją (agent) a makietą portalu w <iframe>.
 *
 * Bezpieczeństwo: obie strony przyjmują wyłącznie wiadomości z **tego samego originu**
 * (`event.origin === location.origin`) i od właściwego okna (ramka → rodzic, rodzic → ta ramka),
 * a kształt wiadomości jest walidowany — obcy origin, inna ramka albo śmieci są ignorowane.
 * Wiadomości wysyłamy zawsze z jawnym `targetOrigin` (nigdy „*”).
 */

export interface Rect {
  x: number
  y: number
  width: number
  height: number
}

export type FieldValue = string | boolean

/** Aplikacja → makieta. */
export type ToFrame =
  | { type: 'fill'; fieldId: string; value: FieldValue }
  | { type: 'submit' } // rodzic zatwierdził wysyłkę (przycisk „Zatwierdzam i wysyłam”)

/** Makieta → aplikacja. */
export type FromFrame =
  | { type: 'ready' }
  | { type: 'ack'; fieldId: string; ok: boolean; rect?: Rect }
  | { type: 'edited'; fieldId: string; value: FieldValue } // rodzic sam zmienił pole w makiecie
  | { type: 'invalid'; fieldIds: string[] } // makieta odmówiła wysyłki: brakuje wymaganych pól
  | { type: 'submitted' }

const isObj = (v: unknown): v is Record<string, unknown> => typeof v === 'object' && v !== null
const isStr = (v: unknown): v is string => typeof v === 'string'
const isValue = (v: unknown): v is FieldValue => isStr(v) || typeof v === 'boolean'

function isRect(v: unknown): v is Rect {
  return isObj(v) && ['x', 'y', 'width', 'height'].every((k) => typeof v[k] === 'number' && Number.isFinite(v[k]))
}

export function isFromFrame(msg: unknown): msg is FromFrame {
  if (!isObj(msg)) return false
  switch (msg.type) {
    case 'ready':
    case 'submitted':
      return true
    case 'ack':
      return isStr(msg.fieldId) && typeof msg.ok === 'boolean' && (msg.rect === undefined || isRect(msg.rect))
    case 'edited':
      return isStr(msg.fieldId) && isValue(msg.value)
    case 'invalid':
      return Array.isArray(msg.fieldIds) && msg.fieldIds.every(isStr)
    default:
      return false
  }
}

export function isToFrame(msg: unknown): msg is ToFrame {
  if (!isObj(msg)) return false
  if (msg.type === 'submit') return true
  return msg.type === 'fill' && isStr(msg.fieldId) && isValue(msg.value)
}

const sameOrigin = (e: MessageEvent) => e.origin === window.location.origin

/**
 * Nasłuch po stronie aplikacji. `frame` zwraca okno ramki — gdy jest dostępne, wiadomość musi od niego pochodzić.
 * Zwraca funkcję odsubskrybowania.
 */
export function listenFromFrame(handler: (msg: FromFrame) => void, frame?: () => Window | null | undefined): () => void {
  function onMessage(e: MessageEvent) {
    if (!sameOrigin(e)) return
    const expected = frame?.()
    if (expected && e.source !== expected) return
    if (isFromFrame(e.data)) handler(e.data)
  }
  window.addEventListener('message', onMessage)
  return () => window.removeEventListener('message', onMessage)
}

export function postToFrame(target: Window | null | undefined, msg: ToFrame): void {
  target?.postMessage(msg, window.location.origin)
}

/** Nasłuch po stronie makiety: tylko od okna nadrzędnego tego samego originu. */
export function listenToParent(handler: (msg: ToFrame) => void): () => void {
  function onMessage(e: MessageEvent) {
    if (!sameOrigin(e)) return
    if (e.source !== window.parent) return
    if (isToFrame(e.data)) handler(e.data)
  }
  window.addEventListener('message', onMessage)
  return () => window.removeEventListener('message', onMessage)
}

export function isFramed(): boolean {
  return window.parent !== window
}

/** Wysyła do okna nadrzędnego (nic nie robi, gdy makieta jest otwarta poza ramką). */
export function postToParent(msg: FromFrame): void {
  if (isFramed()) window.parent.postMessage(msg, window.location.origin)
}
