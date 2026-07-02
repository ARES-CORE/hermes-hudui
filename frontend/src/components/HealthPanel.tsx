import { useState } from 'react'
import { useApi } from '../hooks/useApi'
import Panel from './Panel'
import { useTranslation } from '../i18n'
import { formatSize, timeAgo } from '../lib/utils'

type HealthAction = {
  name: string
  kind: 'refresh' | 'post' | 'tab'
  endpoint?: string
  target?: string
  destructive?: boolean
}

type DiagnosticStatus = {
  name: string
  status: 'ok' | 'warning' | 'broken'
  detail: string
  updated_at?: string | null
  age_seconds?: number | null
  depends_on?: string[]
  suggested_fix?: string
  actions?: HealthAction[]
}

type SeverityFilter = 'all' | 'broken' | 'warning'

const STATUS_COLOR = {
  ok: 'var(--hud-success)',
  warning: 'var(--hud-warning)',
  broken: 'var(--hud-error)',
}

function statusLabel(status: string) {
  if (status === 'ok') return 'OK'
  if (status === 'warning') return 'WARN'
  if (status === 'broken') return 'BROKEN'
  return status.toUpperCase()
}

function DiagnosticList({
  items,
  onAction,
  actionStatus,
  filter,
}: {
  items: DiagnosticStatus[]
  onAction: (action: HealthAction) => void
  actionStatus: string | null
  filter: SeverityFilter
}) {
  const [expanded, setExpanded] = useState<string | null>(null)
  const visibleItems = items.filter((item) => filter === 'all' || item.status === filter)
  if (!visibleItems.length) {
    return <div className="text-[13px]" style={{ color: 'var(--hud-text-dim)' }}>-</div>
  }
  return (
    <div className="space-y-2">
      {visibleItems.map((item) => (
        <div key={item.name} className="py-1.5" style={{ borderBottom: '1px solid var(--hud-border)' }}>
          <button
            type="button"
            className="w-full flex items-start justify-between gap-3 text-[13px] text-left"
            onClick={() => setExpanded(expanded === item.name ? null : item.name)}
          >
            <div className="min-w-0">
              <div className="truncate">{expanded === item.name ? '▾' : '▸'} {item.name}</div>
              <div className="text-[11px]" style={{ color: 'var(--hud-text-dim)' }}>
                {item.updated_at ? timeAgo(item.updated_at) : item.detail}
              </div>
            </div>
            <div className="text-[11px] font-bold shrink-0" style={{ color: STATUS_COLOR[item.status] || 'var(--hud-text-dim)' }}>
              {statusLabel(item.status)}
            </div>
          </button>
          {expanded === item.name && (
            <div className="mt-2 ml-4 space-y-2 text-[11px]" style={{ color: 'var(--hud-text-dim)' }}>
              <div>{item.detail}</div>
              {item.depends_on && item.depends_on.length > 0 && (
                <div>
                  <span style={{ color: 'var(--hud-text)' }}>Depends:</span> {item.depends_on.join(', ')}
                </div>
              )}
              {item.suggested_fix && (
                <div>
                  <span style={{ color: 'var(--hud-text)' }}>Fix:</span> {item.suggested_fix}
                </div>
              )}
              {item.actions && item.actions.length > 0 && (
                <div className="flex flex-wrap gap-1">
                  {item.actions.map((action) => (
                    <button
                      key={`${item.name}:${action.name}`}
                      type="button"
                      className="px-2 py-1 border text-[11px]"
                      style={{ borderColor: 'var(--hud-border)', color: 'var(--hud-primary)' }}
                      onClick={(event) => {
                        event.stopPropagation()
                        onAction(action)
                      }}
                    >
                      {action.name}
                    </button>
                  ))}
                </div>
              )}
              {actionStatus && (
                <div style={{ color: actionStatus.startsWith('Error') ? 'var(--hud-error)' : 'var(--hud-success)' }}>
                  {actionStatus}
                </div>
              )}
            </div>
          )}
        </div>
      ))}
    </div>
  )
}

