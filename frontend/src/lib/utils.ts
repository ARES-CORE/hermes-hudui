/** Shared formatting utilities */

export function timeAgo(iso: string | null | undefined): string {
  if (!iso) return 'never'
  const d = new Date(iso)
  if (isNaN(d.getTime())) return 'never'
  const now = new Date()
  const secs = Math.floor((now.getTime() - d.getTime()) / 1000)
  if (secs < 0) return 'just now'
  if (secs < 60) return `${secs}s ago`
  if (secs < 3600) return `${Math.floor(secs / 60)}m ago`
  if (secs < 86400) {
    const h = Math.floor(secs / 3600)
    const m = Math.floor((secs % 3600) / 60)
    return m ? `${h}h${m}m ago` : `${h}h ago`
  }
  const days = Math.floor(secs / 86400)
  if (days < 30) return `${days}d ago`
  return `${Math.floor(days / 30)}mo ago`
}

export function formatDur(mins: number | null | undefined): string {
  if (!mins) return ''
  if (mins < 1) return '<1m'
  if (mins < 60) return `${Math.floor(mins)}m`
  const h = Math.floor(mins / 60)
  const m = Math.floor(mins % 60)
  return m ? `${h}h${m}m` : `${h}h`
}

export function formatTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`
  return String(n)
}

export function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes}B`
  if (bytes < 1048576) return `${(bytes / 1024).toFixed(0)}KB`
  return `${(bytes / 1048576).toFixed(1)}MB`
}

export function truncate(str: string, len: number): string {
  if (!str) return ''
  return str.length > len ? str.slice(0, len - 3) + '...' : str
}
