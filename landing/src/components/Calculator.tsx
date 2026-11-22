import { useId, useRef, useState } from 'react'
import type { FormEvent, ReactNode } from 'react'
import {
  INSURED,
  SHOWN,
  buildRequest,
  defaultDueDate,
  isoDate,
  maternityVariants,
  needsPay,
  plDate,
  summarize,
  validate,
  zl,
} from './calcEngine'
import type {
  Answers,
  BabyAnswer,
  Benefit,
  ChildAnswer,
  Evaluation,
  RequiredApplication,
  Role,
  Stage,
  Summary,
  TriState,
  Work,
} from './calcEngine'
import '../calculator.css'

const API_URL = import.meta.env.VITE_API_URL ?? ''

function decimalInput(raw: string): string | null {
  const value = raw.replace(/\s/g, '').replace(',', '.')
  if (value === '') return ''
  if (!/^\d*\.?\d*$/.test(value) || (value.match(/\./g) ?? []).length > 1) return null
  return value
}


const WORK_OPTIONS: { value: Work; label: string }[] = [
  { value: 'umowa_o_prace', label: 'Umowa o pracę' },
  { value: 'umowa_zlecenia', label: 'Umowa zlecenie' },
  { value: 'jdg', label: 'Własna firma (JDG)' },
  { value: 'wspolpraca_jdg', label: 'Współpraca przy działalności' },
  { value: 'ulga_na_start', label: 'JDG — ulga na start' },
  { value: 'umowa_o_dzielo', label: 'Umowa o dzieło' },
  { value: 'bezrobotna_z_zasilkiem', label: 'Bezrobotna/y z zasiłkiem' },
  { value: 'bezrobotna_bez_zasilku', label: 'Bezrobotna/y bez zasiłku' },
  { value: 'krus', label: 'KRUS' },
  { value: 'student', label: 'Student/ka' },
  { value: 'duchowny', label: 'Duchowny/a' },
  { value: 'marynarz', label: 'Marynarz' },
  { value: 'sluzba_mundurowa', label: 'Służba mundurowa' },
  { value: 'brak', label: 'Inna sytuacja / brak tytułu' },
]

const TRI_OPTIONS: { value: TriState; label: string }[] = [
  { value: '', label: 'Nie wiem / nie dotyczy' },
  { value: 'tak', label: 'Tak' },
  { value: 'nie', label: 'Nie' },
]

const CONTRACT_OPTIONS = [
  { value: 'czas_nieokreslony', label: 'Na czas nieokreślony' },
  { value: 'czas_okreslony', label: 'Na czas określony' },
  { value: 'okres_probny_powyzej_1_mies', label: 'Okres próbny — ponad miesiąc' },
  { value: 'okres_probny_do_1_mies', label: 'Okres próbny — do miesiąca' },
  { value: 'zastepstwo', label: 'Na zastępstwo' },
] as const

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

function Field({
  label,
  hint,
  required = false,
  children,
}: {
  label: string
  hint?: string
  required?: boolean
  children: (id: string) => ReactNode
}) {
  const id = useId()
  return (
    <div className="calc-field">
      <label htmlFor={id}>
        {label}
        {required && <span className="calc-required"><span aria-hidden="true">➜</span> wymagane</span>}
      </label>
      {children(id)}
      {hint && <p className="calc-hint">{hint}</p>}
    </div>
  )
}

function TriField({ label, value, onChange, hint }: { label: string; value: TriState; onChange: (value: TriState) => void; hint?: string }) {
  return (
    <Field label={label} hint={hint}>
      {(id) => (
        <select id={id} value={value} onChange={(e) => onChange(e.target.value as TriState)}>
          {TRI_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      )}
    </Field>
  )
}

function Amount({ b }: { b: Benefit }) {
  const w = b.wyliczenie
  if (!w || (w.kwota_miesieczna === null && w.kwota_jednorazowa === null))
    return <p className="calc-amount calc-amount-unknown">Kwota do ustalenia</p>
  const weeks = w.okresy.reduce((sum, p) => sum + (p.tygodnie ?? 0), 0)
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
      {zl(w.kwota_jednorazowa!)} <span>jednorazowo</span>
    </p>
  )
}

const MISSING_LABELS: Record<string, string> = {
  'ubezpieczenie.data_objecia_chorobowym': 'data początku ubezpieczenia chorobowego',
  'ubezpieczenie.przychody_12_miesiecy': 'miesięczne podstawy składek',
  'ubezpieczenie.zadeklarowana_podstawa_jdg': 'deklarowane podstawy składek z działalności',
  'wnioskodawca.adres_zamieszkania': 'adres zamieszkania',
  'wnioskodawca.legalny_pobyt_w_polsce': 'informacja o legalnym pobycie',
  'rodzina.dochod_rok_bazowy': 'dochód rodziny z roku bazowego',
  'dzieci[].hospitalizacja': 'daty hospitalizacji dziecka',
  'zdrowie.data_wyczerpania_zasilku': 'data wyczerpania okresu zasiłkowego',
  'zdrowie.ezla': 'informacja o zwolnieniach e-ZLA',
  'wyl.ma_ezla_kod_b': 'informacja, czy e-ZLA ma kod B',
  'wyl.spelnia_okres_wyczekiwania': 'okres wyczekiwania ubezpieczenia',
  'zdrowie.okres_zasilkowy_wykorzystany_dni': 'liczba wykorzystanych dni okresu zasiłkowego',
  'wyl.okres_zasilkowy_wyczerpany': 'informacja, czy wykorzystano cały okres zasiłkowy',
  'zdrowie.nadal_niezdolna_do_pracy': 'informacja o dalszej niezdolności do pracy',
  'zdrowie.rokowania_odzyskania_zdolnosci': 'rokowania odzyskania zdolności do pracy',
  'wyl.ubezpieczony_w_dniu_porodu': 'ubezpieczenie w dniu porodu',
  'rodzina.swiadczenie_za_granica': 'świadczenia rodzinne z innego kraju',
  'wyl.dochod_na_osobe': 'dochód na osobę w rodzinie',
  'ciaza.opieka_medyczna_od_10_tyg': 'opieka medyczna od 10. tygodnia ciąży',
}

function missingLabel(key: string) {
  return MISSING_LABELS[key] ?? key.split('.').slice(-1)[0].replaceAll('_', ' ')
}

