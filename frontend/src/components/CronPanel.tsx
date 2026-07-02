import { useState } from 'react'
import { useApi } from '../hooks/useApi'
import Panel from './Panel'
import { timeAgo, truncate } from '../lib/utils'
import { useTranslation } from '../i18n'

type ScheduleMode = 'interval' | 'cron'

interface CreateCronForm {
  name: string
  prompt: string
  deliver: string
  customDeliver: string
  repeat: string
  scheduleMode: ScheduleMode
  intervalPreset: string
  intervalValue: string
  intervalUnit: string
  cronExpr: string
  skills: string
  script: string
  workdir: string
}

interface CronJob {
  id: string
  name?: string
  prompt?: string
  schedule?: string
  schedule_display?: string
  enabled?: boolean
  state?: string
  next_run_at?: string | null
  last_run_at?: string | null
  last_status?: string | null
  deliver?: string
  repeat_total?: number | null
  repeat_completed?: number | null
  skills?: string[]
  paused_reason?: string | null
}

type CronResponse = { jobs?: CronJob[] } | CronJob[]

const defaultForm: CreateCronForm = {
  name: '',
  prompt: '',
  deliver: 'local',
  customDeliver: '',
  repeat: '',
  scheduleMode: 'interval',
  intervalPreset: '30m',
  intervalValue: '30',
  intervalUnit: 'm',
  cronExpr: '0 9 * * *',
  skills: '',
  script: '',
  workdir: '',
}

const intervalPresets = ['30m', '1h', '2h', '24h']
const deliveryOptions = ['local', 'origin', 'telegram', 'discord', 'signal', 'custom']

async function cronAction(jobId: string, action: string | null, method = 'POST') {
  const url = action ? `/api/cron/${jobId}/${action}` : `/api/cron/${jobId}`
  const res = await fetch(url, { method })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `${action ?? 'delete'} failed`)
  }
}

async function createCronJob(form: CreateCronForm) {
  const schedule = getSchedule(form)
  const deliver = form.deliver === 'custom' ? form.customDeliver.trim() : form.deliver
  const skills = form.skills
    .split(/[\n,]/)
    .map(skill => skill.trim())
    .filter(Boolean)

  const payload = {
    schedule,
    prompt: form.prompt.trim() || undefined,
    name: form.name.trim() || undefined,
    deliver: deliver || undefined,
    repeat: form.repeat.trim() ? Number(form.repeat) : undefined,
    skills,
    script: form.script.trim() || undefined,
    workdir: form.workdir.trim() || undefined,
  }

  const res = await fetch('/api/cron', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || 'Create failed')
  }
}

function getSchedule(form: CreateCronForm) {
  if (form.scheduleMode === 'cron') return form.cronExpr.trim()
  if (form.intervalPreset !== 'custom') return form.intervalPreset
  return `${form.intervalValue.trim()}${form.intervalUnit}`
}

function isValidCronExpr(value: string) {
  return value.trim().split(/\s+/).length === 5
}

function FieldLabel({ children }: { children: string }) {
  return (
    <label className="block uppercase tracking-wider text-[10px] mb-1" style={{ color: 'var(--hud-text-dim)' }}>
      {children}
    </label>
  )
}

