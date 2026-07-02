export type ReplayStatus = 'success' | 'failed' | 'partial' | 'unknown'

export type ReplayCounts = {
  messages: number
  tool_calls: number
  skills_used: number
  files_changed?: number | null
  tests_passed?: number | null
  tests_failed?: number | null
  subagents?: number | null
}

export type ReplayHashes = {
  source_hash?: string | null
  redacted_replay_hash?: string | null
  receipt_hash?: string | null
}

export type ReplayRun = {
  replay_id: string
  source_session_id: string
  title: string
  status: ReplayStatus
  started_at?: string | null
  ended_at?: string | null
  duration_ms?: number | null
  primary_model?: string | null
  total_cost_usd?: number | null
  counts: ReplayCounts
  hashes: ReplayHashes
  redaction_status: string
  created_at?: string | null
  updated_at?: string | null
}

export type ReplayEvent = {
  event_id: string
  replay_id: string
  type: string
  title: string
  summary: string
  raw_content?: string | null
  redacted_content?: string | null
  timestamp?: string | null
  duration_ms?: number | null
  status: string
  metadata?: Record<string, unknown>
}

export type RunReceipt = {
  schema_version: string
  receipt_id: string
  replay_id: string
  source_session_id: string
  title: string
  status: string
  started_at?: string | null
  ended_at?: string | null
  duration_ms?: number | null
  model?: string | null
  total_cost_usd?: number | null
  tool_call_count: number
  skills_used: Array<{ name: string; version?: string | null; hash?: string | null }>
  files_changed?: number | null
  hashes: ReplayHashes
  redaction: {
    mode: string
    findings_count: number
    redacted_fields_count: number
  }
  generated_at: string
  generator: {
    name: string
    version: string
  }
}

export type ReplayArtifact = {
  artifact_id: string
  replay_id: string
  type: string
  title: string
  summary?: string | null
  event_id?: string | null
  path?: string | null
  content?: string | null
  redacted_content?: string | null
  mime_type?: string | null
  size_bytes?: number | null
  hash?: string | null
}

export type ReplayDetail = {
  run: ReplayRun
  events: ReplayEvent[]
  artifacts: ReplayArtifact[]
  receipt?: RunReceipt | null
  missing_data: string[]
  redactions?: Array<{
    finding_id: string
    severity: string
    type: string
    field_path: string
    preview: string
    replacement: string
    auto_redacted: boolean
  }>
}

export type ReplayRunsResponse = {
  runs: ReplayRun[]
}
