import { useCallback, useState } from 'react'
import { api, apiBlob, ApiError } from '../../lib/api'
import AgentFrame from '../portal-sim/AgentFrame'
import SignModal from './SignModal'
import type { Application } from './types'

interface Props {
  app: Application
  onChange: (app: Application) => void
  /** Wniosku nie ma już w systemie (404) — kreator pokazuje stan „Tego wniosku już nie ma”. */
  onGone?: () => void
}

const isGone = (e: unknown) => e instanceof ApiError && e.status === 404

const errText = (e: unknown, fallback: string) => (e instanceof ApiError ? e.detail : fallback)

export default function SendStep({ app, onChange, onGone }: Props) {
  const [signing, setSigning] = useState(false)
  const [signBusy, setSignBusy] = useState(false)
  const [signError, setSignError] = useState<string | null>(null)
  const [sending, setSending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const signed = app.status === 'ready' && app.signed_at !== null

  const closeModal = useCallback(() => setSigning(false), [])

  async function sign() {
    setSignBusy(true)
    setSignError(null)
    try {
      onChange(await api<Application>(`/api/applications/${app.id}/sign`, { method: 'POST' }))
      setSigning(false)
    } catch (e) {
      if (isGone(e) && onGone) {
        setSigning(false)
        onGone()
        return
      }
      setSignError(errText(e, 'Nie udało się podpisać wniosku.'))
    } finally {
      setSignBusy(false)
    }
  }

  async function submit() {
    setSending(true) // przycisk wyłącza się od razu — podwójne kliknięcie nie wyśle dwa razy
    setError(null)
    try {
      onChange(await api<Application>(`/api/applications/${app.id}/submit`, { method: 'POST' }))
    } catch (e) {
      if (isGone(e) && onGone) {
        onGone()
        return
      }
      setError(errText(e, 'Nie udało się wysłać wniosku.'))
      setSending(false)
    }
  }

  async function download() {
    setError(null)
    try {
      const blob = await apiBlob(`/api/applications/${app.id}/pdf`)
      const href = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = href
      a.download = `${app.form_code}.pdf`
      a.click()
      URL.revokeObjectURL(href)
    } catch (e) {
      setError(errText(e, 'Nie udało się pobrać PDF.'))
    }
  }

  if (app.channel === 'portal_agent') {
    return <AgentFrame applicationId={app.id} onSubmitted={onChange} />
  }

  return (
    <section className="card stack" aria-labelledby="send-h">
      <h2 id="send-h">{app.channel === 'employer_email' ? 'Wyślij do pracodawcy' : 'Złóż wniosek'}</h2>
      {app.channel === 'employer_email' ? (
        <p>
          Wyślemy ten wniosek jako PDF w załączniku na adres <strong>{app.recipient_email}</strong>. Zanim to zrobimy, podpisz go.
        </p>
      ) : (
        <p>
          Podpisz wniosek, a potem złóż go jednym kliknięciem: wyślemy go do urzędu przez eZUS albo elektroniczną skrzynkę
          urzędu <span className="badge-sim">SYMULACJA</span>. Wolisz złożyć go osobiście albo pocztą? Pobierz PDF.
        </p>
      )}

      {error && (
        <p role="alert" className="alert">
          {error}
        </p>
      )}

      <div className="row">
        {!signed ? (
          <button type="button" className="btn" onClick={() => setSigning(true)}>
            Podpisz Profilem Zaufanym
          </button>
        ) : (
          <>
            <span className="pill pill-green">Podpisano Profilem Zaufanym</span>
            {app.channel === 'pdf_download' && (
              <button type="button" className="btn btn-secondary" onClick={() => void download()}>
                Pobierz PDF
              </button>
            )}
            <button type="button" className="btn" disabled={sending} onClick={() => void submit()}>
              {app.channel === 'employer_email' ? 'Wyślij' : sending ? 'Składam…' : 'Złóż wniosek'}
            </button>
          </>
        )}
      </div>

      {signing && <SignModal busy={signBusy} error={signError} onConfirm={() => void sign()} onCancel={closeModal} />}
    </section>
  )
}
