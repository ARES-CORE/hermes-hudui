interface ChatDiagnosticsProps {
  model: string
  status: string
  processStartMs: number | null
  firstTokenMs: number | null
  totalMs: number | null
  resumed: boolean
  recentFirstTokenAvgMs: number | null
  recentTotalAvgMs: number | null
  recentRuns: number
}

function formatMs(value: number | null) {
  if (value === null || value < 0) return '-'
  if (value < 1000) return `${value}ms`
  return `${(value / 1000).toFixed(value < 10_000 ? 1 : 0)}s`
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0">
      <div className="text-[10px] uppercase tracking-widest" style={{ color: 'var(--hud-text-dim)' }}>
        {label}
      </div>
      <div className="text-[12px] truncate" style={{ color: 'var(--hud-text)' }}>
        {value}
      </div>
    </div>
  )
}

export default function ChatDiagnostics({
  model,
  status,
  processStartMs,
  firstTokenMs,
  totalMs,
  resumed,
  recentFirstTokenAvgMs,
  recentTotalAvgMs,
  recentRuns,
}: ChatDiagnosticsProps) {
  if (status === 'idle' && recentRuns === 0) return null

  return (
    <div
      className="border-t px-2 py-1.5 grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-2"
      style={{
        borderColor: 'var(--hud-border)',
        background: 'var(--hud-bg-panel)',
      }}
    >
      <Metric label="Model" value={model !== 'unknown' ? model : '-'} />
      <Metric label="Status" value={status.replaceAll('_', ' ')} />
      <Metric label="Spawn" value={formatMs(processStartMs)} />
      <Metric label="First Token" value={formatMs(firstTokenMs)} />
      <Metric label="Total" value={formatMs(totalMs)} />
      <Metric label="Resume" value={resumed ? 'yes' : 'new'} />
      <Metric
        label={`Avg ${recentRuns ? `(${recentRuns})` : ''}`}
        value={
          recentRuns
            ? `${formatMs(recentFirstTokenAvgMs)} first / ${formatMs(recentTotalAvgMs)} total`
            : '-'
        }
      />
    </div>
  )
}
