import { useState } from 'react'
import type { DynamicToolUIPart, ToolUIPart, UITools } from 'ai'
import { isStaticToolUIPart } from 'ai'

type AnyToolPart = DynamicToolUIPart | ToolUIPart<UITools>

interface ToolCallCardProps {
  part: AnyToolPart
}

export default function ToolCallCard({ part }: ToolCallCardProps) {
  const [expanded, setExpanded] = useState(false)

  const toolName = isStaticToolUIPart(part)
    ? String(part.type).replace(/^tool-/, '')
    : part.toolName
  const toolCallId = part.toolCallId
  const state = part.state

  const isRunning = state === 'input-streaming' || state === 'input-available'
  const isError = state === 'output-error'
  const isDone = state === 'output-available'

  const input = 'input' in part ? part.input : undefined
  const output = isDone && 'output' in part ? (part as DynamicToolUIPart & { state: 'output-available' }).output : undefined
  const errorText = isError && 'errorText' in part ? (part as DynamicToolUIPart & { state: 'output-error' }).errorText : undefined

  return (
    <div
      className="my-2 text-[12px]"
      style={{
        borderLeft: `2px solid ${isRunning ? 'var(--hud-warning)' : isError ? 'var(--hud-error)' : 'var(--hud-success)'}`,
        background: 'var(--hud-bg-surface)',
      }}
    >
      {/* Header */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full px-2 py-1.5 flex items-center justify-between cursor-pointer text-left"
        style={{ color: 'var(--hud-text)' }}
      >
        <div className="flex items-center gap-2">
          <span
            style={{
              color: isRunning ? 'var(--hud-warning)' : isError ? 'var(--hud-error)' : 'var(--hud-success)',
            }}
          >
            {isRunning ? '▸' : isError ? '✗' : '✓'}
          </span>
          <span className="font-bold">{toolName}</span>
          {isRunning && (
            <span className="animate-pulse" style={{ color: 'var(--hud-warning)' }}>
              running...
            </span>
          )}
        </div>
        <span style={{ color: 'var(--hud-text-dim)' }}>{expanded ? '▼' : '▶'}</span>
      </button>

      {/* Expanded content */}
      {expanded && (
        <div className="px-2 pb-2 space-y-2">
          {/* Arguments / Input */}
          {input !== undefined && (
            <div>
              <div style={{ color: 'var(--hud-text-dim)' }} className="mb-0.5">
                arguments:
              </div>
              <pre
                className="p-1.5 overflow-x-auto text-[11px]"
                style={{
                  background: 'var(--hud-bg-hover)',
                  color: 'var(--hud-text)',
                  fontFamily: 'monospace',
                }}
              >
                {JSON.stringify(input, null, 2)}
              </pre>
            </div>
          )}

          {/* Tool call ID */}
          {toolCallId && (
            <div style={{ color: 'var(--hud-text-dim)', fontSize: '10px' }}>
              id: {toolCallId}
            </div>
          )}

          {/* Result or Error */}
          {(output !== undefined || errorText) && (
            <div>
              <div
                style={{
                  color: errorText ? 'var(--hud-error)' : 'var(--hud-success)',
                }}
                className="mb-0.5"
              >
                {errorText ? 'error:' : 'result:'}
              </div>
              <pre
                className="p-1.5 overflow-x-auto text-[11px]"
                style={{
                  background: 'var(--hud-bg-hover)',
                  color: 'var(--hud-text)',
                  fontFamily: 'monospace',
                }}
              >
                {errorText ?? JSON.stringify(output, null, 2)}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
