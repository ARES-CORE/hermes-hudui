import { Fragment, useMemo, useState } from 'react'
import { useApi } from '../hooks/useApi'
import Panel from './Panel'
import { formatDur, formatTokens, timeAgo } from '../lib/utils'
import { useTranslation } from '../i18n'

interface ModelInfo {
  model: string
  provider: string
  family: string
  supports_tools: boolean
  supports_vision: boolean
  supports_reasoning: boolean
  supports_structured_output: boolean
  max_output_tokens: number
  auto_context_length: number
  config_context_length: number
  effective_context_length: number
  cost_input_per_m: number | null
  cost_output_per_m: number | null
  cost_cache_read_per_m: number | null
  release_date: string
  knowledge_cutoff: string
  found: boolean
}

interface ModelUsage {
  model: string
  provider: string
  sessions: number
  messages: number
  api_calls: number
  tool_calls: number
  input_tokens: number
  output_tokens: number
  cache_read_tokens: number
  cache_write_tokens: number
  reasoning_tokens: number
  estimated_cost_usd: number
  actual_cost_usd: number
  last_used_at: string | null
  supports_tools: boolean
  supports_vision: boolean
  supports_reasoning: boolean
  supports_structured_output: boolean
  context_window: number
  max_output_tokens: number
  total_tokens: number
  avg_tokens_per_session: number
  session_details: ModelSessionUsage[]
}

interface ModelSessionUsage {
  id: string
  title: string
  source: string
  started_at: string | null
  ended_at: string | null
  messages: number
  api_calls: number
  tool_calls: number
  input_tokens: number
  output_tokens: number
  cache_read_tokens: number
  cache_write_tokens: number
  reasoning_tokens: number
  estimated_cost_usd: number
  actual_cost_usd: number
  total_tokens: number
  duration_seconds: number
}

interface ModelAnalytics {
  models: ModelUsage[]
  period_days: number | null
  total_models: number
  total_sessions: number
  total_tokens: number
  total_estimated_cost_usd: number
  total_actual_cost_usd: number
}

function CapBadge({ active, label }: { active: boolean; label: string }) {
  return (
    <span
      className="px-2 py-1 text-[11px] rounded"
      style={{
        background: active ? 'var(--hud-primary)' : 'var(--hud-panel-alt, transparent)',
        color: active ? 'var(--hud-bg)' : 'var(--hud-text-dim)',
        border: active ? 'none' : '1px solid var(--hud-border)',
        opacity: active ? 1 : 0.6,
      }}
    >
      {active ? '✓ ' : '○ '}
      {label}
    </span>
  )
}

function Money({ value }: { value: number }) {
  return <span>${value.toFixed(value >= 1 ? 2 : 4)}</span>
}

type PeriodDays = 7 | 30 | null
type SortKey =
  | 'model'
  | 'provider'
  | 'sessions'
  | 'tokens'
  | 'avg'
  | 'apiCalls'
  | 'toolCalls'
  | 'lastUsed'
  | 'cost'
  | 'capabilities'

interface SortState {
  key: SortKey
  dir: 'asc' | 'desc'
}

function capabilityCount(model: ModelUsage) {
  return [
    model.supports_tools,
    model.supports_vision,
    model.supports_reasoning,
    model.supports_structured_output,
  ].filter(Boolean).length
}

function sortValue(model: ModelUsage, key: SortKey): string | number {
  switch (key) {
    case 'model':
      return model.model.toLowerCase()
    case 'provider':
      return (model.provider || '').toLowerCase()
    case 'sessions':
      return model.sessions
    case 'tokens':
      return model.total_tokens
    case 'avg':
      return model.avg_tokens_per_session
    case 'apiCalls':
      return model.api_calls
    case 'toolCalls':
      return model.tool_calls
    case 'lastUsed':
      return model.last_used_at ? Date.parse(model.last_used_at) : 0
    case 'cost':
      return model.actual_cost_usd || model.estimated_cost_usd
    case 'capabilities':
      return capabilityCount(model)
  }
}