function BenefitCard({ b, compact = false }: { b: Benefit; compact?: boolean }) {
  const meta = SHOWN[b.id] ?? b.nazwa
  const periods = (b.wyliczenie?.okresy ?? []).filter((p) => p.od && p.do)
  const variants = b.id === 'ZASILEK_MACIERZYNSKI_MATKA' ? maternityVariants(b) : null
  const statusLabel = b.status === 'przysluguje' ? 'Może przysługiwać' : b.status === 'brak_danych' ? 'Potrzeba więcej danych' : 'Warunek niespełniony'
  return (
    <li className={`calc-card calc-card-${b.status}${compact ? ' calc-card-compact' : ''}`}>
      <div className="calc-card-heading">
        <h4>{meta}</h4>
        <span className="calc-status">{statusLabel}</span>
      </div>
      {b.status === 'przysluguje' && <Amount b={b} />}
      {periods.map((p) => (
        <p className="calc-period" key={`${p.nazwa}-${p.od}`}>
          {p.nazwa}: {plDate(p.od!)} – {plDate(p.do!)}
          {p.tygodnie ? ` · ${p.tygodnie} tyg.` : ''}
          {p.procent ? ` · ${String(p.procent).replace('.', ',')}% podstawy` : ''}
        </p>
      ))}
      {b.wyliczenie?.kwota_laczna && periods.length > 0 && !(periods.reduce((t, p) => t + (p.tygodnie ?? 0), 0) < 4.3) ? (
        <p className="calc-total">Razem za wyliczony okres: {zl(b.wyliczenie.kwota_laczna)}</p>
      ) : null}
      {variants && (
        <p className="calc-variant">
          Wariant równy: {zl(variants.even)} miesięcznie (81,5%) przez cały okres. Wariant 100% + 70%: {zl(variants.split[0])}
          {' '}za macierzyński i {zl(variants.split[1])} za rodzicielski. Wniosek o 81,5% złóż do 21 dni po porodzie.
        </p>
      )}
      {b.przyczyny.length > 0 && (
        <ul className="calc-explanations">
          {b.przyczyny.map((reason) => <li key={reason}>{reason}</li>)}
        </ul>
      )}
      {b.brakujace_zmienne.length > 0 && b.status === 'brak_danych' && (
        <p className="calc-note"><strong>Potrzebne informacje:</strong> {b.brakujace_zmienne.map(missingLabel).join(', ')}.</p>
      )}
      {b.informacje.map((info) => <p className="calc-note" key={info}>{info}</p>)}
      {b.wyliczenie?.uwagi.map((note) => <p className="calc-note" key={note}>{note}</p>)}
      {b.do_weryfikacji && <p className="calc-note">Ten wynik wymaga dodatkowego potwierdzenia w ZUS lub właściwym urzędzie.</p>}
      <p className="calc-payer">Właściwa instytucja: {b.instytucja}</p>
    </li>
  )
}

const GROUP_LABELS: Record<string, string> = {
  pracodawca: 'U pracodawcy',
  zus: 'W ZUS',
  gmina: 'W gminie / OPS',
  usc: 'W urzędzie stanu cywilnego',
}

function ApplicationCard({ application }: { application: RequiredApplication }) {
  return (
    <li className="calc-application">
      <strong>{application.nazwa}</strong>
      <span>{GROUP_LABELS[application.grupa] ?? application.instytucja}</span>
      {application.termin_opis && <p>{application.termin_opis}{application.termin ? ` — termin: ${plDate(application.termin)}` : ''}</p>}
      {application.wysylka.length > 0 && <p>Jak złożyć: {application.wysylka.join(', ')}.</p>}
      {application.tylko_elektronicznie && <p>Wniosek można złożyć wyłącznie elektronicznie.</p>}
      {application.dla === 'drugi_rodzic' && <span className="calc-tag">dla drugiego rodzica</span>}
    </li>
  )
}

