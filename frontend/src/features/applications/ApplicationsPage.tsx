import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { timeAgo } from '../../lib/format'
import { useSession } from '../../lib/session'
import { Button } from '../../ui/Button'
import { Icon } from '../../ui/Icon'
import { Avatar, PageHeader, Pill, Segmented } from '../../ui/controls'
import { connectedGmail } from '../family/gmail'
import { childLabel } from '../matters/model'
import { STATUS_LABEL } from './types'
import type { Application } from './types'
import { CHANNEL_SHORT, isOpen, latestMessage, senderLabel, STAGES, stageOf, STATUS_TONE, useApplications } from './useApplications'
import '../../ui/ui.css'
import './applications.css'

function Track({ app }: { app: Application }) {
  const stage = stageOf(app.status)
  const rejected = app.status === 'rejected'
  return (
    <ol className="track" aria-label={`Etap: ${STAGES[stage]}`}>
      {STAGES.map((s, i) => (
        <li key={s} className={`${i < stage ? 'is-done' : ''} ${i === stage ? 'is-now' : ''} ${rejected && i === 3 ? 'is-bad' : ''}`}>
          <span className="track-dot" aria-hidden="true">
            {i < stage || (i === 3 && app.status === 'accepted') ? <Icon name="check" size={12} stroke={3} /> : null}
          </span>
          <span className="track-label">{s}</span>
        </li>
      ))}
    </ol>
  )
}

export default function ApplicationsPage() {
  const { family, user } = useSession()
  const { apps, catalog, error, syncing, syncedAt, sync, nameOf, titleOf, threadOf } = useApplications(!!family)
  const [tab, setTab] = useState<'open' | 'done'>('open')
  const gmail = connectedGmail()

  useEffect(() => {
    if (family) void sync()
  }, [family, sync])

  if (!family) return null

  const memberName = (id: string) => (id === user?.id ? 'Ty' : (family.members.find((m) => m.id === id)?.name.split(' ')[0] ?? 'Drugi rodzic'))
  const childOf = (id: string | null) => family.children.find((c) => c.id === id)
  const openApps = (apps ?? []).filter((a) => isOpen(a.status))
  const doneApps = (apps ?? []).filter((a) => !isOpen(a.status))
  const shown = tab === 'open' ? openApps : doneApps
  const flow = (catalog?.recommended_flow ?? []).filter((code) => !(apps ?? []).some((a) => a.form_code === code)).slice(0, 4)

  return (
    <div className="page apps">
      <PageHeader
        title="Wnioski"
        eyebrow="Wasze sprawy w urzędach"
        actions={
          <Button size="sm" leading="plus" to="/wnioski/nowy">
            Nowy
          </Button>
        }
      />

      <div className="sync-bar rise" role="status" aria-live="polite">
        <span className="sync-bar-icon">
          <Icon name="mail" size={20} />
        </span>
        <span className="sync-bar-text">
          <strong>{gmail ? 'Gmail połączony' : 'Skrzynka pocztowa'}</strong>
          <span>
            {syncing
              ? 'Sprawdzam nowe odpowiedzi z urzędów…'
              : syncedAt
                ? `Zsynchronizowano ${timeAgo(syncedAt.toISOString())} · statusy aktualizują się same`
                : 'Odpowiedzi z ZUS, urzędów i od pracodawcy trafiają tu automatycznie'}
          </span>
        </span>
        <button type="button" className="icon-btn" onClick={() => void sync()} disabled={syncing} aria-label="Sprawdź pocztę teraz">
          <Icon name="refresh" size={20} className={syncing ? 'spin' : ''} />
        </button>
      </div>

      <div className="apps-tabs">
        <Segmented
          label="Wnioski"
          value={tab}
          onChange={setTab}
          options={[
            { value: 'open', label: 'W toku', count: openApps.length },
            { value: 'done', label: 'Zakończone', count: doneApps.length },
          ]}
        />
      </div>

      {error && (
        <p role="alert" className="alert">
          {error}
        </p>
      )}
      {!apps && !error && (
        <div className="stack" role="status" aria-label="Wczytuję wnioski">
          <div className="skeleton" style={{ height: '9rem' }} />
          <div className="skeleton" style={{ height: '9rem' }} />
        </div>
      )}

      {apps && shown.length === 0 && (
        <div className="card empty">
          <Icon name="docCheck" size={34} />
          <p>{tab === 'open' ? 'Nie macie wniosków w toku.' : 'Nie ma jeszcze zakończonych wniosków.'}</p>
          {tab === 'open' && (
            <Button to="/wnioski/nowy" leading="plus" variant="secondary">
              Złóż pierwszy wniosek
            </Button>
          )}
        </div>
      )}

      <ul className="app-cards">
        {shown.map((a, i) => {
          const child = childOf(a.child_id)
          const last = latestMessage(threadOf(a.id))
          const needsYou = a.status === 'needs_input' || a.status === 'draft' || a.status === 'ready' || a.status === 'more_info'
          return (
            <li key={a.id} className="rise" style={{ ['--i' as string]: i }}>
              <Link to={`/wnioski/${a.id}`} className="app-card">
                <div className="app-card-top">
                  <Pill tone={STATUS_TONE[a.status]} dot>
                    {STATUS_LABEL[a.status]}
                  </Pill>
                  <span className="app-card-channel">
                    <Icon name={a.channel === 'portal_agent' ? 'globe' : 'doc'} size={15} />
                    {CHANNEL_SHORT[a.channel]}
                  </span>
                </div>
                <div>
                  <h3 className="app-card-title">{titleOf(a.form_code)}</h3>
                  <p className="app-card-full">{nameOf(a.form_code)}</p>
                </div>
                <div className="app-card-people">
                  <Avatar name={memberName(a.applicant_id)} tone="peach" size={26} />
                  <span>{memberName(a.applicant_id)}</span>
                  {child && (
                    <>
                      <span className="dot-sep" aria-hidden="true" />
                      <span>dot. {childLabel(child)}</span>
                    </>
                  )}
                </div>
                <Track app={a} />
                {last && last.folder === 'inbox' ? (
                  <div className="app-card-mail">
                    <Icon name="inbox" size={17} />
                    <span className="app-card-mail-text">
                      <strong>{senderLabel(last)}</strong>
                      {last.classification_summary ?? last.subject}
                    </span>
                    <span className="app-card-mail-time">{timeAgo(last.received_at)}</span>
                  </div>
                ) : needsYou ? (
                  <div className="app-card-cta">
                    <Icon name="sparkle" size={17} />
                    {a.channel === 'portal_agent' ? 'Agent wypełni formularz online. Kontynuuj' : 'Dokończ i podpisz, reszta jest wypełniona'}
                    <Icon name="arrowRight" size={16} />
                  </div>
                ) : null}
              </Link>
            </li>
          )
        })}
      </ul>

      {flow.length > 0 && (
        <section className="section" aria-labelledby="next-h">
          <h2 id="next-h">Polecane następne</h2>
          <div className="next-forms">
            {flow.map((code) => (
              <Link key={code} to={`/wnioski/nowy?form=${encodeURIComponent(code)}`} className="next-form">
                <span className="icon-tile tone-sky">
                  <Icon name="doc" size={20} />
                </span>
                <span className="next-form-name">{titleOf(code)}</span>
                <Icon name="plus" size={18} />
              </Link>
            ))}
          </div>
        </section>
      )}
    </div>
  )
}
