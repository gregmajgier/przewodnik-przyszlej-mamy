import { useId, useRef, useState } from 'react'
import type { FormEvent, ReactNode } from 'react'
import {
  INSURED,
  SHOWN,
  buildRequest,
  defaultDueDate,
  maternityVariants,
  needsPay,
  plDate,
  summarize,
  validate,
  zl,
} from './calcEngine'
import type { Answers, Benefit, Evaluation, Summary, Work } from './calcEngine'
import '../calculator.css'

const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

const WORK_OPTIONS: { value: Work; label: string }[] = [
  { value: 'umowa_o_prace', label: 'Umowa o pracę' },
  { value: 'umowa_zlecenia', label: 'Umowa zlecenie' },
  { value: 'jdg', label: 'Własna firma (JDG)' },
  { value: 'student', label: 'Studiuję' },
  { value: 'brak', label: 'Nie pracuję' },
]

function Choice<T extends string>({
  legend,
  name,
  value,
  options,
  onChange,
}: {
  legend: string
  name: string
  value: T
  options: { value: T; label: string }[]
  onChange: (v: T) => void
}) {
  return (
    <fieldset className="calc-field">
      <legend>{legend}</legend>
      <div className="calc-pills">
        {options.map((o) => (
          <label key={o.value} className={`calc-pill${value === o.value ? ' is-on' : ''}`}>
            <input type="radio" name={name} value={o.value} checked={value === o.value} onChange={() => onChange(o.value)} />
            {o.label}
          </label>
        ))}
      </div>
    </fieldset>
  )
}

function Field({ label, hint, children }: { label: string; hint?: string; children: (id: string) => ReactNode }) {
  const id = useId()
  return (
    <div className="calc-field">
      <label htmlFor={id}>{label}</label>
      {children(id)}
      {hint && <p className="calc-hint">{hint}</p>}
    </div>
  )
}

function Amount({ b }: { b: Benefit }) {
  const w = b.wyliczenie!
  const weeks = w.okresy.reduce((sum, p) => sum + (p.tygodnie ?? 0), 0)
  // A leave shorter than a month (e.g. 2 weeks of paternity leave) reads better as one total.
  if (w.kwota_miesieczna !== null && w.kwota_laczna !== null && weeks > 0 && weeks < 4.3)
    return (
      <p className="calc-amount">
        {zl(w.kwota_laczna)} <span>za cały urlop</span>
      </p>
    )
  if (w.kwota_miesieczna !== null)
    return (
      <p className="calc-amount">
        {zl(w.kwota_miesieczna)} <span>/ miesiąc</span>
      </p>
    )
  return (
    <p className="calc-amount">
      {zl(w.kwota_jednorazowa ?? 0)} <span>jednorazowo</span>
    </p>
  )
}

function BenefitCard({ b }: { b: Benefit }) {
  const meta = SHOWN[b.id]
  const periods = (b.wyliczenie?.okresy ?? []).filter((p) => p.od && p.do)
  const variants = b.id === 'ZASILEK_MACIERZYNSKI_MATKA' ? maternityVariants(b) : null
  return (
    <li className="calc-card">
      <h4>{meta.name}</h4>
      <Amount b={b} />
      {periods.map((p) => (
        <p className="calc-period" key={p.nazwa}>
          {plDate(p.od!)} – {plDate(p.do!)}
          {p.tygodnie ? ` · ${p.tygodnie} tyg.` : ''}
          {p.procent ? ` · ${String(p.procent).replace('.', ',')}% podstawy` : ''}
        </p>
      ))}
      {b.wyliczenie?.kwota_laczna && periods.length > 0 && !(periods.reduce((t, p) => t + (p.tygodnie ?? 0), 0) < 4.3) ? (
        <p className="calc-total">Razem za ten okres: {zl(b.wyliczenie.kwota_laczna)}</p>
      ) : null}
      {variants && (
        <p className="calc-variant">
          Możesz też wybrać równe {zl(variants.even)} miesięcznie (81,5%) przez cały macierzyński i rodzicielski, zamiast{' '}
          {zl(variants.split[0])}, a potem {zl(variants.split[1])}. Wniosek trzeba złożyć do 21 dni po porodzie.
        </p>
      )}
      {meta.note && <p className="calc-note">{meta.note}</p>}
      <p className="calc-payer">Wypłaca: {b.instytucja}</p>
    </li>
  )
}