function CronCreateDrawer({
  onCreate,
  onCancel,
}: {
  onCreate: () => void | Promise<void>
  onCancel: () => void
}) {
  const { t } = useTranslation()
  const [form, setForm] = useState<CreateCronForm>(defaultForm)
  const [advancedOpen, setAdvancedOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const update = (patch: Partial<CreateCronForm>) => setForm(current => ({ ...current, ...patch }))
  const inputClass = 'w-full text-[13px] px-2 py-1.5 outline-none'
  const inputStyle = {
    background: 'var(--hud-bg-deep)',
    border: '1px solid var(--hud-border)',
    color: 'var(--hud-text)',
  }
  const schedule = getSchedule(form)

  const validate = () => {
    if (!schedule) return t('cron.createScheduleRequired')
    if (form.scheduleMode === 'interval' && form.intervalPreset === 'custom' && !form.intervalValue.trim()) {
      return t('cron.createIntervalInvalid')
    }
    if (form.scheduleMode === 'cron' && !isValidCronExpr(form.cronExpr)) {
      return t('cron.createCronInvalid')
    }
    if (form.repeat.trim() && (!Number.isInteger(Number(form.repeat)) || Number(form.repeat) < 1)) {
      return t('cron.createRepeatInvalid')
    }
    if (form.workdir.trim() && !form.workdir.trim().startsWith('/')) {
      return t('cron.createWorkdirInvalid')
    }
    return ''
  }

  const submit = async () => {
    const validationError = validate()
    if (validationError) {
      setError(validationError)
      return
    }

    setBusy(true)
    setError('')
    try {
      await createCronJob(form)
      setForm(defaultForm)
      await onCreate()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unknown error')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="mb-4 p-3" style={{ background: 'var(--hud-bg-panel)', border: '1px solid var(--hud-border)' }}>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        <div>
          <FieldLabel>{t('cron.createName')}</FieldLabel>
          <input
            value={form.name}
            onChange={e => update({ name: e.target.value })}
            placeholder={t('cron.createNamePlaceholder')}
            className={inputClass}
            style={inputStyle}
          />
        </div>
        <div>
          <FieldLabel>{t('cron.createDeliver')}</FieldLabel>
          <select
            value={form.deliver}
            onChange={e => update({ deliver: e.target.value })}
            className={inputClass}
            style={inputStyle}
          >
            {deliveryOptions.map(option => (
              <option key={option} value={option}>{option === 'custom' ? t('cron.createDeliverCustom') : option}</option>
            ))}
          </select>
        </div>
        <div>
          <FieldLabel>{t('cron.createRepeat')}</FieldLabel>
          <input
            value={form.repeat}
            onChange={e => update({ repeat: e.target.value.replace(/[^\d]/g, '') })}
            placeholder={t('cron.createRepeatPlaceholder')}
            inputMode="numeric"
            className={inputClass}
            style={inputStyle}
          />
        </div>
      </div>

      {form.deliver === 'custom' && (
        <div className="mt-3">
          <FieldLabel>{t('cron.createDeliverTarget')}</FieldLabel>
          <input
            value={form.customDeliver}
            onChange={e => update({ customDeliver: e.target.value })}
            placeholder="platform:chat_id"
            className={inputClass}
            style={inputStyle}
          />
        </div>
      )}

      <div className="mt-3">
        <FieldLabel>{t('cron.createSchedule')}</FieldLabel>
        <div className="flex flex-wrap gap-1.5 mb-2">
          {(['interval', 'cron'] as ScheduleMode[]).map(mode => (
            <button
              key={mode}
              onClick={() => update({ scheduleMode: mode })}
              className="px-2 py-1 text-[11px] cursor-pointer"
              style={{
                background: form.scheduleMode === mode ? 'var(--hud-primary)' : 'var(--hud-bg-hover)',
                color: form.scheduleMode === mode ? 'var(--hud-bg-deep)' : 'var(--hud-text-dim)',
                border: '1px solid var(--hud-border)',
              }}
              type="button"
            >
              {mode === 'interval' ? t('cron.createInterval') : t('cron.createCronExpr')}
            </button>
          ))}
          <span className="text-[12px] self-center ml-auto" style={{ color: 'var(--hud-text-dim)' }}>
            {t('cron.createPreview')}: <span style={{ color: 'var(--hud-primary)' }}>{schedule || '-'}</span>
          </span>
        </div>

        {form.scheduleMode === 'interval' ? (
          <div className="flex flex-wrap gap-2">
            {intervalPresets.map(preset => (
              <button
                key={preset}
                onClick={() => update({ intervalPreset: preset })}
                className="px-2 py-1 text-[12px] cursor-pointer"
                style={{
                  background: form.intervalPreset === preset ? 'var(--hud-primary)' : 'transparent',
                  color: form.intervalPreset === preset ? 'var(--hud-bg-deep)' : 'var(--hud-text)',
                  border: '1px solid var(--hud-border)',
                }}
                type="button"
              >
                {preset}
              </button>
            ))}
            <button
              onClick={() => update({ intervalPreset: 'custom' })}
              className="px-2 py-1 text-[12px] cursor-pointer"
              style={{
                background: form.intervalPreset === 'custom' ? 'var(--hud-primary)' : 'transparent',
                color: form.intervalPreset === 'custom' ? 'var(--hud-bg-deep)' : 'var(--hud-text)',
                border: '1px solid var(--hud-border)',
              }}
              type="button"
            >
              {t('cron.createCustom')}
            </button>
            {form.intervalPreset === 'custom' && (
              <span className="flex gap-1">
                <input
                  value={form.intervalValue}
                  onChange={e => update({ intervalValue: e.target.value.replace(/[^\d]/g, '') })}
                  className="w-20 text-[13px] px-2 py-1 outline-none"
                  style={inputStyle}
                  inputMode="numeric"
                />
                <select
                  value={form.intervalUnit}
                  onChange={e => update({ intervalUnit: e.target.value })}
                  className="text-[13px] px-2 py-1 outline-none"
                  style={inputStyle}
                >
                  <option value="m">{t('cron.createMinutes')}</option>
                  <option value="h">{t('cron.createHours')}</option>
                  <option value="d">{t('cron.createDays')}</option>
                </select>
              </span>
            )}
          </div>
        ) : (
          <input
            value={form.cronExpr}
            onChange={e => update({ cronExpr: e.target.value })}
            placeholder="0 9 * * *"
            className={inputClass}
            style={inputStyle}
          />
        )}
      </div>

      <div className="mt-3">
        <FieldLabel>{t('cron.createPrompt')}</FieldLabel>
        <textarea
          value={form.prompt}
          onChange={e => update({ prompt: e.target.value })}
          placeholder={t('cron.createPromptPlaceholder')}
          className="w-full text-[13px] p-2 outline-none resize-y"
          style={{ ...inputStyle, minHeight: '96px' }}
        />
      </div>

      <button
        onClick={() => setAdvancedOpen(open => !open)}
        className="mt-3 text-[11px] cursor-pointer"
        style={{ color: 'var(--hud-primary)' }}
        type="button"
      >
        {advancedOpen ? t('cron.createHideAdvanced') : t('cron.createShowAdvanced')}
      </button>

      {advancedOpen && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mt-2">
          <div>
            <FieldLabel>{t('cron.createSkills')}</FieldLabel>
            <input
              value={form.skills}
              onChange={e => update({ skills: e.target.value })}
              placeholder="llm-wiki, research"
              className={inputClass}
              style={inputStyle}
            />
          </div>
          <div>
            <FieldLabel>{t('cron.createScript')}</FieldLabel>
            <input
              value={form.script}
              onChange={e => update({ script: e.target.value })}
              placeholder="digest.py"
              className={inputClass}
              style={inputStyle}
            />
          </div>
          <div>
            <FieldLabel>{t('cron.createWorkdir')}</FieldLabel>
            <input
              value={form.workdir}
              onChange={e => update({ workdir: e.target.value })}
              placeholder="/home/zerocool/project"
              className={inputClass}
              style={inputStyle}
            />
          </div>
        </div>
      )}

      {error && (
        <div className="mt-3 px-2 py-1.5 text-[12px]" style={{ color: 'var(--hud-error)', background: 'var(--hud-bg-surface)' }}>
          {error}
        </div>
      )}

      <div className="flex justify-end gap-2 mt-3">
        <button
          onClick={onCancel}
          disabled={busy}
          className="px-2 py-1 text-[11px] cursor-pointer disabled:opacity-40"
          style={{ background: 'var(--hud-bg-hover)', color: 'var(--hud-text-dim)', border: '1px solid var(--hud-border)' }}
          type="button"
        >
          {t('memory.cancel')}
        </button>
        <button
          onClick={submit}
          disabled={busy}
          className="px-2 py-1 text-[11px] cursor-pointer disabled:opacity-40"
          style={{ background: 'var(--hud-primary)', color: 'var(--hud-bg-deep)', border: 'none' }}
          type="button"
        >
          {busy ? '...' : t('cron.createSubmit')}
        </button>
      </div>
    </div>
  )
}

export default function CronPanel() {
  const { t } = useTranslation()
  const { data, isLoading, mutate } = useApi<CronResponse>('/cron', 30000)
  const [confirming, setConfirming] = useState<string | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [creating, setCreating] = useState(false)

  const act = async (jobId: string, action: string | null, method = 'POST') => {
    const busyAction = action ?? 'delete'
    setBusy(`${jobId}:${busyAction}`)
    setError(null)
    try {
      await cronAction(jobId, action, method)
      await mutate()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unknown error')
    } finally {
      setBusy(null)
      setConfirming(null)
    }
  }

  if (isLoading && !data) {
    return <Panel title={t('cron.title')} className="col-span-full"><div className="glow text-[13px] animate-pulse">{t('cron.loading')}</div></Panel>
  }

  const jobs = Array.isArray(data) ? data : data?.jobs || []
  const hasJobs = jobs.length > 0

  return (
    <Panel title={t('cron.title')} className="col-span-full">
      <div className="flex items-center justify-between gap-3 mb-3">
        <div className="text-[12px]" style={{ color: 'var(--hud-text-dim)' }}>
          {hasJobs ? `${jobs.length} ${jobs.length === 1 ? t('cron.job') : t('cron.jobs')}` : t('cron.noJobs')}
        </div>
        <button
          onClick={() => setCreating(open => !open)}
          className="px-2 py-1 text-[11px] cursor-pointer"
          style={{
            background: creating ? 'var(--hud-bg-hover)' : 'var(--hud-primary)',
            color: creating ? 'var(--hud-text-dim)' : 'var(--hud-bg-deep)',
            border: creating ? '1px solid var(--hud-border)' : 'none',
          }}
        >
          {creating ? t('memory.cancel') : `+ ${t('cron.createJob')}`}
        </button>
      </div>

      {creating && (
        <CronCreateDrawer
          onCancel={() => setCreating(false)}
          onCreate={async () => {
            setCreating(false)
            await mutate()
          }}
        />
      )}

      {error && (
        <div className="mb-3 px-2 py-1.5 text-[12px]" style={{ color: 'var(--hud-error)', background: 'var(--hud-bg-surface)' }}>
          {error}
        </div>
      )}

      {!hasJobs ? (
        <div className="text-[13px]" style={{ color: 'var(--hud-text-dim)' }}>{t('cron.noJobs')}</div>
      ) : (
        <div className="space-y-3">
          {jobs.map((job: CronJob) => {
            const isPaused = job.state === 'paused'
            const isCompleted = job.state === 'completed'
            const isActive = job.enabled && !isPaused && !isCompleted
            const isBusy = (action: string) => busy === `${job.id}:${action}`
            const isConfirming = confirming === job.id

            return (
              <div key={job.id} className="p-3" style={{ background: 'var(--hud-bg-panel)', border: '1px solid var(--hud-border)' }}>
                <div className="flex flex-wrap items-center gap-2 mb-2">
                  <span className="w-2 h-2 rounded-full shrink-0"
                    style={{ background: isActive ? 'var(--hud-success)' : 'var(--hud-text-dim)' }} />
                  <span className="font-bold text-[13px]" style={{ color: 'var(--hud-primary)' }}>
                    {job.name || job.id}
                  </span>
                  <span className="text-[13px] px-1.5 py-0.5"
                    style={{
                      background: 'var(--hud-bg-hover)',
                      color: isActive ? 'var(--hud-success)' : 'var(--hud-text-dim)'
                    }}>
                    {job.state || 'unknown'}
                  </span>

                  <div className="ml-auto flex flex-wrap items-center gap-1.5">
                    {!isCompleted && (
                      isPaused ? (
                        <button
                          onClick={() => act(job.id, 'resume')}
                          disabled={!!busy}
                          className="px-2 py-0.5 text-[11px] cursor-pointer disabled:opacity-40"
                          style={{ background: 'var(--hud-success)', color: 'var(--hud-bg-deep)' }}
                        >
                          {isBusy('resume') ? '...' : t('cron.resume')}
                        </button>
                      ) : (
                        <>
                          <button
                            onClick={() => act(job.id, 'run')}
                            disabled={!!busy}
                            className="px-2 py-0.5 text-[11px] cursor-pointer disabled:opacity-40"
                            style={{ background: 'var(--hud-accent)', color: 'var(--hud-bg-deep)' }}
                          >
                            {isBusy('run') ? '...' : t('cron.run')}
                          </button>
                          <button
                            onClick={() => act(job.id, 'pause')}
                            disabled={!!busy}
                            className="px-2 py-0.5 text-[11px] cursor-pointer disabled:opacity-40"
                            style={{ background: 'var(--hud-bg-hover)', color: 'var(--hud-text-dim)' }}
                          >
                            {isBusy('pause') ? '...' : t('cron.pause')}
                          </button>
                        </>
                      )
                    )}

                    {isConfirming ? (
                      <>
                        <button
                          onClick={() => act(job.id, null, 'DELETE')}
                          disabled={!!busy}
                          className="px-2 py-0.5 text-[11px] cursor-pointer disabled:opacity-40"
                          style={{ background: 'var(--hud-error)', color: 'var(--hud-bg-deep)' }}
                        >
                          {isBusy('delete') ? '...' : t('cron.confirm')}
                        </button>
                        <button
                          onClick={() => setConfirming(null)}
                          className="px-2 py-0.5 text-[11px] cursor-pointer"
                          style={{ background: 'var(--hud-bg-hover)', color: 'var(--hud-text-dim)' }}
                        >
                          {t('memory.cancel')}
                        </button>
                      </>
                    ) : (
                      <button
                        onClick={() => setConfirming(job.id)}
                        disabled={!!busy}
                        className="px-2 py-0.5 text-[11px] cursor-pointer disabled:opacity-40"
                        style={{ background: 'var(--hud-bg-hover)', color: 'var(--hud-error)' }}
                      >
                        {t('memory.delete')}
                      </button>
                    )}
                  </div>
                </div>

                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-[13px]">
                  <div>
                    <div className="uppercase tracking-wider" style={{ color: 'var(--hud-text-dim)', fontSize: '10px' }}>{t('cron.schedule')}</div>
                    <div style={{ color: 'var(--hud-primary)' }}>{job.schedule_display || job.schedule || '-'}</div>
                  </div>
                  <div>
                    <div className="uppercase tracking-wider" style={{ color: 'var(--hud-text-dim)', fontSize: '10px' }}>{t('cron.lastRun')}</div>
                    <div>
                      {timeAgo(job.last_run_at)}
                      {job.last_status && (
                        <span className="ml-1" style={{ color: job.last_status === 'ok' ? 'var(--hud-success)' : 'var(--hud-error)' }}>
                          {job.last_status === 'ok' ? '✔' : '✗'}
                        </span>
                      )}
                    </div>
                  </div>
                  <div>
                    <div className="uppercase tracking-wider" style={{ color: 'var(--hud-text-dim)', fontSize: '10px' }}>{t('cron.nextRun')}</div>
                    <div>{job.next_run_at ? new Date(job.next_run_at).toLocaleString() : '-'}</div>
                  </div>
                  <div>
                    <div className="uppercase tracking-wider" style={{ color: 'var(--hud-text-dim)', fontSize: '10px' }}>{t('cron.deliver')}</div>
                    <div style={{ color: 'var(--hud-accent)' }}>{job.deliver || '-'}</div>
                  </div>
                </div>

                {job.repeat_completed != null && (
                  <div className="mt-2 text-[13px]" style={{ color: 'var(--hud-text-dim)' }}>
                    {t('cron.runsCompleted')}: {job.repeat_completed}{job.repeat_total ? ` / ${job.repeat_total}` : ''}
                    {!!job.skills?.length && <span className="ml-2">{t('cron.skills')}: {job.skills.join(', ')}</span>}
                  </div>
                )}

                {job.prompt && (
                  <div className="mt-2 text-[13px]" style={{ color: 'var(--hud-text-dim)' }}>
                    {truncate(job.prompt, 120)}
                  </div>
                )}

                {job.paused_reason && (
                  <div className="mt-1 text-[12px]" style={{ color: 'var(--hud-warning)' }}>
                    {t('cron.pausedReason')}: {job.paused_reason}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}
    </Panel>
  )
}
