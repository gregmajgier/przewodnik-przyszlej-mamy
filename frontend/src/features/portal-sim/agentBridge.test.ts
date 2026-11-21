import { afterEach, describe, expect, it, vi } from 'vitest'
import { isFromFrame, isToFrame, listenFromFrame, listenToParent, postToFrame } from './agentBridge'

const cleanups: Array<() => void> = []
afterEach(() => {
  cleanups.splice(0).forEach((off) => off())
})

function send(data: unknown, init: MessageEventInit = {}) {
  window.dispatchEvent(new MessageEvent('message', { data, origin: window.location.origin, ...init }))
}

describe('agentBridge — wiadomości z makiety do aplikacji', () => {
  it('przyjmuje wiadomość z tego samego originu', () => {
    const handler = vi.fn()
    cleanups.push(listenFromFrame(handler))
    send({ type: 'ready' })
    expect(handler).toHaveBeenCalledWith({ type: 'ready' })
  })

  it('odrzuca wiadomości z obcego originu', () => {
    const handler = vi.fn()
    cleanups.push(listenFromFrame(handler))
    send({ type: 'ready' }, { origin: 'https://evil.example' })
    send({ type: 'submitted' }, { origin: 'null' })
    send({ type: 'ack', fieldId: 'street', ok: true }, { origin: window.location.origin.replace('http:', 'https:') })
    expect(handler).not.toHaveBeenCalled()
  })

  it('gdy znamy ramkę, odrzuca wiadomości od innego okna (nawet z tego samego originu)', () => {
    const handler = vi.fn()
    const frameWindow = {} as Window
    cleanups.push(listenFromFrame(handler, () => frameWindow))
    send({ type: 'ready' }, { source: window }) // inne okno niż ramka
    expect(handler).not.toHaveBeenCalled()
  })

  it('odrzuca wiadomości o niepoprawnym kształcie', () => {
    const handler = vi.fn()
    cleanups.push(listenFromFrame(handler))
    for (const bad of [null, 'ready', 42, {}, { type: 'unknown' }, { type: 'ack', fieldId: 1, ok: true }, { type: 'ack', fieldId: 'a' }, { type: 'edited', fieldId: 'a', value: { x: 1 } }, { type: 'invalid', fieldIds: [1] }, { type: 'ack', fieldId: 'a', ok: true, rect: { x: 'a' } }]) {
      send(bad)
    }
    expect(handler).not.toHaveBeenCalled()
  })

  it('odsubskrybowanie przestaje przekazywać wiadomości', () => {
    const handler = vi.fn()
    const off = listenFromFrame(handler)
    off()
    send({ type: 'ready' })
    expect(handler).not.toHaveBeenCalled()
  })
})

describe('agentBridge — polecenia aplikacji do makiety', () => {
  it('makieta przyjmuje polecenia tylko od okna nadrzędnego tego samego originu', () => {
    const handler = vi.fn()
    cleanups.push(listenToParent(handler))
    send({ type: 'fill', fieldId: 'street', value: 'Floriańska' }, { origin: 'https://evil.example', source: window.parent })
    send({ type: 'fill', fieldId: 'street', value: 'Floriańska' }, { source: null }) // nieznane źródło
    expect(handler).not.toHaveBeenCalled()
    send({ type: 'fill', fieldId: 'street', value: 'Floriańska' }, { source: window.parent })
    expect(handler).toHaveBeenCalledWith({ type: 'fill', fieldId: 'street', value: 'Floriańska' })
  })

  it('makieta odrzuca polecenia o niepoprawnym kształcie', () => {
    const handler = vi.fn()
    cleanups.push(listenToParent(handler))
    for (const bad of [{ type: 'fill', fieldId: 'a' }, { type: 'fill', fieldId: 'a', value: 5 }, { type: 'fill', value: 'x' }, { type: 'eval', code: 'alert(1)' }]) {
      send(bad, { source: window.parent })
    }
    expect(handler).not.toHaveBeenCalled()
  })

  it('postToFrame wysyła z jawnym targetOrigin (nigdy „*”)', () => {
    const target = { postMessage: vi.fn() } as unknown as Window
    postToFrame(target, { type: 'fill', fieldId: 'street', value: 'x' })
    expect(target.postMessage).toHaveBeenCalledWith({ type: 'fill', fieldId: 'street', value: 'x' }, window.location.origin)
    expect(() => postToFrame(null, { type: 'submit' })).not.toThrow()
  })
})

describe('agentBridge — walidacja kształtu', () => {
  it('isFromFrame / isToFrame akceptują poprawne wiadomości', () => {
    expect(isFromFrame({ type: 'ack', fieldId: 'a', ok: false })).toBe(true)
    expect(isFromFrame({ type: 'ack', fieldId: 'a', ok: true, rect: { x: 1, y: 2, width: 3, height: 4 } })).toBe(true)
    expect(isFromFrame({ type: 'edited', fieldId: 'a', value: true })).toBe(true)
    expect(isFromFrame({ type: 'invalid', fieldIds: ['a', 'b'] })).toBe(true)
    expect(isToFrame({ type: 'submit' })).toBe(true)
    expect(isToFrame({ type: 'fill', fieldId: 'a', value: false })).toBe(true)
  })
})
