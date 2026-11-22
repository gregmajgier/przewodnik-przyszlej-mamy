import { useMemo, useState } from 'react'
import { formatPln } from '../../lib/format'
import { useSession } from '../../lib/session'
import { Icon } from '../../ui/Icon'
import { PageHeader, Pill, Segmented } from '../../ui/controls'
import { BenefitSheet, STATUS_TONE } from './BenefitSheet'
import { CATS, catMeta, categoryOf, shortAmount } from './categories'
import { Rates } from './Rates'
import type { CatKey } from './categories'
import { STATUS_LABEL } from './types'
import type { BenefitMatch } from './types'
import { useBenefits } from './useBenefits'
import '../../ui/ui.css'
import './benefits.css'

type View = 'yours' | 'check' | 'all'

function normalize(s: string) {
  return s
    .toLowerCase()
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .replace(/ł/g, 'l')
}

export default function BenefitsPage() {
  const { family } = useSession()
  const { items, error, busyId, answer } = useBenefits(!!family)
  const [view, setView] = useState<View>('yours')
  const [cat, setCat] = useState<CatKey | 'all'>('all')
  const [query, setQuery] = useState('')
  const [openId, setOpenId] = useState<string | null>(null)

  const all = useMemo(() => items ?? [], [items])
  const fits = all.filter((m) => m.match.status === 'fits')
  const maybe = all.filter((m) => m.match.status === 'maybe')
  const annual = fits.reduce((s, m) => s + (m.benefit.annual_value_estimate ?? 0), 0)

  const filtered = useMemo(() => {
    const q = normalize(query.trim())
    return all
      .filter((m) => (view === 'yours' ? m.match.status === 'fits' : view === 'check' ? m.match.status === 'maybe' : true))
      .filter((m) => cat === 'all' || categoryOf(m.benefit) === cat)
      .filter((m) => !q || normalize(`${m.benefit.name} ${m.benefit.description}`).includes(q))
  }, [all, view, cat, query])

  const featured = [...fits].sort((a, b) => (b.benefit.annual_value_estimate ?? 0) - (a.benefit.annual_value_estimate ?? 0)).slice(0, 4)
  const groups = CATS.map((c) => ({ ...c, items: filtered.filter((m) => categoryOf(m.benefit) === c.key) })).filter((g) => g.items.length > 0)
  const presentCats = CATS.filter((c) => all.some((m) => categoryOf(m.benefit) === c.key))
  const open = all.find((m) => m.benefit.id === openId) ?? null

  return (
    <div className="page benefits">
      <PageHeader title="Baza świadczeń" eyebrow="Pieniądze, urlopy i ulgi">
        <p className="muted benefits-lead">
          Wszystko, co przysługuje rodzinom w Polsce i w Twojej gminie, z dopasowaniem do Waszej sytuacji.
        </p>
      </PageHeader>

      {error && (
        <p role="alert" className="alert">
          {error}
        </p>
      )}
      {!items && !error && (
        <div className="featured" role="status" aria-label="Wczytuję świadczenia">
          <div className="skeleton featured-card" />
          <div className="skeleton featured-card" />
        </div>
      )}

      {items && (
        <>
          <section className="benefits-summary rise" aria-label="Podsumowanie">
            {annual > 0 && (
              <div className="benefits-summary-wide">
                <span className="benefits-summary-num">{formatPln(annual)}</span>
                <span>rocznie, szacunkowo, z tego, co już pasuje</span>
              </div>
            )}
            <button
              type="button"
              aria-label="Pokaż świadczenia, które pasują do Was"
              aria-pressed={view === 'yours'}
              onClick={() => setView('yours')}
            >
              <span className="benefits-summary-num">{fits.length}</span>
              <span>pasuje do Was</span>
            </button>
            <button
              type="button"
              aria-label="Pokaż świadczenia do sprawdzenia"
              aria-pressed={view === 'check'}
              onClick={() => setView('check')}
            >
              <span className="benefits-summary-num">{maybe.length}</span>
              <span>do sprawdzenia</span>
            </button>
          </section>

          {featured.length > 0 && view === 'yours' && cat === 'all' && !query && (
            <section className="section" aria-labelledby="feat-h">
              <h2 id="feat-h">Najwięcej dla Was</h2>
              <div className="featured">
                {featured.map((m, i) => {
                  const c = catMeta(categoryOf(m.benefit))
                  return (
                    <button
                      key={m.benefit.id}
                      type="button"
                      className={`featured-card tone-${c.tone} rise`}
                      style={{ ['--i' as string]: i }}
                      onClick={() => setOpenId(m.benefit.id)}
                    >
                      <span className="featured-icon">
                        <Icon name={c.icon} size={24} />
                      </span>
                      <span className="featured-name">{m.benefit.name}</span>
                      {m.benefit.annual_value_estimate ? (
                        <span className="featured-value">
                          ok. {formatPln(m.benefit.annual_value_estimate)}
                          <small> / rok</small>
                        </span>
                      ) : (
                        <span className="featured-value">{shortAmount(m.benefit) ?? c.label}</span>
                      )}
                    </button>
                  )
                })}
              </div>
            </section>
          )}

          <section className="section benefits-browser" aria-label="Przeglądaj świadczenia">
            <div className="benefits-controls">
              <Segmented
                label="Pokaż"
                value={view}
                onChange={setView}
                options={[
                  { value: 'yours', label: 'Dla Was', count: fits.length },
                  { value: 'check', label: 'Sprawdź', count: maybe.length },
                  { value: 'all', label: 'Wszystkie' },
                ]}
              />
              <label className="search">
                <Icon name="search" size={20} />
                <span className="sr-only">Szukaj świadczenia</span>
                <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Szukaj, np. żłobek, urlop, 800+" />
              </label>
            </div>
            <div className="cat-chips" role="group" aria-label="Kategorie">
              <button type="button" className="cat-chip" aria-pressed={cat === 'all'} onClick={() => setCat('all')}>
                Wszystko
              </button>
              {presentCats.map((c) => (
                <button key={c.key} type="button" className="cat-chip" aria-pressed={cat === c.key} onClick={() => setCat(c.key)}>
                  <Icon name={c.icon} size={17} />
                  {c.label}
                </button>
              ))}
            </div>

            {groups.length === 0 && (
              <div className="card empty">
                <Icon name="search" size={32} />
                <p>Nic tu nie ma. Zmień filtr albo wyszukiwanie.</p>
              </div>
            )}

            {groups.map((g) => (
              <div key={g.key} className="benefit-group">
                <h3 className="benefit-group-h">
                  <span className={`icon-tile tone-${g.tone}`}>
                    <Icon name={g.icon} size={20} />
                  </span>
                  {g.label}
                  <span className="benefit-group-n">{g.items.length}</span>
                </h3>
                <div className="card benefit-list">
                  <ul className="list">
                    {g.items.map((m: BenefitMatch) => {
                      const amount = shortAmount(m.benefit)
                      return (
                        <li key={m.benefit.id}>
                          <button type="button" className="list-row" onClick={() => setOpenId(m.benefit.id)}>
                            <span className="list-row-main">
                              <span className="list-row-title">{m.benefit.name}</span>
                              <span className="list-row-sub benefit-row-sub">{m.benefit.description}</span>
                            </span>
                            <span className="list-row-end benefit-row-end">
                              {amount && <span className="matter-amount">{amount}</span>}
                              <Pill tone={STATUS_TONE[m.match.status]} dot>
                                {STATUS_LABEL[m.match.status]}
                              </Pill>
                            </span>
                          </button>
                        </li>
                      )
                    })}
                  </ul>
                </div>
              </div>
            ))}
          </section>
        </>
      )}

      {items && <Rates />}

      <BenefitSheet item={open} onClose={() => setOpenId(null)} onAnswer={answer} busy={busyId === openId} />
    </div>
  )
}
