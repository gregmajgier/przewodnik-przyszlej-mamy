import { useEffect, useRef } from 'react'

interface Props {
  busy: boolean
  error: string | null
  onConfirm: () => void
  onCancel: () => void
}

/** Podpis Profilem Zaufanym: potwierdzenie, że dane we wniosku się zgadzają. */
export default function SignModal({ busy, error, onConfirm, onCancel }: Props) {
  const confirmRef = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    confirmRef.current?.focus()
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape' && !busy) onCancel()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [busy, onCancel])

  return (
    <div className="modal-backdrop">
      <div className="modal card stack" role="dialog" aria-modal="true" aria-labelledby="sign-h">
        <h2 id="sign-h">
          Podpisz Profilem Zaufanym
        </h2>
        <p>
          Potwierdzasz, że dane we wniosku są prawdziwe i chcesz go podpisać. Po podpisaniu zmiana danych wymaga
          ponownego podpisu.
        </p>
        {error && (
          <p role="alert" className="alert">
            {error}
          </p>
        )}
        <div className="row">
          <button ref={confirmRef} type="button" className="btn" disabled={busy} onClick={onConfirm}>
            Podpisz
          </button>
          <button type="button" className="btn btn-secondary" disabled={busy} onClick={onCancel}>
            Anuluj
          </button>
        </div>
      </div>
    </div>
  )
}
