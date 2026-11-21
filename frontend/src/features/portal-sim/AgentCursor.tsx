interface Props {
  /** Położenie czubka kursora względem lewego górnego rogu ramki (px). */
  x: number
  y: number
  label?: string
}

/** Widoczny kursor agenta (kolor AI). Ruch jest wygaszany przez `prefers-reduced-motion` (patrz CSS). */
export default function AgentCursor({ x, y, label = 'AI' }: Props) {
  return (
    <div className="agent-cursor" style={{ transform: `translate(${x}px, ${y}px)` }} aria-hidden="true" data-testid="agent-cursor">
      <span className="agent-cursor-label">{label}</span>
    </div>
  )
}
