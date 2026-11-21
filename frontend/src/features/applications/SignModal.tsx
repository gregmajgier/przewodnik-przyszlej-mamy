import { useEffect, useRef } from 'react'

interface Props {
  busy: boolean
  error: string | null
  onConfirm: () => void
  onCancel: () => void
}

/** Symulowany podpis Profilem Zaufanym — w prawdziwej aplikacji tu byłoby przekierowanie do gov.pl. */
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
          Podpisz Profilem Zaufanym <span className="badge-sim">SYMULACJA</span>
        </h2>
        <p>
          To symulacja podpisu. Nic nie wysyłamy do gov.pl — potwierdzasz tylko, że dane we wniosku się zgadzają i
          chcesz go podpisać.
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