function Results({ s, pregnant, appUrl }: { s: Summary; pregnant: boolean; appUrl: string }) {
  return (
    <div className="calc-results">
      <h3>{s.granted.length ? 'Tyle mniej więcej ci się należy' : 'Na razie nie widzimy zasiłków z ZUS'}</h3>
      {pregnant && <p className="calc-lead">Liczymy tak, jakby dziecko urodziło się w terminie.</p>}
      {s.risks.length > 0 && (
        <ul className="calc-risks">
          {s.risks.map((r) => (
            <li key={r.id}>
              <strong>{r.nazwa}.</strong> {r.komunikat}
            </li>
          ))}
        </ul>
      )}
      {s.granted.length > 0 && (
        <ul className="calc-cards">
          {s.granted.map((b) => (
            <BenefitCard key={b.id} b={b} />
          ))}
        </ul>
      )}
      {s.maybe.length > 0 && (
        <div className="calc-block">
          <h4>Może ci przysługiwać także</h4>
          <p>
            {s.maybe.map((b) => SHOWN[b.id].name).join(', ')}. Żeby to rozstrzygnąć, potrzebujemy kilku dodatkowych
            informacji, na przykład o dochodzie rodziny. W aplikacji dopytamy o resztę.
          </p>
        </div>
      )}
      {s.deadlines.length > 0 && (
        <div className="calc-block">
          <h4>Terminy, których za ciebie przypilnujemy</h4>
          <ul className="calc-deadlines">
            {s.deadlines.map((d) => (
              <li key={`${d.data}-${d.opis}`}>
                <time dateTime={d.data}>{plDate(d.data)}</time>
                <span>{d.opis}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
      <a className="calc-cta" href={appUrl}>
        Załóż konto, a wnioski wypełnimy za ciebie
      </a>
    </div>
  )
}

export function Calculator({ appUrl }: { appUrl: string }) {
  const [a, setA] = useState<Answers>({
    role: 'matka',
    stage: 'ciaza',
    date: defaultDueDate(),
    work: 'umowa_o_prace',
    sickness: true,
    tenure: 'ponad_rok',
    gross: '',
    familyIncome: '',
    familySize: '',
  })
  const [state, setState] = useState<
    { kind: 'idle' } | { kind: 'loading' } | { kind: 'error'; message: string } | { kind: 'done'; summary: Summary; pregnant: boolean }
  >({ kind: 'idle' })
  const resultRef = useRef<HTMLDivElement>(null)
  const set = <K extends keyof Answers>(k: K, v: Answers[K]) => setA((prev) => ({ ...prev, [k]: v }))

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    const problem = validate(a)
    if (problem) {
      setState({ kind: 'error', message: problem })
      return
    }
    setState({ kind: 'loading' })
    const { profile, dataOceny } = buildRequest(a)
    try {
      const qs = dataOceny ? `?data_oceny=${dataOceny}` : ''
      const res = await fetch(`${API_URL}/api/silnik/ocena${qs}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(profile),
      })
      if (!res.ok) throw new Error(String(res.status))
      const summary = summarize((await res.json()) as Evaluation)
      setState({ kind: 'done', summary, pregnant: a.stage === 'ciaza' })
      requestAnimationFrame(() => resultRef.current?.focus())
    } catch {
      setState({ kind: 'error', message: 'Nie udało się teraz policzyć. Spróbuj za chwilę.' })
    }
  }

  const insured = INSURED.includes(a.work)
  const voluntary = a.work === 'umowa_zlecenia' || a.work === 'jdg'

  return (
    <section id="kalkulator" className="section calc-section" aria-labelledby="calc-title">
      <h2 id="calc-title">Policz, ile ci się należy</h2>
      <p className="calc-intro">
        Kilka pytań i od razu widzisz zasiłki, kwoty i terminy. To ułamek tego, co robi mRodzina: w aplikacji
        pobieramy dane z ZUS i mObywatela, wypełniamy wnioski i pilnujemy terminów.
      </p>
      <div className="calc-layout">
        <form className="calc-form" onSubmit={onSubmit} noValidate>
          <Choice
            legend="Kim jesteś?"
            name="calc-role"
            value={a.role}
            options={[
              { value: 'matka', label: 'Mamą' },
              { value: 'ojciec', label: 'Tatą' },
            ]}
            onChange={(v) => set('role', v)}
          />
          <Choice
            legend="Na jakim jesteście etapie?"
            name="calc-stage"
            value={a.stage}
            options={[
              { value: 'ciaza', label: 'Czekamy na dziecko' },
              { value: 'urodzone', label: 'Dziecko już jest' },
            ]}
            onChange={(v) => setA((prev) => ({ ...prev, stage: v, date: v === 'ciaza' ? defaultDueDate() : '' }))}
          />
          <Field label={a.stage === 'ciaza' ? 'Termin porodu' : 'Data urodzenia dziecka'}>
            {(id) => <input id={id} type="date" value={a.date} onChange={(e) => set('date', e.target.value)} required />}
          </Field>
          <Field label="Jak pracujesz?">
            {(id) => (
              <select id={id} value={a.work} onChange={(e) => set('work', e.target.value as Work)}>
                {WORK_OPTIONS.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
            )}
          </Field>
          {voluntary && (
            <label className="calc-check">
              <input type="checkbox" checked={a.sickness} onChange={(e) => set('sickness', e.target.checked)} />
              Opłacam dobrowolne ubezpieczenie chorobowe
            </label>
          )}
          {insured && needsPay(a) && (
            <>
              <Field label={a.work === 'jdg' ? 'Zadeklarowana podstawa składek (zł miesięcznie)' : 'Ile zarabiasz brutto (zł miesięcznie)?'}>
                {(id) => (
                  <input
                    id={id}
                    inputMode="decimal"
                    autoComplete="off"
                    placeholder="np. 7000"
                    value={a.gross}
                    onChange={(e) => set('gross', e.target.value)}
                  />
                )}
              </Field>
              <Field label="Od jak dawna masz to ubezpieczenie?">
                {(id) => (
                  <select id={id} value={a.tenure} onChange={(e) => set('tenure', e.target.value as Answers['tenure'])}>
                    <option value="ponad_rok">Ponad rok</option>
                    <option value="od_3_mies">Od 3 do 12 miesięcy</option>
                    <option value="krocej">Krócej niż 3 miesiące</option>
                  </select>
                )}
              </Field>
            </>
          )}
          <details className="calc-more">
            <summary>Dochód rodziny (dla becikowego i zasiłku rodzinnego)</summary>
            <Field label="Roczny dochód rodziny netto za zeszły rok (zł)">
              {(id) => (
                <input
                  id={id}
                  inputMode="decimal"
                  autoComplete="off"
                  placeholder="np. 60000"
                  value={a.familyIncome}
                  onChange={(e) => set('familyIncome', e.target.value)}
                />
              )}
            </Field>
            <Field label="Ile osób w rodzinie, razem z dzieckiem?">
              {(id) => (
                <input
                  id={id}
                  inputMode="numeric"
                  autoComplete="off"
                  placeholder="np. 3"
                  value={a.familySize}
                  onChange={(e) => set('familySize', e.target.value)}
                />
              )}
            </Field>
          </details>
          <button className="calc-submit" type="submit" disabled={state.kind === 'loading'}>
            {state.kind === 'loading' ? 'Liczę…' : 'Policz'}
          </button>
          <p className="calc-fine">
            Kwoty brutto, szacunkowe, liczone według obowiązujących przepisów. Nic nie zapisujemy.
          </p>
        </form>
        <div className="calc-output" ref={resultRef} tabIndex={-1} aria-live="polite">
          {state.kind === 'idle' && (
            <div className="calc-empty">
              <p>Tu pojawi się wynik: zasiłki, kwoty i terminy wniosków.</p>
            </div>
          )}
          {state.kind === 'loading' && (
            <div className="calc-empty">
              <p>Liczę według przepisów…</p>
            </div>
          )}
          {state.kind === 'error' && (
            <div className="calc-empty calc-error" role="alert">
              <p>{state.message}</p>
            </div>
          )}
          {state.kind === 'done' && <Results s={state.summary} pregnant={state.pregnant} appUrl={appUrl} />}
        </div>
      </div>
    </section>
  )
}
