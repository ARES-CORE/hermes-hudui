import { useApi } from '../hooks/useApi'
import Panel, { Sparkline } from './Panel'
import { useTranslation } from '../i18n'

const OUTCOME: Record<string, { color: string; icon: string }> = {
  success: { color: 'var(--hud-success)', icon: '✓' },
  failed:  { color: 'var(--hud-error)',   icon: '✗' },
  blocked: { color: 'var(--hud-warning)', icon: '⊘' },
  unknown: { color: 'var(--hud-text-dim)', icon: '?' },
}

function timeLabel(ts: string | null) {
  if (!ts) return ''
  const d = new Date(ts)
  return d.toLocaleDateString() + ' ' + d.toLocaleTimeString()
}

export default function SudoPanel() {
  const { t } = useTranslation()
  const { data, isLoading } = useApi('/sudo', 60000)

  if (isLoading && !data) {
    return (
      <Panel title={t('sudo.title')} className="col-span-full">
        <div className="glow text-[13px] animate-pulse">{t('sudo.loading')}</div>
      </Panel>
    )
  }

  const config = data?.config || {}
  const stats = data?.stats || {}
  const commands: any[] = data?.commands || []

  const allowlist: string[] = config.command_allowlist || []
  const byType: Record<string, number> = stats.commands_by_type || {}
  const dailyCounts: { date: string; count: number }[] = stats.daily_counts || []
  const sparkValues = dailyCounts.map((d: any) => d.count)

  return (
    <>
      {/* Panel 1 — Configuration */}
      <Panel title={t('sudo.config')} className="col-span-1">
        <div className="space-y-2 text-[13px]">
          <div className="flex justify-between py-0.5">
            <span style={{ color: 'var(--hud-text-dim)' }}>{t('sudo.approvalMode')}</span>
            <span style={{ color: config.approval_mode === 'manual' ? 'var(--hud-success)' : 'var(--hud-warning)' }}>
              {config.approval_mode || 'manual'}
            </span>
          </div>
          <div className="flex justify-between py-0.5">
            <span style={{ color: 'var(--hud-text-dim)' }}>{t('sudo.approvalTimeout')}</span>
            <span>{config.approval_timeout ?? 60}s</span>
          </div>
          <div className="pt-1" style={{ borderTop: '1px solid var(--hud-border)' }}>
            <div className="mb-1" style={{ color: 'var(--hud-text-dim)' }}>{t('sudo.allowlist')}</div>
            {allowlist.length === 0 ? (
              <span style={{ color: 'var(--hud-text-dim)' }}>{t('sudo.noneConfigured')}</span>
            ) : (
              <div className="space-y-0.5">
                {allowlist.map((cmd: string, i: number) => (
                  <div key={i} className="font-mono text-[12px] px-1.5 py-0.5"
                       style={{ background: 'var(--hud-bg-panel)', color: 'var(--hud-warning)' }}>
                    {cmd}
                  </div>
                ))}
              </div>
            )}
          </div>
          <div className="pt-1" style={{ borderTop: '1px solid var(--hud-border)' }}>
            <div className="mb-1" style={{ color: 'var(--hud-text-dim)' }}>{t('sudo.security')}</div>
            <div className="flex justify-between py-0.5">
              <span style={{ color: 'var(--hud-text-dim)' }}>{t('sudo.redactSecrets')}</span>
              <span style={{ color: config.redact_secrets ? 'var(--hud-success)' : 'var(--hud-error)' }}>
                {config.redact_secrets ? t('sudo.enabled') : t('sudo.disabled')}
              </span>
            </div>
            <div className="flex justify-between py-0.5">
              <span style={{ color: 'var(--hud-text-dim)' }}>{t('sudo.tirith')}</span>
              <span style={{ color: config.tirith_enabled ? 'var(--hud-success)' : 'var(--hud-error)' }}>
                {config.tirith_enabled ? t('sudo.enabled') : t('sudo.disabled')}
              </span>
            </div>
          </div>
        </div>
      </Panel>

      {/* Panel 2 — Statistics */}
      <Panel title={t('sudo.stats')} className="col-span-1">
        <div className="space-y-2 text-[13px]">
          <div className="flex justify-between">
            <span style={{ color: 'var(--hud-text-dim)' }}>{t('sudo.totalCommands')}</span>
            <span className="glow font-bold">{stats.total_commands ?? 0}</span>
          </div>
          <div className="flex gap-4">
            <span style={{ color: 'var(--hud-success)' }}>✓ {stats.approved_count ?? 0} {t('sudo.approved')}</span>
            <span style={{ color: 'var(--hud-error)' }}>✗ {stats.failed_count ?? 0} {t('sudo.failed')}</span>
            <span style={{ color: 'var(--hud-warning)' }}>⊘ {stats.blocked_count ?? 0} {t('sudo.blocked')}</span>
          </div>

          {sparkValues.length > 0 && (
            <div className="pt-1" style={{ borderTop: '1px solid var(--hud-border)' }}>
              <Sparkline values={sparkValues} width={220} height={32} />
            </div>
          )}

          {Object.keys(byType).length > 0 && (
            <div className="pt-1" style={{ borderTop: '1px solid var(--hud-border)' }}>
              <div className="mb-1" style={{ color: 'var(--hud-text-dim)' }}>{t('sudo.byType')}</div>
              <div className="space-y-0.5">
                {Object.entries(byType).map(([type, count]) => (
                  <div key={type} className="flex justify-between">
                    <span className="font-mono">{type}</span>
                    <span style={{ color: 'var(--hud-text-dim)' }}>{count}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </Panel>

      {/* Panel 3 — Command History */}
      <Panel title={t('sudo.history')} className="col-span-full">
        {commands.length === 0 ? (
          <div className="text-[13px]" style={{ color: 'var(--hud-text-dim)' }}>
            {t('sudo.noCommands')}
          </div>
        ) : (
          <div className="space-y-1.5 overflow-y-auto" style={{ maxHeight: '400px' }}>
            {commands.map((cmd: any, i: number) => {
              const o = OUTCOME[cmd.outcome] || OUTCOME.unknown
              return (
                <div key={i} className="p-2 text-[13px]"
                     style={{ background: 'var(--hud-bg-panel)', borderLeft: `2px solid ${o.color}` }}>
                  <div className="flex items-center gap-2 flex-wrap">
                    <span style={{ color: o.color }}>{o.icon}</span>
                    {cmd.timestamp && (
                      <span style={{ color: 'var(--hud-text-dim)' }}>{timeLabel(cmd.timestamp)}</span>
                    )}
                    <span className="font-mono break-all" style={{ color: 'var(--hud-primary)' }}>
                      {cmd.command}
                    </span>
                  </div>
                  {cmd.session_title && (
                    <div className="mt-0.5" style={{ color: 'var(--hud-text-dim)' }}>
                      ↳ {t('sudo.session')}: {cmd.session_title}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </Panel>
    </>
  )
}
