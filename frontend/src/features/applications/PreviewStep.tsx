import { useEffect, useState } from 'react'
import { apiBlob, ApiError } from '../../lib/api'
import '../../components/a11y.css'
import { formatDate } from '../../lib/format'
import type { AnswerValue, Application, Channel, FieldInfo, FormEntry } from './types'
import { CHANNEL_LABEL } from './types'

interface Props {
  app: Application
  form: FormEntry | undefined
  busy: boolean
  error: string | null
  onEdit: (fieldId: string, value: AnswerValue) => Promise<void>
  onChannel: (channel: Channel) => Promise<void>
  onNext: () => void
}

function displayValue(field: FieldInfo, value: unknown): string {
  if (field.type === 'bool') return value === true ? 'Tak' : 'Nie'
  if (field.type === 'date' && typeof value === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(value)) return formatDate(value)
  return String(value)
}

function FieldRow({ field, value, disabled, onEdit }: { field: FieldInfo; value: unknown; disabled: boolean; onEdit: Props['onEdit'] }) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState('')
  const inputId = `edit-${field.id}`

  async function save() {
    if (draft.trim() === '') return
    await onEdit(field.id, draft.trim())
    setEditing(false)
  }

  return (
    <div className="preview-row">
      <dt>{field.label}</dt>
      <dd>
        {editing ? (
          <span className="row">
            <label className="sr-only" htmlFor={inputId}>
              {field.label}
            </label>
            {field.type === 'choice' ? (
              <select id={inputId} value={draft} onChange={(e) => setDraft(e.target.value)}>
                <option value="">— wybierz —</option>
                {(field.choices ?? []).map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
            ) : (
              <input id={inputId} type={field.type === 'date' ? 'date' : 'text'} value={draft} onChange={(e) => setDraft(e.target.value)} />
            )}
            <button type="button" className="btn" disabled={disabled || draft.trim() === ''} onClick={() => void save()}>
              Zapisz
            </button>
            <button type="button" className="btn btn-secondary" onClick={() => setEditing(false)}>
              Anuluj
            </button>
          </span>
        ) : (
          <>
            {displayValue(field, value)}
            {field.type !== 'bool' && (
              <button
                type="button"
                className="link-button"
                aria-label={`Zmień: ${field.label}`}
                disabled={disabled}
                onClick={() => {
                  setDraft(typeof value === 'string' ? value : '')
                  setEditing(true)
                }}
              >
                Zmień
              </button>
            )}
          </>
        )}
      </dd>
    </div>
  )
}

/** PDF z API wymaga nagłówka Bearer, więc pobieramy go jako blob i pokazujemy przez adres obiektu. */
function PdfPreview({ appId, version }: { appId: string; version: string }) {
  const [url, setUrl] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    let created: string | null = null
    apiBlob(`/api/applications/${appId}/pdf`)
      .then((blob) => {
        if (cancelled) return
        created = typeof URL.createObjectURL === 'function' ? URL.createObjectURL(blob) : null
        setUrl(created)
        setError(null)
      })
      .catch((e) => !cancelled && setError(e instanceof ApiError ? e.detail : 'Nie udało się wczytać podglądu PDF.'))
    return () => {
      cancelled = true
      if (created && typeof URL.revokeObjectURL === 'function') URL.revokeObjectURL(created)
    }
  }, [appId, version])

  if (error) return <p role="alert" className="alert">{error}</p>
  if (!url) return <p role="status" className="muted">Przygotowuję podgląd PDF…</p>
  return <iframe className="pdf-frame" title="Podgląd wniosku (PDF)" src={url} />
}

export default function PreviewStep({ app, form, busy, error, onEdit, onChannel, onNext }: Props) {
  const shown = app.fields.filter((f) => app.values[f.id] !== undefined && app.values[f.id] !== null && app.values[f.id] !== '')
  const channels = form?.channels ?? [app.channel]
  const version = JSON.stringify([app.values, app.channel])
  const hasPdf = app.channel !== 'portal_agent'

  return (
    <section className="card stack" aria-labelledby="preview-h">
      <h2 id="preview-h">Sprawdź wniosek</h2>
      <p className="muted">Tak wypełniliśmy wniosek na podstawie Waszych danych. Popraw, co trzeba — nic nie poszło jeszcze do urzędu.</p>
      {error && (
        <p role="alert" className="alert">
          {error}
        </p>
      )}

      <dl className="facts preview-list">
        {shown.map((f) => (
          <FieldRow key={f.id} field={f} value={app.values[f.id]} disabled={busy} onEdit={onEdit} />
        ))}
      </dl>

      {channels.length > 1 && (
        <fieldset className="stack channel-picker" disabled={busy}>
          <legend>Jak złożyć wniosek?</legend>
          {channels.map((c) => (
            <label key={c} className="row">
              <input type="radio" name="channel" checked={app.channel === c} onChange={() => void onChannel(c)} />
              <span>{CHANNEL_LABEL[c]}</span>
            </label>
          ))}
        </fieldset>
      )}

      {hasPdf && <PdfPreview appId={app.id} version={version} />}

      <div className="row">
        <button type="button" className="btn" disabled={busy} onClick={onNext}>
          Dalej
        </button>
      </div>
    </section>
  )
}
