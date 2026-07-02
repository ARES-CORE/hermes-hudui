import { useState, useRef, useEffect } from 'react'
import { useTranslation } from '../../i18n'

interface ComposerProps {
  onSend: (message: string) => void
  onCancel?: () => void
  isStreaming: boolean
  model: string
  status?: string
  elapsedMs?: number
  firstTokenMs?: number | null
  disabled?: boolean
}

const STATUS_LABELS: Record<string, string> = {
  starting_hermes: 'starting Hermes',
  connecting_model: 'connecting model',
  streaming: 'streaming',
  finalizing_tools: 'finalizing tools',
  cancelling: 'cancelling',
  cancelled: 'cancelled',
  error: 'error',
}

function formatSeconds(ms?: number | null) {
  if (!ms || ms < 0) return ''
  return `${(ms / 1000).toFixed(ms < 10_000 ? 1 : 0)}s`
}

export default function Composer({
  onSend,
  onCancel,
  isStreaming,
  model,
  status = 'idle',
  elapsedMs = 0,
  firstTokenMs = null,
  disabled,
}: ComposerProps) {
  const { t } = useTranslation()
  const [input, setInput] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const statusLabel = STATUS_LABELS[status] ?? t('chat.thinking')
  const timingLabel = firstTokenMs ? `first token ${formatSeconds(firstTokenMs)}` : formatSeconds(elapsedMs)

  const handleSubmit = () => {
    const trimmed = input.trim()
    if (!trimmed || isStreaming || disabled) return

    onSend(trimmed)
    setInput('')

    // Reset textarea height
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit()
    }
  }

  // Auto-resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 120)}px`
    }
  }, [input])

  return (
    <div
      className="border-t px-2 py-1.5"
      style={{
        borderColor: 'var(--hud-border)',
        background: 'var(--hud-bg-surface)',
      }}
    >
      <div className="flex items-end gap-2">
        <textarea
          ref={textareaRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={disabled ? t('chat.notAvailable') : t('chat.placeholder')}
          disabled={isStreaming || disabled}
          rows={1}
          className="flex-1 px-2 py-1.5 text-[13px] resize-none outline-none"
          style={{
            background: 'var(--hud-bg-panel)',
            color: 'var(--hud-text)',
            border: '1px solid var(--hud-border)',
            minHeight: '32px',
            maxHeight: '120px',
          }}
        />
        {isStreaming ? (
          <button
            onClick={onCancel}
            className="px-3 py-1.5 text-[13px] font-bold cursor-pointer"
            style={{
              background: 'var(--hud-error)',
              color: 'var(--hud-bg-deep)',
              border: 'none',
              minHeight: '32px',
            }}
            title={t('chat.stopGeneration')}
          >
            ■ {t('chat.stop')}
          </button>
        ) : (
          <button
            onClick={handleSubmit}
            disabled={!input.trim() || disabled}
            className="px-3 py-1.5 text-[13px] font-bold cursor-pointer disabled:opacity-40"
            style={{
              background: 'var(--hud-primary)',
              color: 'var(--hud-bg-deep)',
              border: 'none',
              minHeight: '32px',
            }}
          >
            {t('chat.send')}
          </button>
        )}
      </div>
      <div
        className="mt-1 text-[11px] flex justify-between"
        style={{ color: 'var(--hud-text-dim)' }}
      >
        <span>{model !== 'unknown' ? model : ''}</span>
        <span style={{ color: isStreaming ? 'var(--hud-warning)' : 'var(--hud-text-dim)' }}>
          {isStreaming ? `${statusLabel}${timingLabel ? ` · ${timingLabel}` : ''}` : t('chat.enterHint')}
        </span>
      </div>
    </div>
  )
}
