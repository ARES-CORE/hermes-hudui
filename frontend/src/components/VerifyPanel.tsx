import { useState } from 'react'
import Panel from './Panel'

export default function VerifyPanel({ className = '', embedded = false }: { className?: string; embedded?: boolean }) {
  const [receiptPath, setReceiptPath] = useState('')
  const [replayPath, setReplayPath] = useState('')
  const [result, setResult] = useState<any>(null)
  const [busy, setBusy] = useState(false)

  const verify = async () => {
    setBusy(true)
    try {
      const res = await fetch('/api/replay/verify', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ receipt_path: receiptPath, replay_path: replayPath }),
      })
      if (!res.ok) throw new Error(await res.text())
      setResult(await res.json())
    } catch (error) {
      setResult({ ok: false, errors: [error instanceof Error ? error.message : String(error)], warnings: [] })
    } finally {
      setBusy(false)
    }
  }

  const content = (
    <>
      <div className="space-y-2">
        <input
          value={receiptPath}
          onChange={event => setReceiptPath(event.target.value)}
          placeholder="receipt.json path"
          className="w-full px-2 py-1 text-[12px] outline-none"
          style={{ background: 'var(--hud-bg-deep)', border: '1px solid var(--hud-border)', color: 'var(--hud-text)' }}
        />
        <input
          value={replayPath}
          onChange={event => setReplayPath(event.target.value)}
          placeholder="replay.redacted.json path"
          className="w-full px-2 py-1 text-[12px] outline-none"
          style={{ background: 'var(--hud-bg-deep)', border: '1px solid var(--hud-border)', color: 'var(--hud-text)' }}
        />
        <button
          onClick={verify}
          disabled={busy || !receiptPath.trim() || !replayPath.trim()}
          className="px-2 py-1 text-[12px] cursor-pointer disabled:opacity-40"
          style={{ background: 'var(--hud-bg-hover)', color: 'var(--hud-text)', border: '1px solid var(--hud-border)' }}
        >
          {busy ? 'Verifying...' : 'Verify receipt'}
        </button>
      </div>
      {result && (
        <div className="mt-3 text-[12px]" style={{ color: result.ok ? 'var(--hud-success)' : 'var(--hud-error)' }}>
          {result.ok ? (result.signature_valid ? 'Signature and local hashes match.' : 'Local hashes match.') : (result.errors || []).join(' ')}
          {result.warnings?.length > 0 && (
            <div className="mt-1" style={{ color: 'var(--hud-warning)' }}>{result.warnings.join(' ')}</div>
          )}
          {result.receipt_hash && (
            <div className="mt-2 truncate" style={{ color: 'var(--hud-text-dim)' }}>Receipt: {result.receipt_hash}</div>
          )}
        </div>
      )}
    </>
  )

  if (embedded) {
    return <div className={className}>{content}</div>
  }

  return (
    <Panel title="Verify" className={className}>
      {content}
    </Panel>
  )
}
