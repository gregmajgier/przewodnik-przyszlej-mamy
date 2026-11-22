import { useEffect, useState } from 'react'
import type { FormEvent, ReactNode } from 'react'
import { useNavigate, useOutletContext, useParams, useSearchParams } from 'react-router-dom'
import { api, ApiError } from '../../lib/api'
import { formatPln } from '../../lib/format'
import { decimalToNumber, sanitizeIntegerInput } from '../../lib/numeric'
import { Button } from '../../ui/Button'
import { Icon } from '../../ui/Icon'
import type { IconName } from '../../ui/Icon'
import { PageHeader, Pill, Segmented, Toggle } from '../../ui/controls'
import { Sheet } from '../../ui/Sheet'
import ConditionsReview from './ConditionsReview'
import './official.css'
import { EMPTY_FORM, STATUS_TONE, statusLabel, toForm } from './types'
import type { BenefitDraft, BenefitForm, Condition, Criteria, OfficialBenefit, Unit } from './types'

type AgeUnit = 'years' | 'months'
type Toast = { tone: 'ok' | 'error'; text: string }

const EMPLOYMENT: [NonNullable<Criteria['employment_kinds']>[number], string][] = [
  ['employment', 'Umowa o pracę'],
  ['mandate', 'Umowa zlecenie'],
  ['jdg', 'Działalność'],
]

function num(v: string): number | null {
  return decimalToNumber(v)
}

function errText(e: unknown, fallback: string) {
  return e instanceof ApiError ? e.detail : fallback
}

function Field({ id, label, hint, children, wide }: { id: string; label: string; hint?: string; children: ReactNode; wide?: boolean }) {
  return (
    <div className={`field${wide ? ' field-wide' : ''}`}>
      <label htmlFor={id}>{label}</label>
      {children}
      {hint && <span className="field-hint">{hint}</span>}
    </div>
  )
}

/** Pole z jednostką na końcu („zł”, „lat”). */
function Suffixed({ suffix, children }: { suffix: string; children: ReactNode }) {
  return (
    <div className="off-input-wrap">
      {children}
      <span className="off-suffix" aria-hidden="true">
        {suffix}
      </span>
    </div>
  )
}

function Section({ n, icon, title, lead, children, id }: { n: number; icon: IconName; title: string; lead?: string; children: ReactNode; id: string }) {
  return (
    <section className="off-sec rise" style={{ ['--i' as string]: n }} aria-labelledby={id}>
      <header className="off-sec-head">
        <span className="off-sec-n" aria-hidden="true">
          <Icon name={icon} size={20} />
        </span>
        <div>
          <span className="off-sec-step">Krok {n}</span>
          <h2 id={id}>{title}</h2>
          {lead && <p className="muted">{lead}</p>}
        </div>
      </header>
      <div className="off-sec-body">{children}</div>
    </section>
  )
}

function Check({ ok, children }: { ok: boolean; children: ReactNode }) {
  return (
    <li className={ok ? 'is-ok' : ''}>
      <span className="off-check" aria-hidden="true">
        {ok && <Icon name="check" size={13} stroke={2.6} />}
      </span>
      <span>
        {children}
        <span className="sr-only">{ok ? ': gotowe' : ': do zrobienia'}</span>
      </span>
    </li>
  )
}

