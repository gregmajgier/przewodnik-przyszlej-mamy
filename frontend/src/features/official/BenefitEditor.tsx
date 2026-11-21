import { useEffect, useState } from 'react'
import type { FormEvent, ReactNode } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api, ApiError } from '../../lib/api'
import ConditionsReview from './ConditionsReview'
import './official.css'
import { EMPTY_FORM, STATUS_LABEL, toForm } from './types'
import type { BenefitDraft, BenefitForm, Condition, Criteria, OfficialBenefit } from './types'

type AgeUnit = 'years' | 'months'

function num(v: string): number | null {
  const n = Number(v.replace(',', '.').replace(/\s/g, ''))
  return v.trim() === '' || Number.isNaN(n) ? null : n
}

function Field({ id, label, children, wide }: { id: string; label: string; children: ReactNode; wide?: boolean }) {
  return (
    <div className={`field${wide ? ' field-wide' : ''}`}>
      <label htmlFor={id}>{label}</label>
      {children}
    </div>
  )
}

function errText(e: unknown, fallback: string) {
  return e instanceof ApiError ? e.detail : fallback
}

export default function BenefitEditor() {
  const { id = 'nowe' } = useParams()
  const navigate = useNavigate()
  const isNew = id === 'nowe'
  const [benefit, setBenefit] = useState<OfficialBenefit | null>(null)
  const [form, setForm] = useState<BenefitForm>(EMPTY_FORM)
  const [dirty, setDirty] = useState(isNew)
  const [conditions, setConditions] = useState<Condition[]>([])
  const [conditionsDirty, setConditionsDirty] = useState(false)
  const [ageUnit, setAgeUnit] = useState<AgeUnit>('years')
  const [resolution, setResolution] = useState('')
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [aiError, setAiError] = useState<string | null>(null)
  const [info, setInfo] = useState<string | null>(null)
  const [loaded, setLoaded] = useState(isNew)

  function load(b: OfficialBenefit) {
    setBenefit(b)
    setForm(toForm(b))
    setConditions(b.extra_conditions)
    setConditionsDirty(false)
    setDirty(false)
  }

  useEffect(() => {
    if (isNew) return
    let cancelled = false
    api<OfficialBenefit>(`/api/official/benefits/${id}`)
      .then((b) => !cancelled && load(b))
      .catch((e) => !cancelled && setError(errText(e, 'Nie udało się pobrać świadczenia.')))
      .finally(() => !cancelled && setLoaded(true))
    return () => {
      cancelled = true
    }
  }, [id, isNew])

  function set<K extends keyof BenefitForm>(key: K, value: BenefitForm[K]) {
    setForm((f) => ({ ...f, [key]: value }))
    setDirty(true)
  }

  function setCrit<K extends keyof Criteria>(key: K, value: Criteria[K]) {
    setForm((f) => ({ ...f, criteria: { ...f.criteria, [key]: value } }))
    setDirty(true)
  }

  const factor = ageUnit === 'years' ? 12 : 1
  const showAge = (m: number | null) => (m === null ? '' : ageUnit === 'years' ? String((m + 1) / 12) : String(m))
  // „do 3 lat” = do 35 miesięcy włącznie (granica włącznie w silniku dopasowania)
  const ageMin = (v: string) => (num(v) === null ? null : Math.round(num(v)! * factor))
  const ageMax = (v: string) => (num(v) === null ? null : Math.round(num(v)! * factor) - (ageUnit === 'years' ? 1 : 0))

  async function save(): Promise<OfficialBenefit | null> {
    setError(null)
    setInfo(null)
    try {
      const saved = isNew && !benefit
        ? await api<OfficialBenefit>('/api/official/benefits', { method: 'POST', body: form })
        : await api<OfficialBenefit>(`/api/official/benefits/${benefit!.id}`, { method: 'PUT', body: form })
      load(saved)
      if (isNew && !benefit) navigate(`/urzednik/swiadczenia/${saved.id}`, { replace: true })
      return saved
    } catch (e) {
      setError(errText(e, 'Nie udało się zapisać świadczenia.'))
      return null
    }
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setBusy('save')
    if (await save()) setInfo('Zapisano. Edycja wraca świadczenie do szkicu — opublikuj je ponownie.')
    setBusy(null)
  }

  async function extract() {
    setBusy('extract')
    setAiError(null)
    const saved = dirty || !benefit ? await save() : benefit
    if (saved) {
      try {
        load(await api<OfficialBenefit>(`/api/official/benefits/${saved.id}/extract-conditions`, { method: 'POST' }))
      } catch (e) {
        setAiError(errText(e, 'Nie udało się wyodrębnić warunków — dodaj je ręcznie.'))
      }
    }
    setBusy(null)
  }

  async function approve() {
    if (!benefit) return
    setBusy('approve')
    setError(null)
    try {
      load(
        await api<OfficialBenefit>(`/api/official/benefits/${benefit.id}/approve-conditions`, {
          method: 'POST',
          body: { conditions: conditions.filter((c) => c.text.trim()) },
        }),
      )
    } catch (e) {
      setError(errText(e, 'Nie udało się zatwierdzić warunków.'))
    }
    setBusy(null)
  }

  async function setPublished(publish: boolean) {
    if (!benefit) return
    setBusy('publish')
    setError(null)
    try {
      load(await api<OfficialBenefit>(`/api/official/benefits/${benefit.id}/${publish ? 'publish' : 'unpublish'}`, { method: 'POST' }))
      setInfo(publish ? 'Opublikowano — rodzice z Twojego obszaru już widzą to świadczenie.' : 'Wycofano publikację.')
    } catch (e) {
      setError(errText(e, 'Nie udało się zmienić publikacji.'))
    }
    setBusy(null)
  }

  async function prefill() {
    setBusy('prefill')
    setAiError(null)
    try {
      const d = await api<BenefitDraft>('/api/official/prefill-from-text', { method: 'POST', body: { text: resolution } })
      setForm((f) => ({
        ...f,
        name: d.name || f.name,
        description: d.description || f.description,
        amount_text: d.amount_text ?? f.amount_text,
        criteria: { ...f.criteria, ...Object.fromEntries(Object.entries(d.criteria).filter(([, v]) => v !== null)) },
        extra_text: d.extra_text ?? f.extra_text,
      }))
      setDirty(true)
      setInfo('Wypełniono z uchwały. Sprawdź pola i zapisz.')
    } catch (e) {
      setAiError(errText(e, 'Nie udało się wypełnić formularza z uchwały — uzupełnij pola ręcznie.'))
    }
    setBusy(null)
  }

  if (!loaded) return <p role="status">Ładowanie…</p>

  const hasExtra = Boolean(form.extra_text?.trim())
  const conditionsReady = !hasExtra || (benefit?.conditions_approved && !conditionsDirty)
  const canPublish = Boolean(benefit) && !dirty && conditionsReady && benefit?.status !== 'published'
  const c = form.criteria
  const kinds = c.employment_kinds ?? []

  return (
    <div className="stack">
      <p>
        <Link to="/urzednik">← Wszystkie świadczenia</Link>
      </p>
      <div className="row" style={{ justifyContent: 'space-between' }}>
        <h1>{isNew && !benefit ? 'Nowe świadczenie' : form.name || 'Świadczenie'}</h1>
        {benefit && <span className={`status-pill status-${benefit.status}`}>{STATUS_LABEL[benefit.status]}</span>}
      </div>

      <details className="card">
        <summary>
          <strong>Wklej uchwałę → wypełnij</strong> <span className="badge-sim">AI</span>
        </summary>
        <div className="stack" style={{ marginTop: '0.8rem' }}>
          <Field id="resolution" label="Tekst uchwały" wide>
            <textarea id="resolution" value={resolution} onChange={(e) => setResolution(e.target.value)} />
          </Field>
          <div>
            <button className="btn btn-secondary" type="button" disabled={!resolution.trim() || busy !== null} onClick={prefill}>
              {busy === 'prefill' ? 'Czytam uchwałę…' : 'Wypełnij z uchwały'}
            </button>
          </div>
        </div>
      </details>

      <form className="card stack" onSubmit={onSubmit} aria-label="Dane świadczenia">
        <h2>Opis</h2>
        <div className="official-form">
          <Field id="b-name" label="Nazwa" wide>
            <input id="b-name" required value={form.name} onChange={(e) => set('name', e.target.value)} />
          </Field>
          <Field id="b-desc" label="Opis dla rodziców" wide>
            <textarea id="b-desc" value={form.description} onChange={(e) => set('description', e.target.value)} />
          </Field>
          <Field id="b-cat" label="Rodzaj">
            <select id="b-cat" value={form.category} onChange={(e) => set('category', e.target.value as BenefitForm['category'])}>
              <option value="benefit">Świadczenie / dopłata</option>
              <option value="perk">Zniżka / program</option>
            </select>
          </Field>
          <Field id="b-amount" label="Kwota (opis)">
            <input id="b-amount" value={form.amount_text ?? ''} onChange={(e) => set('amount_text', e.target.value || null)} />
          </Field>
          <Field id="b-annual" label="Szacowana wartość roczna (zł)">
            <input id="b-annual" inputMode="numeric" value={form.annual_value_estimate ?? ''} onChange={(e) => set('annual_value_estimate', num(e.target.value))} />
          </Field>
          <Field id="b-deadline" label="Termin">
            <input id="b-deadline" value={form.deadline_text ?? ''} onChange={(e) => set('deadline_text', e.target.value || null)} />
          </Field>
          <Field id="b-how" label="Sposób złożenia" wide>
            <textarea id="b-how" value={form.how_to_apply} onChange={(e) => set('how_to_apply', e.target.value)} />
          </Field>
          <Field id="b-apply" label="Link do wniosku lub PDF">
            <input id="b-apply" type="url" value={form.apply_url ?? ''} onChange={(e) => set('apply_url', e.target.value || null)} />
          </Field>
          <Field id="b-source" label="Źródło (uchwała, strona)">
            <input id="b-source" type="url" value={form.source_url} onChange={(e) => set('source_url', e.target.value)} />
          </Field>
        </div>

        <h2>Kryteria</h2>
        <p className="muted">Sprawdzane automatycznie u każdego rodzica. Zamieszkanie na obszarze jednostki sprawdzamy zawsze.</p>
        <div className="official-form">
          <Field id="b-age-unit" label="Wiek dziecka podajesz w">
            <select id="b-age-unit" value={ageUnit} onChange={(e) => setAgeUnit(e.target.value as AgeUnit)}>
              <option value="years">latach</option>
              <option value="months">miesiącach</option>
            </select>
          </Field>
          <Field id="b-age-min" label={`Wiek dziecka od (${ageUnit === 'years' ? 'lat' : 'mies.'})`}>
            <input id="b-age-min" inputMode="numeric" value={c.child_age_min_months === null ? '' : String(c.child_age_min_months / factor)} onChange={(e) => setCrit('child_age_min_months', ageMin(e.target.value))} />
          </Field>
          <Field id="b-age-max" label={`Wiek dziecka do (${ageUnit === 'years' ? 'ukończenia lat' : 'mies. włącznie'})`}>
            <input id="b-age-max" inputMode="numeric" value={showAge(c.child_age_max_months)} onChange={(e) => setCrit('child_age_max_months', ageMax(e.target.value))} />
          </Field>
          <Field id="b-income" label="Maks. dochód na osobę (zł)">
            <input id="b-income" inputMode="decimal" value={c.max_income_per_person ?? ''} onChange={(e) => setCrit('max_income_per_person', num(e.target.value))} />
          </Field>
          <Field id="b-children" label="Min. liczba dzieci">
            <input id="b-children" inputMode="numeric" value={c.min_children ?? ''} onChange={(e) => setCrit('min_children', num(e.target.value))} />
          </Field>
          <div className="field">
            <label className="row">
              <input type="checkbox" checked={c.requires_disability === true} onChange={(e) => setCrit('requires_disability', e.target.checked || null)} />
              Dziecko z niepełnosprawnością
            </label>
            <label className="row">
              <input type="checkbox" checked={c.requires_foster === true} onChange={(e) => setCrit('requires_foster', e.target.checked || null)} />
              Rodzina zastępcza
            </label>
          </div>
          <fieldset className="field field-wide" style={{ border: 0, padding: 0 }}>
            <legend>Zatrudnienie rodzica (puste = dowolne)</legend>
            <div className="row">
              {(
                [
                  ['employment', 'umowa o pracę'],
                  ['mandate', 'zlecenie'],
                  ['jdg', 'działalność'],
                ] as const
              ).map(([k, label]) => (
                <label key={k} className="row">
                  <input
                    type="checkbox"
                    checked={kinds.includes(k)}
                    onChange={(e) => {
                      const next = e.target.checked ? [...kinds, k] : kinds.filter((x) => x !== k)
                      setCrit('employment_kinds', next.length ? next : null)
                    }}
                  />
                  {label}
                </label>
              ))}
            </div>
          </fieldset>
        </div>

        <h2>Dodatkowe wymogi</h2>
        <Field id="b-extra" label="Dodatkowe wymogi (tekst z uchwały)" wide>
          <textarea id="b-extra" value={form.extra_text ?? ''} onChange={(e) => set('extra_text', e.target.value || null)} />
        </Field>
        <div className="row">
          <button className="btn btn-secondary" type="button" disabled={!hasExtra || busy !== null} onClick={extract}>
            {busy === 'extract' ? 'Wyodrębniam…' : 'Wyodrębnij warunki'}
          </button>
          <span className="badge-sim">AI</span>
        </div>
        {aiError && (
          <p role="alert" className="alert">
            {aiError}
          </p>
        )}
        {error && (
          <p role="alert" className="alert">
            {error}
          </p>
        )}
        {info && (
          <p role="status" className="notice">
            {info}
          </p>
        )}
        <div className="row">
          <button className="btn" type="submit" disabled={busy !== null || !dirty}>
            {busy === 'save' ? 'Zapisuję…' : 'Zapisz'}
          </button>
        </div>
      </form>

      {hasExtra && (benefit?.extra_conditions.length || aiError || conditions.length > 0) ? (
        <section className="card stack" aria-labelledby="cond-h">
          <h2 id="cond-h">Warunki do zatwierdzenia</h2>
          <p className="muted">
            Sprawdź listę: popraw treść, usuń zbędne albo dodaj brakujące. Rodzice zobaczą świadczenie
            dopiero po zatwierdzeniu warunków i publikacji.
          </p>
          <ConditionsReview
            conditions={conditions}
            onChange={(next) => {
              setConditions(next)
              setConditionsDirty(true)
            }}
          />
          <div className="row">
            <button className="btn" type="button" disabled={busy !== null || !benefit || dirty} onClick={approve}>
              Zatwierdź warunki
            </button>
            {benefit?.conditions_approved && !conditionsDirty && <span>✓ Warunki zatwierdzone</span>}
          </div>
        </section>
      ) : null}

      <section className="card stack" aria-labelledby="pub-h">
        <h2 id="pub-h">Publikacja</h2>
        {!conditionsReady && <p className="muted">Najpierw zatwierdź listę warunków z „Dodatkowych wymogów”.</p>}
        {dirty && <p className="muted">Zapisz zmiany przed publikacją.</p>}
        <div className="row">
          <button className="btn" type="button" disabled={!canPublish || busy !== null} onClick={() => setPublished(true)}>
            Opublikuj
          </button>
          {benefit?.status === 'published' && (
            <button className="btn btn-secondary" type="button" disabled={busy !== null} onClick={() => setPublished(false)}>
              Wycofaj publikację
            </button>
          )}
        </div>
      </section>
    </div>
  )
}
