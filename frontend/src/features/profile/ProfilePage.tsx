import { useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { api, ApiError } from '../../lib/api'
import { formatDate, maskPesel } from '../../lib/format'
import { useSession } from '../../lib/session'
import type { MemberProfile } from '../../lib/types'
import { Icon } from '../../ui/Icon'
import type { IconName } from '../../ui/Icon'
import { Avatar, PageHeader, Pill, TONES } from '../../ui/controls'
import { profileSections } from '../registry'
import { answerLabel, applicationFacts, isApplicationAnswer, needsBenefitNames, questionTexts } from './answers'
import type { QuestionTexts } from './answers'
import '../../ui/ui.css'
import './profile.css'

const KIND_LABEL = {
  employment: 'Umowa o pracę',
  mandate: 'Umowa zlecenie',
  jdg: 'Działalność gospodarcza',
} as const

const money = new Intl.NumberFormat('pl-PL', { style: 'currency', currency: 'PLN', maximumFractionDigits: 0 })

function Row({ icon, tone, title, sub, end }: { icon: ReactNode; tone?: string; title: ReactNode; sub?: ReactNode; end?: ReactNode }) {
  return (
    <li className="profile-row">
      {typeof icon === 'string' ? (
        <span className={`icon-tile ${tone ?? ''}`} aria-hidden="true">
          <Icon name={icon as IconName} size={20} />
        </span>
      ) : (
        icon
      )}
      <span className="profile-row-main">
        <span className="profile-row-title">{title}</span>
        {sub && <span className="profile-row-sub">{sub}</span>}
      </span>
      {end}
    </li>
  )
}

function Card({ title, label, children, note }: { title: string; label: string; children: ReactNode; note?: ReactNode }) {
  return (
    <section className="profile-card" aria-label={label}>
      <div className="profile-card-head">
        <h3>{title}</h3>
        {note}
      </div>
      {children}
    </section>
  )
}

function IdentityCard({ m }: { m: MemberProfile }) {
  const a = m.address
  return (
    <Card title="Dane z ZUS i mObywatela" label={`ZUS i mObywatel: ${m.user_name}`} note={<Pill tone="blue">pobrane automatycznie</Pill>}>
      <dl className="profile-facts">
        <div>
          <dt>PESEL</dt>
          <dd>{maskPesel(m.pesel)}</dd>
        </div>
        <div>
          <dt>Data urodzenia</dt>
          <dd>{formatDate(m.birth_date)}</dd>
        </div>
        <div className="profile-facts-wide">
          <dt>Adres</dt>
          <dd>
            {a.postal_code} {a.city}
            <span className="profile-facts-sub">woj. {a.voivodeship.toLowerCase()}</span>
          </dd>
        </div>
      </dl>
    </Card>
  )
}

function WorkCard({ m }: { m: MemberProfile }) {
  const empty = m.insurance.length === 0 && m.ezla.length === 0 && !m.contribution_debt
  return (
    <Card title="Praca i ubezpieczenie" label={`Praca i ubezpieczenie: ${m.user_name}`}>
      {empty ? (
        <p className="muted profile-empty">ZUS nie pokazuje teraz żadnego ubezpieczenia.</p>
      ) : (
        <ul className="profile-rows">
          {m.insurance.map((i) => (
            <Row
              key={`${i.payer}-${i.since}`}
              icon="briefcase"
              tone="tone-sky"
              title={i.payer}
              sub={
                <>
                  {KIND_LABEL[i.kind]} · od {formatDate(i.since)}
                  <br />
                  podstawa składek {money.format(i.contribution_base)}
                </>
              }
            />
          ))}
          {m.ezla.map((e) => (
            <Row
              key={e.from_date}
              icon="health"
              tone="tone-mint"
              title={`Zwolnienie lekarskie e-ZLA, kod ${e.code}`}
              sub={`${formatDate(e.from_date)} – ${formatDate(e.to_date)}`}
            />
          ))}
          {m.contribution_debt && (
            <Row
              icon="alert"
              tone="tone-butter"
              title={`Zaległe składki: ${money.format(m.contribution_debt.amount)}`}
              sub={`od ${formatDate(m.contribution_debt.since)}`}
            />
          )}
        </ul>
      )}
    </Card>
  )
}

function ChildrenCard({ m }: { m: MemberProfile }) {
  if (m.known_children.length === 0) return null
  return (
    <Card title="Dzieci w ZUS" label={`Dzieci w ZUS: ${m.user_name}`}>
      <ul className="profile-rows">
        {m.known_children.map((k, i) => {
          const expected = Boolean(k.due_date && !k.birth_date)
          return (
            <Row
              key={k.name}
              icon={<Avatar name={k.name} tone={TONES[i % TONES.length]} icon={expected ? 'baby' : undefined} size={46} />}
              title={k.name}
              sub={
                expected
                  ? `termin porodu ${formatDate(k.due_date as string)}`
                  : k.birth_date
                    ? `urodzone ${formatDate(k.birth_date)}`
                    : undefined
              }
            />
          )
        })}
      </ul>
    </Card>
  )
}

function AnswersCard({ m, questions }: { m: MemberProfile; questions: QuestionTexts }) {
  const entries = Object.entries(m.answers)
  const forms = applicationFacts(m.answers)
  const benefits = entries.filter(([k, v]) => !isApplicationAnswer(k, v))
  return (
    <Card title="Twoje odpowiedzi" label={`Odpowiedzi: ${m.user_name}`}>
      {entries.length === 0 ? (
        <p className="muted profile-empty">
          Zapytamy Cię tylko o to, czego nie wiemy, a co zmienia wynik dopasowania świadczeń.
        </p>
      ) : (
        <>
          {forms.length > 0 && (
            <dl className="profile-facts">
              {forms.map((f) => (
                <div key={f.key} className={f.key === 'employer_email' || f.key === 'street' ? 'profile-facts-wide' : undefined}>
                  <dt>{f.label}</dt>
                  <dd>{f.value}</dd>
                </div>
              ))}
            </dl>
          )}
          {benefits.length > 0 && (
            <ul className="profile-answers">
              {benefits.map(([k, v]) => (
                <li key={k}>
                  <span>{answerLabel(k, questions)}</span>
                  {typeof v === 'boolean' ? (
                    <Pill tone={v ? 'green' : 'neutral'}>{v ? 'Tak' : 'Nie'}</Pill>
                  ) : (
                    <strong>{v}</strong>
                  )}
                </li>
              ))}
            </ul>
          )}
          <p className="muted small profile-foot">Użyjemy tego przy kolejnych wnioskach, żeby nie pytać drugi raz.</p>
        </>
      )}
    </Card>
  )
}

export default function ProfilePage() {
  const { user } = useSession()
  const [members, setMembers] = useState<MemberProfile[] | null>(null)
  const [questions, setQuestions] = useState<QuestionTexts>({})
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    api<{ members: MemberProfile[] }>('/api/profile')
      .then((r) => {
        if (cancelled) return
        setMembers(r.members)
        if (r.members.some((m) => needsBenefitNames(m.answers))) {
          // treść pytań o świadczenia — tylko po to, żeby podpisać odpowiedzi po ludzku
          api<Parameters<typeof questionTexts>[0]>('/api/benefits')
            .then((all) => !cancelled && setQuestions(questionTexts(all)))
            .catch(() => undefined)
        }
      })
      .catch((e) => !cancelled && setError(e instanceof ApiError ? e.detail : 'Nie udało się pobrać danych.'))
    return () => {
      cancelled = true
    }
  }, [])

  if (!members) {
    return (
      <div className="page page-narrow">
        {error ? (
          <p role="alert" className="alert">
            {error}
          </p>
        ) : (
          <div className="skeleton" style={{ height: '14rem', marginTop: '4rem' }} role="status" aria-label="Ładowanie" />
        )}
      </div>
    )
  }

  const ordered = [...members].sort((a, b) => Number(b.user_id === user?.id) - Number(a.user_id === user?.id))

  return (
    <div className="page page-narrow profile">
      <PageHeader title="Moje dane" eyebrow="Profil">
        <p className="muted profile-lead">
          Wszystko, co wiemy o Was z ZUS i mObywatela, plus to, co nam powiedzieliście. Nie pytamy drugi raz o to, co już mamy.
        </p>
      </PageHeader>

      {ordered.map((m, idx) => (
        <section key={m.user_id} className="section profile-member" aria-labelledby={`person-${m.user_id}`}>
          <div className="profile-person">
            <Avatar name={m.user_name} tone={m.user_id === user?.id ? 'peach' : 'sky'} size={56} />
            <div>
              <h2 id={`person-${m.user_id}`}>{m.user_name}</h2>
              <span className="muted small">{m.user_id === user?.id ? 'To Ty' : idx === 0 ? 'Rodzic' : 'Drugi rodzic'}</span>
            </div>
          </div>
          <div className="profile-cards">
            <IdentityCard m={m} />
            <WorkCard m={m} />
            <ChildrenCard m={m} />
            {profileSections.length === 0 ? (
              <Card title="Umowy o pracę" label={`Umowy: ${m.user_name}`}>
                <p className="muted profile-empty">Tutaj pojawią się dane z zatwierdzonych skanów umów.</p>
              </Card>
            ) : (
              profileSections.map((s) => (
                <Card key={s.title} title={s.title} label={`${s.title}: ${m.user_name}`}>
                  <div className="profile-slot">
                    <s.Component userId={m.user_id} userName={m.user_name} />
                  </div>
                </Card>
              ))
            )}
            <AnswersCard m={m} questions={questions} />
          </div>
        </section>
      ))}
    </div>
  )
}
