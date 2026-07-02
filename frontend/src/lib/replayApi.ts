import type { ReplayDetail, ReplayRunsResponse } from '../types/replay'

export async function fetchReplayRuns(limit = 50): Promise<ReplayRunsResponse> {
  const res = await fetch(`/api/replay/runs?limit=${limit}`)
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function fetchReplayDetail(sessionId: string): Promise<ReplayDetail> {
  const res = await fetch(`/api/replay/runs/${encodeURIComponent(sessionId)}`)
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

