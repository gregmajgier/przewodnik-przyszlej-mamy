import { useEffect, useState } from 'react'
import { api, ApiError } from '../../lib/api'
import { describeChild, formatDate, maskPesel } from '../../lib/format'
import type { MemberProfile } from '../../lib/types'
import { profileSections } from '../registry'
import { PageHeader } from '../../ui/controls'

const KIND_LABEL = {
  employment: 'umowa o pracę',
  mandate: 'umowa zlecenie',
  jdg: 'działalność gospodarcza',
} as const

const money = new Intl.NumberFormat('pl-PL', { style: 'currency', currency: 'PLN' })

function ZusSection({ m }: { m: MemberProfile }) {
  return (
    <section className="stack" aria-label={`ZUS i mObywatel — ${m.user_name}`}>
      <h3>
        Dane z ZUS i mObywatela
      </h3>
      <dl className="facts">
        <dt>PESEL</dt>
        <dd>{maskPesel(m.pesel)}</dd>
        <dt>Data urodzenia</dt>
        <dd>{formatDate(m.birth_date)}</dd>
        <dt>Adres</dt>
        <dd>
          {m.address.postal_code} {m.address.city}, woj. {m.address.voivodeship.toLowerCase()}
        </dd>
        {m.insurance.map((i) => (
          <div key={`${i.payer}-${i.since}`} style={{ display: 'contents' }}>
            <dt>Ubezpieczenie</dt>
            <dd>
              {KIND_LABEL[i.kind]}, {i.payer}
              <br />
              <span className="muted">
                podstawa składek {money.format(i.contribution_base)} · od {formatDate(i.since)}
              </span>
            </dd>
          </div>
        ))}
        {m.ezla.map((e) => (
          <div key={e.from_date} style={{ display: 'contents' }}>
            <dt>e-ZLA</dt>
            <dd>
              kod {e.code}, {formatDate(e.from_date)} – {formatDate(e.to_date)}
            </dd>
          </div>
        ))}
        {m.contribution_debt && (
          <>
            <dt>Zadłużenie składkowe</dt>
            <dd>
              {money.format(m.contribution_debt.amount)} od {formatDate(m.contribution_debt.since)}
            </dd>
          </>
        )}
        {m.known_children.length > 0 && (
          <>
            <dt>Dzieci w ZUS</dt>
            <dd>
              {m.known_children.map((k) => (
                <div key={k.name}>
                  {k.name}{' '}
                  <span className="muted">
                    {describeChild({
                      status: k.due_date && !k.birth_date ? 'expected' : 'born',
                      birth_date: k.birth_date,
                      due_date: k.due_date,
                    })}
                  </span>
                </div>
              ))}
            </dd>
          </>
        )}
      </dl>
    </section>
  )
}

function AnswersSection({ m }: { m: MemberProfile }) {
  const entries = Object.entries(m.answers)
  return (
    <section className="stack" aria-label={`Odpowiedzi — ${m.user_name}`}>
      <h3>Twoje odpowiedzi</h3>
      {entries.length === 0 ? (
        <p className="muted">
          Zapytamy Cię tylko o to, czego nie wiemy, a co zmienia wynik dopasowania świadczeń.
        </p>
      ) : (
        <dl className="facts">
          {entries.map(([k, v]) => (
            <div key={k} style={{ display: 'contents' }}>
              <dt>{k}</dt>
              <dd>{typeof v === 'boolean' ? (v ? 'Tak' : 'Nie') : v}</dd>
            </div>
          ))}
        </dl>
      )}
    </section>
  )
}

export default function ProfilePage() {
  const [members, setMembers] = useState<MemberProfile[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    api<{ members: MemberProfile[] }>('/api/profile')
      .then((r) => !cancelled && setMembers(r.members))
      .catch((e) => !cancelled && setError(e instanceof ApiError ? e.detail : 'Nie udało się pobrać danych.'))
    return () => {
      cancelled = true
    }
  }, [])

  if (error)
    return (
      <p role="alert" className="alert">
        {error}
      </p>
    )
  if (!members) return <p role="status">Ładowanie…</p>

  return (
    <div className="page page-narrow stack">
      <PageHeader title="Moje dane" eyebrow="Profil" />
      <p className="muted">
        Dane rodziców i dzieci w jednym miejscu. Nie pytamy o to, co już wiemy z ZUS i mObywatela.
      </p>
      <div className="grid">
        {members.map((m) => (
          <article key={m.user_id} className="card stack">
            <h2>{m.user_name}</h2>
            <ZusSection m={m} />
            {profileSections.length === 0 && (
              <section className="stack" aria-label={`Umowy — ${m.user_name}`}>
                <h3>Umowy o pracę</h3>
                <p className="muted">Tutaj pojawią się dane z zatwierdzonych skanów umów.</p>
              </section>
            )}
            {profileSections.map((s) => (
              <section key={s.title} className="stack" aria-label={`${s.title} — ${m.user_name}`}>
                <h3>{s.title}</h3>
                <s.Component userId={m.user_id} userName={m.user_name} />
              </section>
            ))}
            <AnswersSection m={m} />
          </article>
        ))}
      </div>
    </div>
  )
}