function Results({
  summaries,
  appUrl,
  adoption,
  childLoss,
}: {
  summaries: { title: string; summary: Summary }[]
  appUrl: string
  adoption: boolean
  childLoss: boolean
}) {
  return (
    <div className="calc-results">
      <h3>Wynik dopasowany do podanych danych</h3>
      {summaries.map(({ title, summary }) => (
        <section className="calc-result-section" key={title} aria-label={title}>
          <h4 className="calc-result-title">{title}</h4>
          {summary.risks.length > 0 && (
            <ul className="calc-risks">
              {summary.risks.map((r) => (
                <li className={`calc-risk-${r.poziom}`} key={r.id}>
                  <strong>{r.nazwa}.</strong> {r.komunikat}
                  {r.podstawa && <small> Podstawa: {r.podstawa}.</small>}
                </li>
              ))}
            </ul>
          )}
          {summary.planErrors.length > 0 && (
            <ul className="calc-risks">
              {summary.planErrors.map((issue) => <li key={issue.id}>{issue.komunikat}</li>)}
            </ul>
          )}
          {summary.granted.length > 0 && (
            <ul className="calc-cards">
              {summary.granted.map((b) => <BenefitCard key={b.id} b={b} />)}
            </ul>
          )}
          {summary.maybe.length > 0 && (
            <div className="calc-block">
              <h5>Możliwe świadczenia — brakuje informacji</h5>
              <ul className="calc-cards">
                {summary.maybe.map((b) => <BenefitCard key={b.id} b={b} />)}
              </ul>
            </div>
          )}
          {summary.notGranted.length > 0 && (
            <details className="calc-more calc-not-granted">
              <summary>Sprawdzone uprawnienia, których warunki nie są spełnione ({summary.notGranted.length})</summary>
              <ul className="calc-cards">
                {summary.notGranted.map((b) => <BenefitCard key={b.id} b={b} compact />)}
              </ul>
            </details>
          )}
          {summary.secondParent.length > 0 && (
            <div className="calc-block">
              <h5>Możliwe świadczenia drugiego rodzica</h5>
              <p>Jeśli dane o podstawach składek są niepełne, silnik pokaże je jako brakujące zamiast szacować kwotę.</p>
              <ul className="calc-cards">
                {summary.secondParent.map((b) => <BenefitCard key={b.id} b={b} />)}
              </ul>
            </div>
          )}
          {summary.applications.length > 0 && (
            <div className="calc-block">
              <h5>Co i gdzie złożyć</h5>
              <ul className="calc-applications">
                {summary.applications.map((application) => (
                  <ApplicationCard key={`${application.kod}-${application.dla}`} application={application} />
                ))}
              </ul>
            </div>
          )}
          {summary.deadlines.length > 0 && (
            <div className="calc-block">
              <h5>Terminy i ważne daty</h5>
              <ul className="calc-deadlines">
                {summary.deadlines.map((d) => (
                  <li key={`${d.data}-${d.opis}`}>
                    <time dateTime={d.data}>{plDate(d.data)}</time>
                    <span>{d.opis}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {summary.granted.length === 0 && summary.maybe.length === 0 && summary.notGranted.length === 0 && (
            <p className="calc-empty-result">Silnik nie zwrócił świadczeń do pokazania dla tego etapu. Uzupełnij dane albo sprawdź profil w aplikacji.</p>
          )}
        </section>
      ))}
      {childLoss && (
        <div className="calc-block calc-support">
          <h4>Nie musisz szukać wsparcia samodzielnie</h4>
          <p>W aplikacji jest osobna ścieżka z informacjami o pomocy po stracie dziecka i w trudnej sytuacji.</p>
          <a className="calc-cta" href={`${appUrl.replace(/\/$/, '')}/jaskolka`}>Zobacz dostępne wsparcie</a>
        </div>
      )}
      {adoption && <p className="calc-note">Okresy dla przyjęcia na wychowanie zależą też od wieku dziecka i dat postępowania sądowego.</p>}
      <div className="calc-block calc-sources">
        <h4>Sprawdź oficjalne informacje</h4>
        <ul>
          <li><a href="https://www.zus.pl/" target="_blank" rel="noreferrer">ZUS — informacje o zasiłkach</a></li>
          <li><a href="https://www.gov.pl/web/rodzina/urlop-rodzicielski" target="_blank" rel="noreferrer">MRPiPS — urlop rodzicielski</a></li>
          <li><a href="https://www.pip.gov.pl/dla-pracodawcow/poradyprawne/rodzicielstwo" target="_blank" rel="noreferrer">Państwowa Inspekcja Pracy — rodzicielstwo</a></li>
        </ul>
      </div>
      <a className="calc-cta" href={appUrl}>Przejdź do aplikacji i przygotuj wnioski</a>
    </div>
  )
}

function monthLabels(date: string) {
  if (!date) return Array.from({ length: 12 }, (_, i) => `Miesiąc ${i + 1}`)
  const birth = new Date(`${date}T00:00:00`)
  return Array.from({ length: 12 }, (_, i) => {
    const d = new Date(birth.getFullYear(), birth.getMonth() - 12 + i, 1)
    return d.toLocaleDateString('pl-PL', { month: 'long', year: 'numeric' })
  })
}

function defaultBaby(): BabyAnswer {
  return { weight: '', hospitalFrom: '', hospitalTo: '', zaZyciem: false }
}

function defaultChild(): ChildAnswer {
  return { date: '', studying: false, dependent: true, disabled: false, inPoland: 'tak' }
}

export function Calculator({ appUrl }: { appUrl: string }) {
  const [a, setA] = useState<Answers>({
    role: 'matka',
    stage: 'ciaza',
    date: '',
    childBirthDate: '',
    adoptionKind: 'przysposobienie',
    courtDate: '',
    adoptionFinalDate: '',
    delayedSchool: '',
    work: 'umowa_o_prace',
    sickness: '',
    insuranceStart: '',
    insuranceEnd: '',
    contractKind: 'czas_nieokreslony',
    contractEnd: '',
    endedInPregnancy: '',
    payerCount: '',
    incomeMode: 'average',
    gross: '',
    monthlyGross: Array(12).fill(''),
    jdgDebt: '',
    previousSicknessGap: '',
    previousSicknessBase: '',
    baseChangedInPregnancy: '',
    changedBaseDate: '',
    baseBeforeChange: '',
    baseAfterChange: '',
    changedConditionsInPregnancy: '',
    changedConditionsDate: '',
    pregnancyCare: '',
    sickLeave: '',
    sickFrom: '',
    sickTo: '',
    sickCodeB: '',
    sickDaysUsed: '',
    stillUnableToWork: '',
    recoveryLikely: '',
    exhaustionDate: '',
    motherStatus: '',
    motherInsured: '',
    childStatus: 'zywe',
    childDeathDate: '',
    babyCount: 1,
    pregnancyWeek: '',
    babies: [defaultBaby()],
    childInPoland: 'tak',
    adultsInFamily: '2',
    familyIncomeTaxed: '',
    familyIncomeUntaxed: '',
    familyIncomeLost: '',
    familyIncomeGained: '',
    familyIncomeYear: '',
    singleParent: '',
    foreignBenefit: '',
    alternatingCare: '',
    otherChildren: [],
    secondParentWork: '',
    secondParentSickness: '',
    secondParentInsuranceStart: '',
    secondParentInsuranceEnd: '',
    secondParentIncomeMode: 'average',
    secondParentGross: '',
    secondParentMonthlyGross: Array(12).fill(''),
    secondParentPayerCount: '',
    sharedHousehold: '',
    eightOneFive: false,
    workDuringLeave: false,
    leaveParent: 'matka',
    leaveFrom: '',
    leaveTo: '',
    leaveWorkFraction: '0.5',
    city: '',
    municipality: '',
    county: '',
    voivodeship: '',
    citizenship: 'PL',
    legalStay: 'tak',
    ukrStatus: 'nie',
    ukrActive: '',
  })
  const [state, setState] = useState<
    | { kind: 'idle' }
    | { kind: 'loading' }
    | { kind: 'error'; message: string }
    | { kind: 'done'; summaries: { title: string; summary: Summary }[] }
  >({ kind: 'idle' })
  const initialAnswers = useRef(a)
  const resultRef = useRef<HTMLDivElement>(null)
  const calculationId = useRef(0)
  const set = <K extends keyof Answers>(k: K, v: Answers[K]) => setA((prev) => ({ ...prev, [k]: v }))
  const insured = INSURED.includes(a.work)
  const asksSickness = insured && a.work !== 'umowa_o_prace'
  const payRequired = needsPay(a)
  const childLoss = a.stage === 'urodzone' && a.childStatus !== 'zywe'
  function applyDemo(specific: boolean) {
    const insuranceStart = isoDate(new Date(new Date().getFullYear() - 2, 0, 1))
    const demoAnswers = {
      ...initialAnswers.current,
      role: 'matka',
      stage: 'ciaza',
      date: defaultDueDate(),
      work: specific ? 'jdg' : 'umowa_o_prace',
      sickness: specific ? 'dobrowolne' : '',
      insuranceStart,
      gross: specific ? '5000' : '6500',
      pregnancyCare: 'tak',
      babyCount: specific ? 2 : 1,
      babies: Array.from({ length: specific ? 2 : 1 }, defaultBaby),
      city: 'Kraków',
      municipality: 'Kraków',
    } satisfies Answers
    setA(demoAnswers)
    void calculate(demoAnswers)
  }

  function changeStage(stage: Stage) {
    calculationId.current += 1
    setState({ kind: 'idle' })
    setA((prev) => ({
      ...prev,
      stage,
      date: '',
      adoptionKind: stage === 'adopcja_zastepcza' ? 'przysposobienie' : prev.adoptionKind,
      role:
        stage === 'adopcja_zastepcza'
          ? 'przysposabiajacy'
          : prev.role === 'przysposabiajacy' || prev.role.startsWith('rodzina_zastepcza')
            ? 'matka'
            : prev.role,
    }))
  }

  function resizeBabies(count: number) {
    setA((prev) => ({
      ...prev,
      babyCount: count,
      babies: Array.from({ length: count }, (_, i) => prev.babies[i] ?? defaultBaby()),
    }))
  }

  function updateBaby(index: number, key: keyof BabyAnswer, value: string | boolean) {
    setA((prev) => {
      const babies = [...prev.babies]
      babies[index] = { ...(babies[index] ?? defaultBaby()), [key]: value }
      return { ...prev, babies }
    })
  }

  async function fetchEvaluation(profile: Record<string, unknown>, evaluationDate?: string): Promise<Evaluation> {
    const qs = evaluationDate ? `?data_oceny=${encodeURIComponent(evaluationDate)}` : ''
    const res = await fetch(`${API_URL}/api/silnik/ocena${qs}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(profile),
    })
    if (!res.ok) throw new Error(`API zwróciło błąd HTTP ${res.status}.`)
    return (await res.json()) as Evaluation
  }

  async function calculate(answers: Answers) {
    const requestId = ++calculationId.current
    const problem = validate(answers)
    if (problem) {
      setState({ kind: 'error', message: problem })
      return
    }
    setState({ kind: 'loading' })
    const request = buildRequest(answers)
    try {
      const evaluations = await Promise.all([
        fetchEvaluation(request.profile),
        ...(request.futureProfile ? [fetchEvaluation(request.futureProfile, request.futureDate)] : []),
      ])
      if (requestId !== calculationId.current) return
      const summaries =
        answers.stage === 'ciaza'
          ? [
              { title: 'Twoja sytuacja teraz — ciąża', summary: summarize(evaluations[0]) },
              { title: 'Prognoza po porodzie', summary: summarize(evaluations[1]) },
            ]
          : [{ title: answers.stage === 'adopcja_zastepcza' ? 'Przyjęcie dziecka na wychowanie' : 'Twoja sytuacja', summary: summarize(evaluations[0]) }]
      setState({ kind: 'done', summaries })
      requestAnimationFrame(() => resultRef.current?.focus())
    } catch (error) {
      if (requestId !== calculationId.current) return
      console.error('Nie udało się obliczyć uprawnień:', error)
      if (error instanceof TypeError) {
        setState({
          kind: 'error',
          message: 'Nie udało się połączyć z kalkulatorem. Wypełnij wymagane pola, aby zobaczyć dostępne świadczenia, i spróbuj ponownie.',
        })
      } else {
        const detail = error instanceof Error ? error.message : 'Nieznany błąd'
        setState({ kind: 'error', message: `Nie udało się policzyć uprawnień. ${detail}` })
      }
    }
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    await calculate(a)
  }

  const referenceDate = a.stage === 'adopcja_zastepcza' ? a.date : a.date
  const labels = monthLabels(referenceDate)

  return (
    <section id="kalkulator" className="section calc-section" aria-labelledby="calc-title">
      <h2 id="calc-title">Policz, co może przysługiwać twojej rodzinie</h2>
      <p className="calc-intro">
        Zbierzemy fakty o ubezpieczeniu, rodzinie i planach urlopowych. Silnik pokaże szacunkowe kwoty, warunki,
        ryzyka, terminy i miejsce złożenia wniosków — a przy brakach nie będzie zgadywać.
      </p>
      <div className="calc-layout">
        <form className="calc-form" onSubmit={onSubmit} noValidate>
          <Choice
            legend="Jaka jest twoja sytuacja?"
            name="calc-stage"
            value={a.stage}
            options={[
              { value: 'ciaza', label: 'Ciąża' },
              { value: 'urodzone', label: 'Dziecko już się urodziło' },
              { value: 'adopcja_zastepcza', label: 'Adopcja / rodzina zastępcza' },
            ]}
            onChange={changeStage}
          />
          {a.stage === 'adopcja_zastepcza' ? (
            <>
              <Choice
                legend="Jaka jest podstawa przyjęcia dziecka?"
                name="calc-adoption"
                value={a.role as Extract<Role, 'przysposabiajacy' | 'rodzina_zastepcza_niezawodowa'>}
                options={[
                  { value: 'przysposabiajacy', label: 'Przysposobienie (adopcja)' },
                  { value: 'rodzina_zastepcza_niezawodowa', label: 'Rodzina zastępcza niezawodowa' },
                ]}
                onChange={(v) => setA((prev) => ({
                  ...prev,
                  role: v,
                  adoptionKind: v === 'przysposabiajacy' ? 'przysposobienie' : 'rodzina_zastepcza_niezawodowa',
                }))}
              />
              <Field label="Data przyjęcia dziecka na wychowanie" required>
                {(id) => <input id={id} type="date" value={a.date} onChange={(e) => set('date', e.target.value)} required />}
              </Field>
              <Field label="Data urodzenia przyjętego dziecka" required>
                {(id) => <input id={id} type="date" value={a.childBirthDate} onChange={(e) => set('childBirthDate', e.target.value)} required />}
              </Field>
              <TriField
                label="Czy dziecko mieszka w Polsce?"
                value={a.childInPoland}
                onChange={(v) => set('childInPoland', v)}
              />
              <TriField
                label="Czy sąd odroczył obowiązek szkolny dziecka?"
                value={a.delayedSchool}
                onChange={(v) => set('delayedSchool', v)}
              />
              <details className="calc-more">
                <summary>Daty postępowania sądowego</summary>
                <Field label="Data wystąpienia do sądu">
                  {(id) => <input id={id} type="date" value={a.courtDate} onChange={(e) => set('courtDate', e.target.value)} />}
                </Field>
                <Field label="Data uprawomocnienia orzeczenia (jeśli dotyczy)">
                  {(id) => <input id={id} type="date" value={a.adoptionFinalDate} onChange={(e) => set('adoptionFinalDate', e.target.value)} />}
                </Field>
              </details>
            </>
          ) : (
            <>
              <Choice
                legend="Którym rodzicem jesteś?"
                name="calc-role"
                value={a.role as 'matka' | 'ojciec'}
                options={[
                  { value: 'matka', label: 'Matką' },
                  { value: 'ojciec', label: 'Ojcem' },
                ]}
                onChange={(v) => set('role', v)}
              />
              <Field label={a.stage === 'ciaza' ? 'Przewidywany termin porodu' : 'Data urodzenia dziecka'} required>
                {(id) => <input id={id} type="date" value={a.date} onChange={(e) => set('date', e.target.value)} required />}
              </Field>
              {a.stage === 'ciaza' && (
                <TriField
                  label="Czy opieka lekarza lub położnej zaczęła się przed 10. tygodniem?"
                  value={a.pregnancyCare}
                  onChange={(v) => set('pregnancyCare', v)}
                  hint="Ta informacja ma znaczenie m.in. przy becikowym."
                />
              )}
              {a.stage === 'urodzone' && (
                <>
                  <Field label="Stan dziecka">
                    {(id) => (
                      <select id={id} value={a.childStatus} onChange={(e) => set('childStatus', e.target.value as Answers['childStatus'])}>
                        <option value="zywe">Dziecko żyje</option>
                        <option value="martwe">Martwe urodzenie</option>
                        <option value="zgon_do_8_tyg">Śmierć dziecka przed ukończeniem 8 tygodni</option>
                        <option value="zgon_po_8_tyg">Śmierć dziecka po ukończeniu 8 tygodni</option>
                      </select>
                    )}
                  </Field>
                  {a.childStatus.startsWith('zgon_') && (
                    <Field label="Data śmierci dziecka">
                      {(id) => <input id={id} type="date" value={a.childDeathDate} onChange={(e) => set('childDeathDate', e.target.value)} />}
                    </Field>
                  )}
                </>
              )}
            </>
          )}

          <div className="calc-location-fields">
            <Field label="Miejscowość, w której mieszkacie">
              {(id) => <input id={id} autoComplete="address-level2" value={a.city} onChange={(e) => set('city', e.target.value)} placeholder="np. Kraków" />}
            </Field>
            <Field label="Gmina">
              {(id) => <input id={id} value={a.municipality} onChange={(e) => set('municipality', e.target.value)} placeholder="Właściwy urząd świadczeń" />}
            </Field>
            <p className="calc-hint">Dzięki temu wynik wskaże, gdzie załatwiać sprawy gminne. Aktualnych lokalnych dopłat nie zgadujemy.</p>
          </div>

          {a.stage !== 'adopcja_zastepcza' && (
            <>
              <Field label="Ile dzieci urodziło się / ma się urodzić?">
                {(id) => (
                  <select id={id} value={a.babyCount} onChange={(e) => resizeBabies(Number(e.target.value))}>
                    {Array.from({ length: 10 }, (_, i) => i + 1).map((count) => (
                      <option key={count} value={count}>{count}</option>
                    ))}
                  </select>
                )}
              </Field>
            </>
          )}

          <Field label="Jaki masz tytuł ubezpieczenia / sytuację zawodową?">
            {(id) => (
              <select id={id} value={a.work} onChange={(e) => set('work', e.target.value as Work)}>
                {WORK_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
            )}
          </Field>
          {asksSickness && (
            <Field label="Jakie masz ubezpieczenie chorobowe?">
            {(id) => (
              <select id={id} value={a.sickness} onChange={(e) => set('sickness', e.target.value as Answers['sickness'])}>
                <option value="">Nie wiem</option>
                <option value="obowiazkowe">Obowiązkowe</option>
                <option value="dobrowolne">Dobrowolne</option>
                <option value="brak">Nie mam</option>
              </select>
            )}
            </Field>
          )}
          {insured && (
            <>
              <Field label="Od kiedy podlegasz ubezpieczeniu chorobowemu?" hint="Jeśli nie pamiętasz dokładnej daty, pozostaw puste — wynik oznaczy brakujące dane.">
                {(id) => <input id={id} type="date" value={a.insuranceStart} onChange={(e) => set('insuranceStart', e.target.value)} />}
              </Field>
              <Field label="Czy ubezpieczenie już ustało? Jeśli tak, podaj datę">
                {(id) => <input id={id} type="date" value={a.insuranceEnd} onChange={(e) => set('insuranceEnd', e.target.value)} />}
              </Field>
            </>
          )}
          {a.work === 'umowa_o_prace' && (
            <>
              <Field label="Rodzaj umowy o pracę">
                {(id) => (
                  <select id={id} value={a.contractKind} onChange={(e) => set('contractKind', e.target.value as Answers['contractKind'])}>
                    {CONTRACT_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                  </select>
                )}
              </Field>
              {a.contractKind !== 'czas_nieokreslony' && (
                <Field label="Data końca umowy">
                  {(id) => <input id={id} type="date" value={a.contractEnd} onChange={(e) => set('contractEnd', e.target.value)} />}
                </Field>
              )}
            </>
          )}
          {payRequired && (
            <details className="calc-more">
              <summary>Podstawa składek i dokładniejsze wyliczenie kwoty</summary>
              <Choice
                legend="Jak podać zarobki?"
                name="calc-income-mode"
                value={a.incomeMode}
                options={[
                  { value: 'average', label: 'Jedna średnia — szacunek' },
                  { value: 'monthly', label: 'Miesiąc po miesiącu' },
                ]}
                onChange={(v) => set('incomeMode', v)}
              />
              {a.incomeMode === 'average' ? (
                <Field
                  label={a.work === 'jdg' || a.work === 'wspolpraca_jdg' ? 'Przeciętna zadeklarowana podstawa składek (zł/mies.)' : 'Przeciętna podstawa składek brutto (zł/mies.)'}
                  hint="Wpisz podstawę, od której odprowadzano składki, nie kwotę „na rękę”. To tylko przybliżenie, jeśli podstawa się zmieniała."
                >
                  {(id) => (
                    <input id={id} type="number" min="0" max="1000000" step="0.01" inputMode="decimal" autoComplete="off" placeholder="np. 7000" value={a.gross} onChange={(e) => { const value = decimalInput(e.target.value); if (value !== null) set('gross', value) }} />
                  )}
                </Field>
              ) : (
                <div className="calc-month-grid">
                  <p className="calc-hint">Wpisz podstawę składek za pełne miesiące. Puste miesiące pozostaną nieznane.</p>
                  {labels.map((label, index) => (
                    <Field key={label} label={`${label} — zł`}>
                      {(id) => (
                        <input
                          id={id}
                          type="number"
                          min="0"
                          max="1000000"
                          step="0.01"
                          inputMode="decimal"
                          autoComplete="off"
                          placeholder="puste = brak danych"
                          value={a.monthlyGross[index] ?? ''}
                          onChange={(e) => {
                            const next = [...a.monthlyGross]
                            const value = decimalInput(e.target.value)
                            if (value === null) return
                            next[index] = value
                            set('monthlyGross', next)
                          }}
                        />
                      )}
                    </Field>
                  ))}
                </div>
              )}
            </details>
          )}

          <details className="calc-more">
            <summary>Rodzina, dochód i miejsce zamieszkania</summary>
            <Field label="Powiat">
              {(id) => <input id={id} value={a.county} onChange={(e) => set('county', e.target.value)} />
              }
            </Field>
            <Field label="Województwo">
              {(id) => <input id={id} autoComplete="address-level1" value={a.voivodeship} onChange={(e) => set('voivodeship', e.target.value)} />
              }
            </Field>
            <Field label="Liczba dorosłych we wspólnym gospodarstwie">
              {(id) => <input id={id} type="number" min="1" max="10" inputMode="numeric" value={a.adultsInFamily} onChange={(e) => set('adultsInFamily', e.target.value)} />}
            </Field>
            <TriField label="Czy samotnie wychowujesz dziecko?" value={a.singleParent} onChange={(v) => set('singleParent', v)} />
            <TriField label="Czy prowadzicie wspólne gospodarstwo domowe?" value={a.sharedHousehold} onChange={(v) => set('sharedHousehold', v)} />
            <TriField label="Czy jest ustalona opieka naprzemienna?" value={a.alternatingCare} onChange={(v) => set('alternatingCare', v)} />
            <TriField label="Czy pobierasz świadczenia rodzinne z innego kraju?" value={a.foreignBenefit} onChange={(v) => set('foreignBenefit', v)} />
            <Field label="Rok, którego dotyczą wpisane dochody">
              {(id) => <input id={id} type="number" min="1900" max={new Date().getFullYear()} step="1" inputMode="numeric" placeholder={String(new Date().getFullYear() - 1)} value={a.familyIncomeYear} onChange={(e) => set('familyIncomeYear', /^\d*$/.test(e.target.value) ? e.target.value : a.familyIncomeYear)} />}
            </Field>
            <Field label="Roczny dochód opodatkowany rodziny (zł)">
              {(id) => <input id={id} type="number" min="0" step="0.01" inputMode="decimal" value={a.familyIncomeTaxed} onChange={(e) => { const value = decimalInput(e.target.value); if (value !== null) set('familyIncomeTaxed', value) }} />}
            </Field>
            <Field label="Roczny dochód nieopodatkowany rodziny (zł)">
              {(id) => <input id={id} type="number" min="0" step="0.01" inputMode="decimal" value={a.familyIncomeUntaxed} onChange={(e) => { const value = decimalInput(e.target.value); if (value !== null) set('familyIncomeUntaxed', value) }} />}
            </Field>
            <Field label="Dochód utracony (zł)">
              {(id) => <input id={id} type="number" min="0" step="0.01" inputMode="decimal" value={a.familyIncomeLost} onChange={(e) => { const value = decimalInput(e.target.value); if (value !== null) set('familyIncomeLost', value) }} />
              }
            </Field>
            <Field label="Dochód uzyskany (zł)">
              {(id) => <input id={id} type="number" min="0" step="0.01" inputMode="decimal" value={a.familyIncomeGained} onChange={(e) => { const value = decimalInput(e.target.value); if (value !== null) set('familyIncomeGained', value) }} />
              }
            </Field>
            <fieldset className="calc-field">
              <legend>Inne dzieci w rodzinie</legend>
              {a.otherChildren.map((child, index) => (
                <div className="calc-child-fields" key={index}>
                  <Field label={`Data urodzenia dziecka ${index + 1}`}>
                    {(id) => <input id={id} type="date" value={child.date} onChange={(e) => {
                      const next = [...a.otherChildren]
                      next[index] = { ...child, date: e.target.value }
                      set('otherChildren', next)
                    }} />}
                  </Field>
                  <label className="calc-check"><input type="checkbox" checked={child.dependent} onChange={(e) => {
                    const next = [...a.otherChildren]
                    next[index] = { ...child, dependent: e.target.checked }
                    set('otherChildren', next)
                  }} />Na utrzymaniu rodziny</label>
                  <label className="calc-check"><input type="checkbox" checked={child.studying} onChange={(e) => {
                    const next = [...a.otherChildren]
                    next[index] = { ...child, studying: e.target.checked }
                    set('otherChildren', next)
                  }} />Uczy się</label>
                  <label className="calc-check"><input type="checkbox" checked={child.disabled} onChange={(e) => {
                    const next = [...a.otherChildren]
                    next[index] = { ...child, disabled: e.target.checked }
                    set('otherChildren', next)
                  }} />Ma orzeczenie o niepełnosprawności</label>
                  <TriField label={`Czy dziecko ${index + 1} mieszka w Polsce?`} value={child.inPoland} onChange={(v) => {
                    const next = [...a.otherChildren]
                    next[index] = { ...child, inPoland: v }
                    set('otherChildren', next)
                  }} />
                  <button className="calc-small-button" type="button" onClick={() => set('otherChildren', a.otherChildren.filter((_, i) => i !== index))}>Usuń dziecko</button>
                </div>
              ))}
              <button className="calc-small-button" type="button" disabled={a.otherChildren.length >= 10} onClick={() => set('otherChildren', [...a.otherChildren, defaultChild()])}>
                Dodaj dziecko
              </button>
            </fieldset>
          </details>

          {a.stage !== 'adopcja_zastepcza' && (
            <details className="calc-more">
              <summary>Zdrowie, wcześniactwo i szczególne okoliczności</summary>
              {a.stage === 'ciaza' && (
                <Field label="Który to tydzień ciąży (jeśli znasz)?">
                  {(id) => <input id={id} type="number" min="1" max="45" inputMode="numeric" value={a.pregnancyWeek} onChange={(e) => set('pregnancyWeek', e.target.value)} />}
                </Field>
              )}
              <TriField label="Czy masz obecnie e-ZLA?" value={a.sickLeave} onChange={(v) => set('sickLeave', v)} />
              {a.sickLeave === 'tak' && (
                <>
                  <Field label="Początek e-ZLA">
                    {(id) => <input id={id} type="date" value={a.sickFrom} onChange={(e) => set('sickFrom', e.target.value)} />}
                  </Field>
                  <Field label="Koniec e-ZLA (jeśli znany)">
                    {(id) => <input id={id} type="date" value={a.sickTo} onChange={(e) => set('sickTo', e.target.value)} />}
                  </Field>
                  <TriField label="Czy e-ZLA ma kod B?" value={a.sickCodeB} onChange={(v) => set('sickCodeB', v)} />
                </>
              )}
              <Field label="Ile dni okresu zasiłkowego wykorzystano?">
                {(id) => <input id={id} type="number" min="0" inputMode="numeric" value={a.sickDaysUsed} onChange={(e) => set('sickDaysUsed', e.target.value)} />}
              </Field>
              <TriField label="Czy nadal jesteś niezdolna/niezdolny do pracy?" value={a.stillUnableToWork} onChange={(v) => set('stillUnableToWork', v)} />
              <TriField label="Czy lekarz przewiduje odzyskanie zdolności do pracy?" value={a.recoveryLikely} onChange={(v) => set('recoveryLikely', v)} />
              <Field label="Przewidywana data wyczerpania zasiłku chorobowego">
                {(id) => <input id={id} type="date" value={a.exhaustionDate} onChange={(e) => set('exhaustionDate', e.target.value)} />}
              </Field>
              <TriField
                label="Czy doszło do zmiany podstawy składek w ciąży?"
                value={a.baseChangedInPregnancy}
                onChange={(v) => set('baseChangedInPregnancy', v)}
                hint="Silnik pokaże ostrzeżenie o ryzyku ponownej weryfikacji podstawy."
              />
              {a.baseChangedInPregnancy === 'tak' && (
                <>
                  <Field label="Data zmiany podstawy">
                    {(id) => <input id={id} type="date" value={a.changedBaseDate} onChange={(e) => set('changedBaseDate', e.target.value)} />}
                  </Field>
                  <Field label="Podstawa przed zmianą (zł)">
                    {(id) => <input id={id} type="number" min="0" step="0.01" inputMode="decimal" value={a.baseBeforeChange} onChange={(e) => { const value = decimalInput(e.target.value); if (value !== null) set('baseBeforeChange', value) }} />}
                  </Field>
                  <Field label="Podstawa po zmianie (zł)">
                    {(id) => <input id={id} type="number" min="0" step="0.01" inputMode="decimal" value={a.baseAfterChange} onChange={(e) => { const value = decimalInput(e.target.value); if (value !== null) set('baseAfterChange', value) }} />}
                  </Field>
                </>
              )}
              <TriField
                label="Czy w ciąży zmieniły się warunki zatrudnienia?"
                value={a.changedConditionsInPregnancy}
                onChange={(v) => set('changedConditionsInPregnancy', v)}
              />
              {a.changedConditionsInPregnancy === 'tak' && (
                <Field label="Data zmiany warunków zatrudnienia">
                  {(id) => <input id={id} type="date" value={a.changedConditionsDate} onChange={(e) => set('changedConditionsDate', e.target.value)} />}
                </Field>
              )}
              {a.work === 'umowa_o_prace' && (
                <>
                  <TriField
                    label="Czy umowa została rozwiązana w ciąży?"
                    value={a.endedInPregnancy}
                    onChange={(v) => set('endedInPregnancy', v)}
                  />
                  <Field label="Liczba osób zgłoszonych do ubezpieczenia przez płatnika">
                    {(id) => <input id={id} type="number" min="0" inputMode="numeric" value={a.payerCount} onChange={(e) => set('payerCount', e.target.value)} />}
                  </Field>
                </>
              )}
              {(a.work === 'jdg' || a.work === 'wspolpraca_jdg') && (
                <>
                  <Field label="Zadłużenie składkowe na dzień powstania prawa (zł)">
                    {(id) => <input id={id} type="number" min="0" step="0.01" inputMode="decimal" value={a.jdgDebt} onChange={(e) => { const value = decimalInput(e.target.value); if (value !== null) set('jdgDebt', value) }} />}
                  </Field>
                  <p className="calc-hint">Kalkulator nie sprawdza konta ZUS ani nie wystawia zaświadczenia — podaj kwotę z eZUS, jeśli ją znasz.</p>
                </>
              )}
              <Field label="Przerwa od poprzedniego zasiłku chorobowego (dni)">
                {(id) => <input id={id} type="number" min="0" inputMode="numeric" value={a.previousSicknessGap} onChange={(e) => set('previousSicknessGap', e.target.value)} />}
              </Field>
              <Field label="Podstawa poprzedniego zasiłku (zł/mies.)">
                {(id) => <input id={id} type="number" min="0" step="0.01" inputMode="decimal" value={a.previousSicknessBase} onChange={(e) => { const value = decimalInput(e.target.value); if (value !== null) set('previousSicknessBase', value) }} />}
              </Field>
              {a.stage === 'urodzone' && (
                <>
                  {a.babyCount > 1 && <Field label="W którym tygodniu ciąży nastąpił poród?">
                    {(id) => <input id={id} type="number" min="1" max="45" inputMode="numeric" value={a.pregnancyWeek} onChange={(e) => set('pregnancyWeek', e.target.value)} />}
                  </Field>}
                  {a.babies.map((baby, index) => (
                    <fieldset className="calc-field calc-baby" key={index}>
                      <legend>Dziecko {index + 1}</legend>
                      <Field label="Masa urodzeniowa (g)">
                        {(id) => <input id={id} type="number" min="200" max="7000" inputMode="numeric" value={baby.weight} onChange={(e) => updateBaby(index, 'weight', e.target.value)} />}
                      </Field>
                      <TriField label="Czy dziecko ma zaświadczenie „Za życiem”?" value={baby.zaZyciem ? 'tak' : 'nie'} onChange={(v) => updateBaby(index, 'zaZyciem', v === 'tak')} />
                      <Field label="Pobyt w szpitalu — od">
                        {(id) => <input id={id} type="date" value={baby.hospitalFrom} onChange={(e) => updateBaby(index, 'hospitalFrom', e.target.value)} />}
                      </Field>
                      <Field label="Pobyt w szpitalu — do">
                        {(id) => <input id={id} type="date" value={baby.hospitalTo} onChange={(e) => updateBaby(index, 'hospitalTo', e.target.value)} />}
                      </Field>
                    </fieldset>
                  ))}
                </>
              )}
              <Field label="Stan biologicznej matki (jeśli ma znaczenie dla sprawy)">
                {(id) => (
                  <select id={id} value={a.motherStatus} onChange={(e) => set('motherStatus', e.target.value as Answers['motherStatus'])}>
                    <option value="">Nie dotyczy / nie wiem</option>
                    <option value="zyje">Żyje</option>
                    <option value="zmarla">Zmarła</option>
                    <option value="porzucila_dziecko">Porzuciła dziecko</option>
                  </select>
                )}
              </Field>
            </details>
          )}

          <details className="calc-more">
            <summary>Drugi rodzic i plan urlopów</summary>
            <Field label="Tytuł ubezpieczenia drugiego rodzica">
              {(id) => (
                <select id={id} value={a.secondParentWork} onChange={(e) => set('secondParentWork', e.target.value as Work | '')}>
                  <option value="">Nie sprawdzaj / nie wiem</option>
                  {WORK_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                </select>
              )}
            </Field>
            {a.secondParentWork && needsPay({ ...a, work: a.secondParentWork, sickness: a.secondParentSickness }) && (
              <>
                {a.secondParentWork !== 'umowa_o_prace' && (
                  <Field label="Ubezpieczenie chorobowe drugiego rodzica">
                    {(id) => (
                      <select id={id} value={a.secondParentSickness} onChange={(e) => set('secondParentSickness', e.target.value as Answers['secondParentSickness'])}>
                        <option value="">Nie wiem</option>
                        <option value="obowiazkowe">Obowiązkowe</option>
                        <option value="dobrowolne">Dobrowolne</option>
                        <option value="brak">Brak</option>
                      </select>
                    )}
                  </Field>
                )}
                <Field label="Data objęcia ubezpieczeniem chorobowym drugiego rodzica" hint="Jeśli nie znasz daty, pozostaw puste — wynik oznaczy brakujące dane.">
                  {(id) => <input id={id} type="date" value={a.secondParentInsuranceStart} onChange={(e) => set('secondParentInsuranceStart', e.target.value)} />}
                </Field>
                <Field label="Data ustania ubezpieczenia (jeśli ustało)">
                  {(id) => <input id={id} type="date" value={a.secondParentInsuranceEnd} onChange={(e) => set('secondParentInsuranceEnd', e.target.value)} />}
                </Field>
                <Field label="Liczba osób zgłoszonych do ubezpieczenia chorobowego przez płatnika">
                  {(id) => <input id={id} type="number" min="0" step="1" value={a.secondParentPayerCount} onChange={(e) => set('secondParentPayerCount', e.target.value)} />}
                </Field>
                <fieldset className="calc-field">
                  <legend>Podstawa składek drugiego rodzica</legend>
                  <div className="calc-pills">
                    <label className={`calc-pill${a.secondParentIncomeMode === 'average' ? ' is-on' : ''}`}>
                      <input type="radio" name="second-parent-income-mode" checked={a.secondParentIncomeMode === 'average'} onChange={() => set('secondParentIncomeMode', 'average')} />
                      Jedna średnia miesięczna
                    </label>
                    <label className={`calc-pill${a.secondParentIncomeMode === 'monthly' ? ' is-on' : ''}`}>
                      <input type="radio" name="second-parent-income-mode" checked={a.secondParentIncomeMode === 'monthly'} onChange={() => set('secondParentIncomeMode', 'monthly')} />
                      Każdy miesiąc osobno
                    </label>
                  </div>
                </fieldset>
                {a.secondParentIncomeMode === 'average' ? (
                  <Field label="Średnia miesięczna podstawa składek (zł)">
                    {(id) => <input id={id} type="number" min="0" max="1000000" step="0.01" value={a.secondParentGross} onChange={(e) => set('secondParentGross', e.target.value)} />}
                  </Field>
                ) : (
                  <div className="calc-grid">
                    {a.secondParentMonthlyGross.map((value, index) => (
                      <Field key={index} label={`Podstawa składek — ${labels[index]} (zł)`}>
                        {(id) => (
                          <input
                            id={id}
                            type="number"
                            min="0"
                            max="1000000"
                            step="0.01"
                            value={value}
                            onChange={(e) => set('secondParentMonthlyGross', a.secondParentMonthlyGross.map((v, i) => (i === index ? e.target.value : v)))}
                          />
                        )}
                      </Field>
                    ))}
                  </div>
                )}
                <p className="calc-hint">Podaj podstawę, od której faktycznie opłacono składki, a nie samo wynagrodzenie brutto. Puste miesiące nie zostaną oszacowane.</p>
              </>
            )}
            {a.stage !== 'adopcja_zastepcza' && a.role === 'matka' && (
              <label className="calc-check">
                <input type="checkbox" checked={a.eightOneFive} onChange={(e) => set('eightOneFive', e.target.checked)} />
                Zasymuluj wybór równej stawki 81,5% (wniosek do 21 dni po porodzie)
              </label>
            )}
            <label className="calc-check">
              <input type="checkbox" checked={a.workDuringLeave} onChange={(e) => set('workDuringLeave', e.target.checked)} />
              Planuję łączyć urlop rodzicielski z pracą
            </label>
            {a.workDuringLeave && (
              <>
                {a.stage === 'adopcja_zastepcza' ? (
                  <p className="calc-hint">Ta symulacja dotyczy urlopu wnioskodawcy, który przyjął dziecko na wychowanie.</p>
                ) : (
                  <Field label="Który rodzic będzie na tej części urlopu?">
                    {(id) => (
                      <select id={id} value={a.leaveParent} onChange={(e) => set('leaveParent', e.target.value as Answers['leaveParent'])}>
                        <option value="matka">Matka</option>
                        <option value="ojciec">Ojciec</option>
                      </select>
                    )}
                  </Field>
                )}
                <Field label="Urlop rodzicielski — od">
                  {(id) => <input id={id} type="date" value={a.leaveFrom} onChange={(e) => set('leaveFrom', e.target.value)} />}
                </Field>
                <Field label="Urlop rodzicielski — do">
                  {(id) => <input id={id} type="date" value={a.leaveTo} onChange={(e) => set('leaveTo', e.target.value)} />}
                </Field>
                <Field label="Wymiar pracy w tym czasie">
                  {(id) => (
                    <select id={id} value={a.leaveWorkFraction} onChange={(e) => set('leaveWorkFraction', e.target.value)}>
                      <option value="0.25">1/4 etatu</option>
                      <option value="0.5">1/2 etatu</option>
                    </select>
                  )}
                </Field>
              </>
            )}
            {a.stage !== 'adopcja_zastepcza' && a.role === 'ojciec' && (
              <TriField label="Czy matka jest ubezpieczona w dniu porodu?" value={a.motherInsured} onChange={(v) => set('motherInsured', v)} />
            )}
          </details>

          <details className="calc-more">
            <summary>Obywatelstwo i status pobytu</summary>
            <Field label="Obywatelstwo">
              {(id) => <input id={id} value={a.citizenship} onChange={(e) => set('citizenship', e.target.value.toUpperCase())} placeholder="np. PL" maxLength={3} />}
            </Field>
            <TriField label="Czy masz legalny pobyt w Polsce?" value={a.legalStay} onChange={(v) => set('legalStay', v)} />
            <TriField label="Czy masz status UKR?" value={a.ukrStatus} onChange={(v) => set('ukrStatus', v)} />
            {a.ukrStatus === 'tak' && <TriField label="Czy jesteś aktywna/y zawodowo?" value={a.ukrActive} onChange={(v) => set('ukrActive', v)} />}
          </details>

          <button className="calc-submit" type="submit" disabled={state.kind === 'loading'}>
            {state.kind === 'loading' ? 'Sprawdzam uprawnienia…' : 'Sprawdź świadczenia i terminy'}
          </button>
          <div className="calc-demos">
            <strong>Wypróbuj kalkulator</strong>
            <p>Wstaw przykładowe dane — możesz je potem zmienić.</p>
            <div>
              <button className="calc-small-button" type="button" disabled={state.kind === 'loading'} onClick={() => applyDemo(false)}>Typowa sytuacja</button>
              <button className="calc-small-button" type="button" disabled={state.kind === 'loading'} onClick={() => applyDemo(true)}>Bliźnięta + własna firma</button>
            </div>
            <span className="calc-demo-label">Oba zestawy są wyłącznie demonstracyjne (DEMO), nie opisują prawdziwej osoby.</span>
          </div>
        </form>
        <div className={`calc-output${state.kind === 'idle' ? ' calc-output-idle' : ''}`} ref={resultRef} tabIndex={-1} aria-live="polite">
          {state.kind === 'idle' && (
            <div className="calc-empty">
              <div className="calc-empty-copy">
                <h3>Opowiedz nam o sobie</h3>
                <p>Po wypełnieniu pól pomożemy Ci znaleźć świadczenia, które mogą przysługiwać Twojej rodzinie. Nie musisz znać wszystkich szczegółów — brakujące informacje pokażemy w wynikach.</p>
              </div>
            </div>
          )}
          {state.kind === 'idle' && (
            <div className="calc-empty-spirals" aria-hidden="true">
              {Array.from({ length: 8 }, (_, spiral) => (
                <svg className="calc-empty-spiral" key={spiral} viewBox="0 0 140 140">
                  <path d="M 84 18 C 53 10 23 30 18 60 C 12 96 43 124 78 114 C 113 104 126 64 102 39 C 83 19 52 27 43 49 C 34 71 52 89 70 82 C 85 76 86 58 74 50 C 64 43 52 49 53 60" />
                </svg>
              ))}
            </div>
          )}
          {state.kind === 'loading' && (
            <div className="calc-empty">
              <p>Sprawdzam uprawnienia, ryzyka i terminy…</p>
            </div>
          )}
          {state.kind === 'error' && (
            <div className="calc-empty calc-error" role="alert">
              <p>{state.message}</p>
            </div>
          )}
          {state.kind === 'done' && (
            <Results
              summaries={state.summaries}
              appUrl={appUrl}
              adoption={a.stage === 'adopcja_zastepcza'}
              childLoss={childLoss}
            />
          )}
        </div>
      </div>
    </section>
  )
}
