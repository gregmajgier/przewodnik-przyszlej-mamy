import { useEffect, useState } from 'react'
import { apiBlob, ApiError } from '../../lib/api'
import '../../components/a11y.css'
import { formatDate } from '../../lib/format'
import { Button } from '../../ui/Button'
import { Icon } from '../../ui/Icon'
import { Select } from '../../ui/controls'
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
              <Select
                id={inputId}
                label={field.label}
                value={draft}
                onChange={setDraft}
                options={(field.choices ?? []).map((c) => ({ value: c, label: c }))}
              />
            ) : (
              <input
                id={inputId}
                className="input"
                type={field.type === 'date' ? 'date' : 'text'}
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
              />
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
  if (!url)
    return (
      <div className="paper">
        <div className="skeleton" style={{ height: '28rem' }} role="status" aria-label="Przygotowuję podgląd PDF" />
      </div>
    )
  return (
    <div className="paper">
      <div className="paper-bar">
        <Icon name="doc" size={18} />
        <span>{appId ? 'Wniosek.pdf' : ''}</span>
        <a href={url} download="wniosek.pdf" className="paper-dl" aria-label="Pobierz PDF">
          <Icon name="download" size={18} />
        </a>
      </div>
      <iframe className="pdf-frame" title="Podgląd wniosku (PDF)" src={url} />
    </div>
  )
}

export default function PreviewStep({ app, form, busy, error, onEdit, onChannel, onNext }: Props) {
  const shown = app.fields.filter((f) => app.values[f.id] !== undefined && app.values[f.id] !== null && app.values[f.id] !== '')
  const channels = form?.channels ?? [app.channel]
  const version = JSON.stringify([app.values, app.channel])
  const hasPdf = app.channel !== 'portal_agent'

  return (
    <section className="stack" aria-labelledby="preview-h">
      <div className="autofill-banner">
        <span className="autofill-icon">
          <Icon name="sparkle" size={22} />
        </span>
        <div>
          <h2 id="preview-h">Sprawdź wniosek</h2>
          <p>
            Wypełniliśmy automatycznie <strong>{shown.length} {shown.length === 1 ? 'pole' : shown.length % 10 >= 2 && shown.length % 10 <= 4 && (shown.length % 100 < 12 || shown.length % 100 > 14) ? 'pola' : 'pól'}</strong> na
            podstawie danych z ZUS, mObywatela i Waszych odpowiedzi. Popraw, co trzeba. Nic nie poszło jeszcze do urzędu.
          </p>
        </div>
      </div>
      {error && (
        <p role="alert" className="alert">
          {error}
        </p>
      )}

      <dl className="card preview-list">
        {shown.map((f) => (
          <FieldRow key={f.id} field={f} value={app.values[f.id]} disabled={busy} onEdit={onEdit} />
        ))}
      </dl>

      {channels.length > 1 && (
        <div className="channel-picker" role="radiogroup" aria-label="Jak złożyć wniosek?">
          <h3>Jak złożyć wniosek?</h3>
          {channels.map((c) => (
            <button
              key={c}
              type="button"
              role="radio"
              aria-checked={app.channel === c}
              className="channel-option"
              disabled={busy}
              onClick={() => void onChannel(c)}
            >
              <Icon name={c === 'portal_agent' ? 'globe' : c === 'employer_email' ? 'mail' : 'download'} size={20} />
              <span>{CHANNEL_LABEL[c]}</span>
              <span className="channel-radio" aria-hidden="true" />
            </button>
          ))}
        </div>
      )}

      {hasPdf && <PdfPreview appId={app.id} version={version} />}

      <div className="wizard-actions">
        <Button block disabled={busy} onClick={onNext} icon="arrowRight">
          Wszystko się zgadza
        </Button>
      </div>
    </section>
  )
}