export default function HealthPanel() {
  const { t } = useTranslation()
  const { data, isLoading, mutate } = useApi('/health', 30000)
  const [actionStatus, setActionStatus] = useState<string | null>(null)
  const [severityFilter, setSeverityFilter] = useState<SeverityFilter>('all')

  // Only show loading on initial load
  if (isLoading && !data) {
    return <Panel title={t('health.title')} className="col-span-full"><div className="glow text-[13px] animate-pulse">{t('health.loading')}</div></Panel>
  }

  const keys = data.keys || []
  const services = data.services || []
  const readiness = data.readiness || []
  const freshness = data.freshness || []
  const database = data.database || []
  const features = data.features || []

  async function runAction(action: HealthAction) {
    setActionStatus(null)
    if (action.kind === 'refresh') {
      await mutate()
      setActionStatus(t('health.actionDone'))
      return
    }
    if (action.kind === 'tab' && action.target) {
      window.dispatchEvent(new CustomEvent('hud:navigate', { detail: { tab: action.target } }))
      return
    }
    if (action.kind === 'post' && action.endpoint) {
      try {
        const res = await fetch(action.endpoint, { method: 'POST' })
        if (!res.ok) throw new Error(await res.text())
        await mutate()
        setActionStatus(t('health.actionDone'))
      } catch (err) {
        setActionStatus(`Error: ${err instanceof Error ? err.message : String(err)}`)
      }
    }
  }

  return (
    <>
      <Panel title={t('health.diagnostics')} className="col-span-full">
        <div className="grid grid-cols-2 md:grid-cols-5 gap-2 text-[13px]">
          {[
            [t('health.ok'), data.diagnostics_ok || 0, 'var(--hud-success)'],
            [t('health.warnings'), data.diagnostics_warnings || 0, 'var(--hud-warning)'],
            [t('health.broken'), data.diagnostics_broken || 0, 'var(--hud-error)'],
            [t('health.sessions'), data.session_count || 0, 'var(--hud-primary)'],
            [t('health.db'), data.state_db_exists ? formatSize(data.state_db_size || 0) : t('health.missing'), 'var(--hud-text)'],
          ].map(([label, value, color]) => (
            <div key={String(label)} className="py-2 px-2 border" style={{ borderColor: 'var(--hud-border)' }}>
              <div className="text-[11px] uppercase tracking-widest" style={{ color: 'var(--hud-text-dim)' }}>{label}</div>
              <div className="font-bold" style={{ color: String(color) }}>{value}</div>
            </div>
          ))}
        </div>
        <div className="mt-3 grid grid-cols-1 md:grid-cols-3 gap-2 text-[12px]">
          <div><span style={{ color: 'var(--hud-text-dim)' }}>{t('health.cli')}:</span> {data.hermes_cli_status || '-'}</div>
          <div><span style={{ color: 'var(--hud-text-dim)' }}>{t('health.path')}:</span> {data.hermes_cli_path || '-'}</div>
          <div><span style={{ color: 'var(--hud-text-dim)' }}>{t('health.lastSession')}:</span> {data.last_session_at ? timeAgo(data.last_session_at) : '-'}</div>
        </div>
        <div className="mt-3 flex flex-wrap gap-1">
          {[
            ['all', t('health.filterAll')],
            ['broken', t('health.filterBroken')],
            ['warning', t('health.filterWarnings')],
          ].map(([value, label]) => (
            <button
              key={value}
              type="button"
              className="px-2 py-1 text-[11px] border"
              style={{
                borderColor: severityFilter === value ? 'var(--hud-primary)' : 'var(--hud-border)',
                color: severityFilter === value ? 'var(--hud-primary)' : 'var(--hud-text-dim)',
                background: severityFilter === value ? 'var(--hud-panel-alt, transparent)' : 'transparent',
              }}
              onClick={() => setSeverityFilter(value as SeverityFilter)}
            >
              {label}
            </button>
          ))}
        </div>
      </Panel>

      <Panel title={t('health.features')} className="col-span-full">
        <DiagnosticList items={features} onAction={runAction} actionStatus={actionStatus} filter={severityFilter} />
      </Panel>

      <Panel title={t('health.readiness')} className="col-span-1">
        <DiagnosticList items={readiness} onAction={runAction} actionStatus={actionStatus} filter={severityFilter} />
      </Panel>

      <Panel title={t('health.freshness')} className="col-span-1">
        <DiagnosticList items={freshness} onAction={runAction} actionStatus={actionStatus} filter={severityFilter} />
      </Panel>

      <Panel title={t('health.database')} className="col-span-full">
        <DiagnosticList items={database} onAction={runAction} actionStatus={actionStatus} filter={severityFilter} />
      </Panel>

      <Panel title={t('health.apiKeys')} className="col-span-1">
        <div className="space-y-1 text-[13px]">
          {keys.map((k: any, i: number) => (
            <div key={i} className="flex justify-between py-0.5">
              <span className="truncate mr-2">{k.name}</span>
              <span style={{ color: k.present ? 'var(--hud-success)' : 'var(--hud-error)' }}>
                {k.present ? '●' : '○'}
              </span>
            </div>
          ))}
        </div>
        <div className="mt-2 pt-2 text-[13px]" style={{ borderTop: '1px solid var(--hud-border)' }}>
          <span style={{ color: 'var(--hud-success)' }}>{data.keys_ok || 0}</span>
          <span style={{ color: 'var(--hud-text-dim)' }}> {t('health.configured')} · </span>
          <span style={{ color: data.keys_missing > 0 ? 'var(--hud-error)' : 'var(--hud-text-dim)' }}>{data.keys_missing || 0}</span>
          <span style={{ color: 'var(--hud-text-dim)' }}> {t('health.missing')}</span>
        </div>
      </Panel>

      <Panel title={t('health.services')} className="col-span-1">
        <div className="space-y-2 text-[13px]">
          {services.map((s: any, i: number) => (
            <div key={i} className="py-1 px-2" style={{ borderLeft: `2px solid ${s.running ? 'var(--hud-success)' : 'var(--hud-error)'}` }}>
              <div className="flex justify-between">
                <span>{s.name}</span>
                <span style={{ color: s.running ? 'var(--hud-success)' : 'var(--hud-error)' }}>
                  {s.running ? t('health.running') : t('health.stopped')}
                </span>
              </div>
              {s.pid && <div style={{ color: 'var(--hud-text-dim)' }}>{t('health.pid')} {s.pid}</div>}
              {s.note && <div style={{ color: 'var(--hud-text-dim)' }}>{s.note}</div>}
            </div>
          ))}
        </div>
        <div className="mt-3 text-[13px]" style={{ color: 'var(--hud-text-dim)' }}>
          <div>{t('health.provider')}: {data.config_provider || '-'}</div>
          <div>{t('health.model')}: {data.config_model || '-'}</div>
          <div>{t('health.db')}: {data.state_db_exists ? `${(data.state_db_size / 1048576).toFixed(1)}MB` : t('health.missing')}</div>
        </div>
      </Panel>
    </>
  )
}