export default function ModelInfoPanel() {
  const { t } = useTranslation()
  const [periodDays, setPeriodDays] = useState<PeriodDays>(30)
  const [sort, setSort] = useState<SortState>({ key: 'tokens', dir: 'desc' })
  const [expandedModel, setExpandedModel] = useState<string | null>(null)
  const { data, isLoading } = useApi<ModelInfo>('/model-info', 30000)
  const analyticsDays = periodDays === null ? 0 : periodDays
  const { data: analytics } = useApi<ModelAnalytics>(`/model-analytics?days=${analyticsDays}`, 30000)

  const sortedModels = useMemo(() => {
    const models = analytics?.models ?? []
    return [...models].sort((a, b) => {
      const aValue = sortValue(a, sort.key)
      const bValue = sortValue(b, sort.key)
      const direction = sort.dir === 'asc' ? 1 : -1
      if (typeof aValue === 'string' || typeof bValue === 'string') {
        return String(aValue).localeCompare(String(bValue)) * direction
      }
      return (aValue - bValue) * direction
    })
  }, [analytics?.models, sort])

  const setSortKey = (key: SortKey) => {
    setSort((current) => ({
      key,
      dir: current.key === key && current.dir === 'desc' ? 'asc' : 'desc',
    }))
  }

  const sortMark = (key: SortKey) => (sort.key === key ? (sort.dir === 'asc' ? ' asc' : ' desc') : '')

  const sortableHeader = (key: SortKey, label: string, align: 'left' | 'right' = 'right') => (
    <th className={`py-2 pr-3 ${align === 'right' ? 'text-right' : 'text-left'}`} aria-sort={sort.key === key ? (sort.dir === 'asc' ? 'ascending' : 'descending') : 'none'}>
      <button
        type="button"
        className={`w-full ${align === 'right' ? 'text-right' : 'text-left'} hover:glow`}
        onClick={() => setSortKey(key)}
      >
        {label}{sortMark(key)}
      </button>
    </th>
  )

  if (isLoading && !data) {
    return (
      <Panel title={t('modelInfo.title')} className="col-span-full">
        <div className="glow text-[13px] animate-pulse">{t('modelInfo.loading')}</div>
      </Panel>
    )
  }

  if (!data || !data.model) {
    return (
      <Panel title={t('modelInfo.title')} className="col-span-full">
        <div className="text-[13px]" style={{ color: 'var(--hud-text-dim)' }}>
          {t('modelInfo.none')}
        </div>
      </Panel>
    )
  }

  const costRow = (label: string, value: number | null) =>
    value !== null ? (
      <div className="flex justify-between py-0.5 text-[13px]">
        <span style={{ color: 'var(--hud-text-dim)' }}>{label}</span>
        <span>${value.toFixed(2)} / 1M</span>
      </div>
    ) : null

  return (
    <>
      <Panel title={t('modelInfo.identity')}>
        <div className="space-y-1 text-[13px]">
          <div className="flex justify-between">
            <span style={{ color: 'var(--hud-text-dim)' }}>{t('modelInfo.model')}</span>
            <span style={{ color: 'var(--hud-primary)' }} className="font-mono">{data.model}</span>
          </div>
          <div className="flex justify-between">
            <span style={{ color: 'var(--hud-text-dim)' }}>{t('modelInfo.provider')}</span>
            <span>{data.provider || '—'}</span>
          </div>
          {data.family && (
            <div className="flex justify-between">
              <span style={{ color: 'var(--hud-text-dim)' }}>{t('modelInfo.family')}</span>
              <span>{data.family}</span>
            </div>
          )}
          {data.release_date && (
            <div className="flex justify-between">
              <span style={{ color: 'var(--hud-text-dim)' }}>{t('modelInfo.release')}</span>
              <span>{data.release_date}</span>
            </div>
          )}
          {data.knowledge_cutoff && (
            <div className="flex justify-between">
              <span style={{ color: 'var(--hud-text-dim)' }}>{t('modelInfo.knowledge')}</span>
              <span>{data.knowledge_cutoff}</span>
            </div>
          )}
        </div>

        <div className="mt-4">
          <div className="text-[12px] mb-2" style={{ color: 'var(--hud-text-dim)' }}>
            {t('modelInfo.capabilities')}
          </div>
          <div className="flex flex-wrap gap-2">
            <CapBadge active={data.supports_tools} label={t('modelInfo.tools')} />
            <CapBadge active={data.supports_vision} label={t('modelInfo.vision')} />
            <CapBadge active={data.supports_reasoning} label={t('modelInfo.reasoning')} />
            <CapBadge active={data.supports_structured_output} label={t('modelInfo.structured')} />
          </div>
          {!data.found && (
            <div className="mt-3 text-[11px]" style={{ color: 'var(--hud-text-dim)' }}>
              {t('modelInfo.notFound')}
            </div>
          )}
        </div>
      </Panel>

      <Panel title={t('modelInfo.limits')}>
        <div className="text-[13px] space-y-1">
          <div className="flex justify-between">
            <span style={{ color: 'var(--hud-text-dim)' }}>{t('modelInfo.effectiveContext')}</span>
            <span style={{ color: 'var(--hud-primary)' }}>{formatTokens(data.effective_context_length)}</span>
          </div>
          <div className="flex justify-between">
            <span style={{ color: 'var(--hud-text-dim)' }}>{t('modelInfo.autoContext')}</span>
            <span>{formatTokens(data.auto_context_length)}</span>
          </div>
          <div className="flex justify-between">
            <span style={{ color: 'var(--hud-text-dim)' }}>{t('modelInfo.configContext')}</span>
            <span>{data.config_context_length > 0 ? formatTokens(data.config_context_length) : t('modelInfo.unset')}</span>
          </div>
          <div className="flex justify-between">
            <span style={{ color: 'var(--hud-text-dim)' }}>{t('modelInfo.maxOutput')}</span>
            <span>{formatTokens(data.max_output_tokens)}</span>
          </div>
        </div>

        {(data.cost_input_per_m !== null || data.cost_output_per_m !== null) && (
          <div className="mt-4 pt-3" style={{ borderTop: '1px solid var(--hud-border)' }}>
            <div className="text-[12px] mb-1" style={{ color: 'var(--hud-text-dim)' }}>
              {t('modelInfo.cost')}
            </div>
            {costRow(t('modelInfo.costInput'), data.cost_input_per_m)}
            {costRow(t('modelInfo.costOutput'), data.cost_output_per_m)}
            {costRow(t('modelInfo.costCacheRead'), data.cost_cache_read_per_m)}
          </div>
        )}
      </Panel>

      <Panel title={t('modelInfo.usage')} className="col-span-full">
        <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
          <div className="text-[12px]" style={{ color: 'var(--hud-text-dim)' }}>
            {periodDays === null ? t('modelInfo.periodAll') : t('modelInfo.periodDays').replace('{days}', String(periodDays))}
          </div>
          <div className="flex border" style={{ borderColor: 'var(--hud-border)' }}>
            {[
              [7, t('modelInfo.period7d')],
              [30, t('modelInfo.period30d')],
              [null, t('modelInfo.periodAll')],
            ].map(([value, label]) => {
              const active = periodDays === value
              return (
                <button
                  key={String(value)}
                  type="button"
                  className="px-3 py-1.5 text-[12px]"
                  style={{
                    background: active ? 'var(--hud-primary)' : 'transparent',
                    color: active ? 'var(--hud-bg)' : 'var(--hud-text)',
                    borderRight: value === null ? 'none' : '1px solid var(--hud-border)',
                  }}
                  onClick={() => {
                    setPeriodDays(value as PeriodDays)
                    setExpandedModel(null)
                  }}
                >
                  {label}
                </button>
              )
            })}
          </div>
        </div>

        {!analytics || analytics.models.length === 0 ? (
          <div className="text-[13px]" style={{ color: 'var(--hud-text-dim)' }}>
            {t('modelInfo.noUsage')}
          </div>
        ) : (
          <>
            <div className="grid grid-cols-2 md:grid-cols-5 gap-2 mb-3">
              {[
                [t('modelInfo.models'), analytics.total_models],
                [t('modelInfo.sessions'), analytics.total_sessions],
                [t('modelInfo.tokens'), formatTokens(analytics.total_tokens)],
                [t('modelInfo.estimated'), `$${analytics.total_estimated_cost_usd.toFixed(2)}`],
                [t('modelInfo.actual'), `$${analytics.total_actual_cost_usd.toFixed(2)}`],
              ].map(([label, value]) => (
                <div key={String(label)} className="p-2 border" style={{ borderColor: 'var(--hud-border)' }}>
                  <div className="text-[11px] uppercase tracking-widest" style={{ color: 'var(--hud-text-dim)' }}>{label}</div>
                  <div className="text-[15px] font-bold" style={{ color: 'var(--hud-primary)' }}>{value}</div>
                </div>
              ))}
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-[12px]">
                <thead>
                  <tr style={{ color: 'var(--hud-text-dim)', borderBottom: '1px solid var(--hud-border)' }}>
                    {sortableHeader('model', t('modelInfo.model'), 'left')}
                    {sortableHeader('provider', t('modelInfo.provider'), 'left')}
                    {sortableHeader('sessions', t('modelInfo.sessions'))}
                    {sortableHeader('tokens', t('modelInfo.tokens'))}
                    {sortableHeader('avg', t('modelInfo.avg'))}
                    {sortableHeader('apiCalls', t('modelInfo.apiCalls'))}
                    {sortableHeader('toolCalls', t('modelInfo.toolCalls'))}
                    {sortableHeader('lastUsed', t('modelInfo.lastUsed'))}
                    {sortableHeader('cost', t('modelInfo.cost'))}
                    {sortableHeader('capabilities', t('modelInfo.capabilities'), 'left')}
                  </tr>
                </thead>
                <tbody>
                  {sortedModels.map((model) => {
                    const modelKey = `${model.provider}:${model.model}`
                    const expanded = expandedModel === modelKey
                    return (
                      <Fragment key={modelKey}>
                        <tr style={{ borderBottom: '1px solid var(--hud-border)' }}>
                          <td className="py-2 pr-3 font-mono" style={{ color: 'var(--hud-text)' }}>
                            <button
                              type="button"
                              className="text-left hover:glow"
                              onClick={() => setExpandedModel(expanded ? null : modelKey)}
                              title={expanded ? t('modelInfo.hideSessions') : t('modelInfo.showSessions')}
                            >
                              {expanded ? '[-]' : '[+]'} {model.model}
                            </button>
                          </td>
                          <td className="py-2 pr-3" style={{ color: 'var(--hud-text-dim)' }}>{model.provider || '—'}</td>
                          <td className="py-2 pr-3 text-right">{model.sessions}</td>
                          <td className="py-2 pr-3 text-right">
                            <div>{formatTokens(model.total_tokens)}</div>
                            <div className="text-[10px]" style={{ color: 'var(--hud-text-dim)' }}>
                              I {formatTokens(model.input_tokens)} / O {formatTokens(model.output_tokens)}
                              {(model.cache_read_tokens || model.cache_write_tokens || model.reasoning_tokens) ? (
                                <>
                                  {' '} / C {formatTokens(model.cache_read_tokens + model.cache_write_tokens)}
                                  {' '} / R {formatTokens(model.reasoning_tokens)}
                                </>
                              ) : null}
                            </div>
                          </td>
                          <td className="py-2 pr-3 text-right">{formatTokens(model.avg_tokens_per_session)}</td>
                          <td className="py-2 pr-3 text-right">{model.api_calls}</td>
                          <td className="py-2 pr-3 text-right">{model.tool_calls}</td>
                          <td className="py-2 pr-3 text-right whitespace-nowrap">
                            {model.last_used_at ? timeAgo(model.last_used_at) : '-'}
                          </td>
                          <td className="py-2 pr-3 text-right">
                            <div>A <Money value={model.actual_cost_usd} /></div>
                            <div className="text-[10px]" style={{ color: 'var(--hud-text-dim)' }}>
                              E <Money value={model.estimated_cost_usd} />
                            </div>
                          </td>
                          <td className="py-2">
                            <div className="flex flex-wrap gap-1">
                              <CapBadge active={model.supports_tools} label={t('modelInfo.tools')} />
                              <CapBadge active={model.supports_vision} label={t('modelInfo.vision')} />
                              <CapBadge active={model.supports_reasoning} label={t('modelInfo.reasoning')} />
                            </div>
                          </td>
                        </tr>
                        {expanded && (
                          <tr style={{ borderBottom: '1px solid var(--hud-border)', background: 'var(--hud-panel-alt, transparent)' }}>
                            <td colSpan={10} className="p-3">
                              <div className="text-[11px] uppercase tracking-widest mb-2" style={{ color: 'var(--hud-text-dim)' }}>
                                {t('modelInfo.sessionDrilldown')}
                              </div>
                              <div className="overflow-x-auto">
                                <table className="w-full text-[11px]">
                                  <thead>
                                    <tr style={{ color: 'var(--hud-text-dim)', borderBottom: '1px solid var(--hud-border)' }}>
                                      <th className="text-left py-1 pr-3">{t('modelInfo.session')}</th>
                                      <th className="text-left py-1 pr-3">{t('modelInfo.source')}</th>
                                      <th className="text-right py-1 pr-3">{t('modelInfo.messages')}</th>
                                      <th className="text-right py-1 pr-3">{t('modelInfo.tokens')}</th>
                                      <th className="text-right py-1 pr-3">{t('modelInfo.duration')}</th>
                                      <th className="text-right py-1 pr-3">{t('modelInfo.lastUsed')}</th>
                                      <th className="text-right py-1">{t('modelInfo.cost')}</th>
                                    </tr>
                                  </thead>
                                  <tbody>
                                    {model.session_details.map((session) => (
                                      <tr key={session.id} style={{ borderBottom: '1px solid var(--hud-border)' }}>
                                        <td className="py-1.5 pr-3">
                                          <div style={{ color: 'var(--hud-text)' }}>{session.title || session.id}</div>
                                          {session.title && (
                                            <div className="font-mono text-[10px]" style={{ color: 'var(--hud-text-dim)' }}>{session.id}</div>
                                          )}
                                        </td>
                                        <td className="py-1.5 pr-3" style={{ color: 'var(--hud-text-dim)' }}>{session.source || '—'}</td>
                                        <td className="py-1.5 pr-3 text-right">{session.messages}</td>
                                        <td className="py-1.5 pr-3 text-right">{formatTokens(session.total_tokens)}</td>
                                        <td className="py-1.5 pr-3 text-right">{session.duration_seconds ? formatDur(session.duration_seconds) : '-'}</td>
                                        <td className="py-1.5 pr-3 text-right whitespace-nowrap">{session.started_at ? timeAgo(session.started_at) : '-'}</td>
                                        <td className="py-1.5 text-right"><Money value={session.actual_cost_usd || session.estimated_cost_usd} /></td>
                                      </tr>
                                    ))}
                                  </tbody>
                                </table>
                              </div>
                            </td>
                          </tr>
                        )}
                      </Fragment>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </>
        )}
      </Panel>
    </>
  )
}