export default function BenefitEditor() {
  const { id = 'nowe' } = useParams()
  const [params] = useSearchParams()
  const unit = useOutletContext<Unit | null | undefined>()
  const navigate = useNavigate()
  const isNew = id === 'nowe'
  const [benefit, setBenefit] = useState<OfficialBenefit | null>(null)
  const [form, setForm] = useState<BenefitForm>(EMPTY_FORM)
  const [dirty, setDirty] = useState(isNew)
  const [conditions, setConditions] = useState<Condition[]>([])
  const [conditionsDirty, setConditionsDirty] = useState(false)
  const [ageUnit, setAgeUnit] = useState<AgeUnit>('years')
  const [aiOpen, setAiOpen] = useState(isNew || params.get('z') === 'uchwala')
  const [resolution, setResolution] = useState('')
  const [busy, setBusy] = useState<string | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [prefillError, setPrefillError] = useState<string | null>(null)
  const [aiError, setAiError] = useState<string | null>(null)
  const [toast, setToast] = useState<Toast | null>(null)
  const [confirmDelete, setConfirmDelete] = useState(false)
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
      .catch((e) => !cancelled && setLoadError(errText(e, 'Nie udało się pobrać świadczenia.')))
      .finally(() => !cancelled && setLoaded(true))
    return () => {
      cancelled = true
    }
  }, [id, isNew])

  // potwierdzenia znikają same, błędy zostają do zamknięcia
  useEffect(() => {
    if (toast?.tone !== 'ok') return
    const t = window.setTimeout(() => setToast(null), 5000)
    return () => window.clearTimeout(t)
  }, [toast])

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
    try {
      const saved =
        isNew && !benefit
          ? await api<OfficialBenefit>('/api/official/benefits', { method: 'POST', body: form })
          : await api<OfficialBenefit>(`/api/official/benefits/${benefit!.id}`, { method: 'PUT', body: form })
      load(saved)
      if (isNew && !benefit) navigate(`/urzednik/swiadczenia/${saved.id}`, { replace: true })
      return saved
    } catch (e) {
      setToast({ tone: 'error', text: errText(e, 'Nie udało się zapisać świadczenia.') })
      return null
    }
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    const wasPublished = benefit?.status === 'published'
    setBusy('save')
    setToast(null)
    if (await save()) {
      setToast({ tone: 'ok', text: wasPublished ? 'Zapisano. Świadczenie wróciło do szkicu. Opublikuj je ponownie.' : 'Zapisano zmiany.' })
    }
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
        setAiError(errText(e, 'Nie udało się wyodrębnić warunków. Dodaj je ręcznie.'))
      }
    }
    setBusy(null)
  }

  async function approve() {
    if (!benefit) return
    setBusy('approve')
    setToast(null)
    try {
      load(
        await api<OfficialBenefit>(`/api/official/benefits/${benefit.id}/approve-conditions`, {
          method: 'POST',
          body: { conditions: conditions.filter((c) => c.text.trim()) },
        }),
      )
      setToast({ tone: 'ok', text: 'Warunki zatwierdzone. Możesz opublikować świadczenie.' })
    } catch (e) {
      setToast({ tone: 'error', text: errText(e, 'Nie udało się zatwierdzić warunków.') })
    }
    setBusy(null)
  }

  async function setPublished(publish: boolean) {
    if (!benefit) return
    setBusy('publish')
    setToast(null)
    try {
      load(await api<OfficialBenefit>(`/api/official/benefits/${benefit.id}/${publish ? 'publish' : 'unpublish'}`, { method: 'POST' }))
      setToast({ tone: 'ok', text: publish ? 'Opublikowano. Rodzice z Twojego obszaru już widzą to świadczenie.' : 'Wycofano publikację.' })
    } catch (e) {
      setToast({ tone: 'error', text: errText(e, 'Nie udało się zmienić publikacji.') })
    }
    setBusy(null)
  }

  async function remove() {
    if (!benefit) return
    setBusy('delete')
    try {
      await api(`/api/official/benefits/${benefit.id}`, { method: 'DELETE' })
      navigate('/urzednik', { replace: true })
    } catch (e) {
      setConfirmDelete(false)
      setToast({ tone: 'error', text: errText(e, 'Nie udało się usunąć świadczenia.') })
      setBusy(null)
    }
  }

  async function prefill() {
    setBusy('prefill')
    setPrefillError(null)
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
      setAiOpen(false)
      setToast({ tone: 'ok', text: 'Wypełniono z uchwały. Sprawdź pola i zapisz.' })
    } catch (e) {
      setPrefillError(errText(e, 'Nie udało się wypełnić formularza z uchwały. Uzupełnij pola ręcznie.'))
    }
    setBusy(null)
  }

  if (!loaded) return <p role="status" className="page">Ładowanie…</p>
  if (loadError && !benefit) {
    return (
      <div className="page page-narrow off-page">
        <PageHeader title="Nie udało się otworzyć świadczenia" eyebrow="Świadczenie" back="/urzednik" />
        <p role="alert" className="alert">
          {loadError}
        </p>
      </div>
    )
  }

  const hasExtra = Boolean(form.extra_text?.trim())
  const conditionsReady = !hasExtra || Boolean(benefit?.conditions_approved && !conditionsDirty)
  const hasDescription = Boolean(form.description.trim())
  const published = benefit?.status === 'published'
  const canPublish = Boolean(benefit) && !dirty && conditionsReady && hasDescription && !published
  const showConditions = hasExtra && Boolean(benefit?.extra_conditions.length || aiError || conditions.length > 0)
  const c = form.criteria
  const kinds = c.employment_kinds ?? []
  const where = unit?.name ?? 'Twoja jednostka'

  return (
    <div className="page off-page off-editor">
      <PageHeader title={isNew && !benefit ? 'Nowe świadczenie' : form.name || 'Świadczenie'} eyebrow={where} back="/urzednik">
        <div className="row off-editor-pills">
          {benefit ? (
            <Pill tone={STATUS_TONE[benefit.status]} dot>
              {statusLabel(benefit)}
            </Pill>
          ) : (
            <Pill>Jeszcze niezapisane</Pill>
          )}
          <Pill tone={form.category === 'perk' ? 'blue' : 'pink'}>{form.category === 'perk' ? 'Zniżka / program' : 'Świadczenie / dopłata'}</Pill>
        </div>
      </PageHeader>

      <div className="off-editor-layout">
        <div className="off-editor-main">
          <section className={`off-ai rise ${aiOpen ? 'is-open' : ''}`} aria-labelledby="off-ai-h">
            <button type="button" className="off-ai-head" aria-expanded={aiOpen} aria-controls="off-ai-body" onClick={() => setAiOpen((o) => !o)}>
              <span className="off-ai-icon" aria-hidden="true">
                <Icon name="sparkle" size={22} />
              </span>
              <span className="off-ai-title">
                <strong id="off-ai-h">Wklej uchwałę → wypełnij</strong>
                <span>Nazwę, kwotę, kryteria i dodatkowe wymogi odczytamy z tekstu.</span>
              </span>
              <Icon name="chevronDown" size={20} className="off-ai-chev" />
            </button>
            {aiOpen && (
              <div id="off-ai-body" className="off-ai-body">
                <div className="field">
                  <label htmlFor="resolution">Tekst uchwały</label>
                  <textarea
                    id="resolution"
                    rows={6}
                    placeholder="Np. „§ 1. Ustanawia się program… § 2. Świadczenie przysługuje…”"
                    value={resolution}
                    onChange={(e) => setResolution(e.target.value)}
                  />
                </div>
                {prefillError && (
                  <p role="alert" className="alert">
                    {prefillError}
                  </p>
                )}
                <div className="row">
                  <Button variant="dark" leading="sparkle" disabled={!resolution.trim() || busy !== null} onClick={prefill}>
                    {busy === 'prefill' ? 'Czytam uchwałę…' : 'Wypełnij z uchwały'}
                  </Button>
                  <span className="muted small">Nic nie zapisujemy, dopóki nie klikniesz „Zapisz”.</span>
                </div>
              </div>
            )}
          </section>

          <form id="benefit-form" className="off-form" onSubmit={onSubmit} aria-label="Dane świadczenia">
            <Section n={1} id="sec-desc" icon="gift" title="Co to za świadczenie" lead="Tak przedstawimy je rodzicom w bazie świadczeń.">
              <div className="off-grid">
                <Field id="b-name" label="Nazwa" wide>
                  <input id="b-name" required value={form.name} onChange={(e) => set('name', e.target.value)} placeholder="Np. Dopłata do żłobka" />
                </Field>
                <Field id="b-desc" label="Opis dla rodziców" wide hint="Dwa, trzy zdania prostym językiem. Bez opisu nie opublikujesz świadczenia.">
                  <textarea id="b-desc" rows={4} value={form.description} onChange={(e) => set('description', e.target.value)} />
                </Field>
                <div className="field field-wide">
                  <span className="field-label">Rodzaj</span>
                  <Segmented
                    label="Rodzaj"
                    value={form.category}
                    onChange={(v) => set('category', v)}
                    options={[
                      { value: 'benefit', label: 'Świadczenie / dopłata' },
                      { value: 'perk', label: 'Zniżka / program' },
                    ]}
                  />
                </div>
                <Field id="b-amount" label="Kwota (opis)" hint="Np. „do 500 zł / mies.”">
                  <input id="b-amount" value={form.amount_text ?? ''} onChange={(e) => set('amount_text', e.target.value || null)} />
                </Field>
                <Field id="b-annual" label="Szacowana wartość roczna">
                  <Suffixed suffix="zł">
                    <input id="b-annual" type="number" min="0" step="1" inputMode="numeric" value={form.annual_value_estimate ?? ''} onChange={(e) => set('annual_value_estimate', num(e.target.value))} />
                  </Suffixed>
                </Field>
              </div>
            </Section>

            <Section n={2} id="sec-how" icon="doc" title="Jak je dostać" lead="Rodzic zobaczy te informacje przy składaniu wniosku.">
              <div className="off-grid">
                <Field id="b-how" label="Sposób złożenia" wide>
                  <textarea id="b-how" rows={3} value={form.how_to_apply} onChange={(e) => set('how_to_apply', e.target.value)} />
                </Field>
                <Field id="b-deadline" label="Termin" wide>
                  <input id="b-deadline" value={form.deadline_text ?? ''} onChange={(e) => set('deadline_text', e.target.value || null)} placeholder="Np. do 30 września każdego roku" />
                </Field>
                <Field id="b-apply" label="Link do wniosku lub PDF">
                  <input id="b-apply" type="url" placeholder="https://" value={form.apply_url ?? ''} onChange={(e) => set('apply_url', e.target.value || null)} />
                </Field>
                <Field id="b-source" label="Źródło (uchwała, strona)">
                  <input id="b-source" type="url" placeholder="https://" value={form.source_url} onChange={(e) => set('source_url', e.target.value)} />
                </Field>
              </div>
            </Section>

            <Section
              n={3}
              id="sec-crit"
              icon="family"
              title="Kto może skorzystać"
              lead="Sprawdzamy to automatycznie u każdej rodziny. Zamieszkanie na obszarze jednostki sprawdzamy zawsze."
            >
              <div className="off-grid">
                <div className="field field-wide">
                  <span className="field-label">Wiek dziecka podajesz w</span>
                  <Segmented
                    label="Wiek dziecka podajesz w"
                    value={ageUnit}
                    onChange={setAgeUnit}
                    options={[
                      { value: 'years', label: 'latach' },
                      { value: 'months', label: 'miesiącach' },
                    ]}
                  />
                </div>
                <Field id="b-age-min" label="Wiek dziecka od">
                  <Suffixed suffix={ageUnit === 'years' ? 'lat' : 'mies.'}>
                    <input
                      id="b-age-min"
                      type="number"
                      min="0"
                      step="1"
                      inputMode="numeric"
                      value={c.child_age_min_months === null ? '' : String(c.child_age_min_months / factor)}
                      onChange={(e) => {
                        const clean = sanitizeIntegerInput(e.target.value)
                        if (clean !== null) setCrit('child_age_min_months', ageMin(clean))
                      }}
                    />
                  </Suffixed>
                </Field>
                <Field id="b-age-max" label={ageUnit === 'years' ? 'Do ukończenia' : 'Do (włącznie)'}>
                  <Suffixed suffix={ageUnit === 'years' ? 'lat' : 'mies.'}>
                    <input id="b-age-max" type="number" min="0" step="1" inputMode="numeric" value={showAge(c.child_age_max_months)} onChange={(e) => {
                      const clean = sanitizeIntegerInput(e.target.value)
                      if (clean !== null) setCrit('child_age_max_months', ageMax(clean))
                    }} />
                  </Suffixed>
                </Field>
                <Field id="b-income" label="Maks. dochód na osobę" hint="Puste = bez progu dochodowego">
                  <Suffixed suffix="zł">
                    <input id="b-income" type="number" min="0" step="0.01" inputMode="decimal" value={c.max_income_per_person ?? ''} onChange={(e) => setCrit('max_income_per_person', num(e.target.value))} />
                  </Suffixed>
                </Field>
                <Field id="b-children" label="Min. liczba dzieci">
                  <input id="b-children" type="number" min="0" step="1" inputMode="numeric" value={c.min_children ?? ''} onChange={(e) => {
                    const clean = sanitizeIntegerInput(e.target.value)
                    if (clean !== null) setCrit('min_children', clean === '' ? null : Number(clean))
                  }} />
                </Field>
                <div className="field field-wide off-toggles">
                  <Toggle
                    label="Dziecko z niepełnosprawnością"
                    description="Tylko rodziny z orzeczeniem o niepełnosprawności dziecka"
                    checked={c.requires_disability === true}
                    onChange={(v) => setCrit('requires_disability', v || null)}
                  />
                  <Toggle
                    label="Rodzina zastępcza"
                    description="Tylko rodziny zastępcze i rodzinne domy dziecka"
                    checked={c.requires_foster === true}
                    onChange={(v) => setCrit('requires_foster', v || null)}
                  />
                </div>
                <fieldset className="field field-wide off-fieldset">
                  <legend>Zatrudnienie rodzica</legend>
                  <div className="off-chips">
                    {EMPLOYMENT.map(([k, label]) => {
                      const on = kinds.includes(k)
                      return (
                        <button
                          key={k}
                          type="button"
                          className={`off-chip ${on ? 'is-on' : ''}`}
                          aria-pressed={on}
                          onClick={() => {
                            const next = on ? kinds.filter((x) => x !== k) : [...kinds, k]
                            setCrit('employment_kinds', next.length ? next : null)
                          }}
                        >
                          {on && <Icon name="check" size={15} stroke={2.4} />}
                          {label}
                        </button>
                      )
                    })}
                  </div>
                  <span className="field-hint">Nic nie zaznaczono = dowolna forma zatrudnienia.</span>
                </fieldset>
              </div>
            </Section>

            <Section
              n={4}
              id="sec-extra"
              icon="docCheck"
              title="Dodatkowe wymogi"
              lead="Wszystko, czego nie da się zaznaczyć wyżej. Zamienimy to na listę warunków do Twojej akceptacji."
            >
              <Field id="b-extra" label="Dodatkowe wymogi (tekst z uchwały)" wide>
                <textarea id="b-extra" rows={4} value={form.extra_text ?? ''} onChange={(e) => set('extra_text', e.target.value || null)} />
              </Field>
              <div className="row">
                <Button variant="secondary" leading="sparkle" disabled={!hasExtra || busy !== null} onClick={extract}>
                  {busy === 'extract' ? 'Wyodrębniam…' : 'Wyodrębnij warunki'}
                </Button>
                {dirty && hasExtra && <span className="muted small">Najpierw zapiszemy zmiany.</span>}
              </div>
              {aiError && (
                <p role="alert" className="alert">
                  {aiError}
                </p>
              )}
            </Section>
          </form>

          {showConditions && (
            <section className="off-sec off-sec-conds rise" aria-labelledby="cond-h">
              <header className="off-sec-head">
                <span className="off-sec-n is-amber" aria-hidden="true">
                  <Icon name="checkCircle" size={20} />
                </span>
                <div>
                  <span className="off-sec-step">Krok 5</span>
                  <h2 id="cond-h">Warunki do zatwierdzenia</h2>
                  <p className="muted">Popraw treść, usuń zbędne albo dodaj brakujące. Rodzice zobaczą świadczenie po zatwierdzeniu i publikacji.</p>
                </div>
              </header>
              <div className="off-sec-body">
                <ConditionsReview
                  conditions={conditions}
                  onChange={(next) => {
                    setConditions(next)
                    setConditionsDirty(true)
                  }}
                />
                <div className="row">
                  <Button leading="check" disabled={busy !== null || !benefit || dirty} onClick={approve}>
                    Zatwierdź warunki
                  </Button>
                  {benefit?.conditions_approved && !conditionsDirty && (
                    <Pill tone="green">
                      <Icon name="check" size={14} /> Warunki zatwierdzone
                    </Pill>
                  )}
                </div>
              </div>
            </section>
          )}

          {dirty && (
            <div className="off-savebar" role="region" aria-label="Niezapisane zmiany">
              <span>
                <span className="off-savebar-dot" aria-hidden="true" />
                Masz niezapisane zmiany
              </span>
              <Button type="submit" form="benefit-form" variant="dark" disabled={busy !== null}>
                {busy === 'save' ? 'Zapisuję…' : 'Zapisz'}
              </Button>
            </div>
          )}
        </div>

        <aside className="off-editor-aside">
          <section className="off-panel" aria-labelledby="pub-h">
            <h2 id="pub-h">Publikacja</h2>
            <ul className="off-checklist">
              <Check ok={hasDescription}>Opis dla rodziców</Check>
              <Check ok={Boolean(benefit) && !dirty}>Zmiany zapisane</Check>
              <Check ok={conditionsReady}>{hasExtra ? 'Warunki zatwierdzone' : 'Bez dodatkowych wymogów'}</Check>
              <Check ok={published}>Widoczne dla rodziców</Check>
            </ul>
            {!conditionsReady && !dirty && <p className="muted small">Najpierw zatwierdź listę warunków z „Dodatkowych wymogów”.</p>}
            {dirty && <p className="muted small">Zapisz zmiany przed publikacją.</p>}
            <div className="off-panel-actions">
              <Button block disabled={!canPublish || busy !== null} onClick={() => setPublished(true)}>
                Opublikuj
              </Button>
              {published && (
                <Button block variant="secondary" disabled={busy !== null} onClick={() => setPublished(false)}>
                  Wycofaj publikację
                </Button>
              )}
              {benefit && (
                <button type="button" className="link-button off-delete" onClick={() => setConfirmDelete(true)} disabled={busy !== null}>
                  <Icon name="trash" size={16} /> Usuń świadczenie
                </button>
              )}
            </div>
          </section>

          <section className="off-preview" aria-labelledby="prev-h">
            <h2 id="prev-h">
              <Icon name="eye" size={16} /> Tak zobaczą to rodzice
            </h2>
            <article className="off-preview-card">
              <span className={`icon-tile ${form.category === 'perk' ? 'tone-sky' : 'tone-peach'}`} aria-hidden="true">
                <Icon name={form.category === 'perk' ? 'percent' : 'coins'} size={22} />
              </span>
              <div>
                <p className="off-preview-where">{unit?.name ?? 'Twoja gmina'}</p>
                <h3>{form.name || 'Nazwa świadczenia'}</h3>
                {(form.amount_text || form.annual_value_estimate) && (
                  <p className="off-preview-amount">
                    {form.amount_text}
                    {form.annual_value_estimate ? <span> · ~{formatPln(form.annual_value_estimate)} / rok</span> : null}
                  </p>
                )}
                <p className="off-preview-desc">{form.description || 'Tu pojawi się opis dla rodziców.'}</p>
                {form.deadline_text && (
                  <p className="off-preview-deadline">
                    <Icon name="clock" size={14} /> {form.deadline_text}
                  </p>
                )}
              </div>
            </article>
          </section>
        </aside>
      </div>

      {toast && (
        <div className={`off-toast is-${toast.tone}`} role={toast.tone === 'error' ? 'alert' : 'status'}>
          <Icon name={toast.tone === 'error' ? 'alert' : 'checkCircle'} size={20} />
          <span>{toast.text}</span>
          <button type="button" className="icon-btn" aria-label="Zamknij komunikat" onClick={() => setToast(null)}>
            <Icon name="close" size={16} />
          </button>
        </div>
      )}

      <Sheet
        open={confirmDelete}
        onClose={() => setConfirmDelete(false)}
        title="Usunąć świadczenie?"
        subtitle={form.name}
        busy={busy === 'delete'}
        footer={
          <>
            <Button variant="secondary" onClick={() => setConfirmDelete(false)}>
              Zostaw
            </Button>
            <Button variant="danger" leading="trash" disabled={busy === 'delete'} onClick={remove}>
              {busy === 'delete' ? 'Usuwam…' : 'Usuń na stałe'}
            </Button>
          </>
        }
      >
        <p>
          Świadczenie zniknie z panelu{published ? ' i z bazy świadczeń rodziców' : ''}. Tej operacji nie da się cofnąć. Jeśli chcesz je tylko
          ukryć, wycofaj publikację.
        </p>
      </Sheet>
    </div>
  )
}
