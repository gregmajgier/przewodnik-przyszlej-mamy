import RisksPanel from './RisksPanel'

export default function RisksWidget() {
  return (
    <section className="card stack" aria-labelledby="risks-h">
      <h2 id="risks-h">Ostrzeżenia</h2>
      <RisksPanel />
    </section>
  )
}
