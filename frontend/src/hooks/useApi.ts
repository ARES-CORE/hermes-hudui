import useSWR, { mutate } from 'swr'

const fetcher = async (url: string) => {
  const res = await fetch(url)
  if (!res.ok) {
    const text = await res.text()
    throw new Error(`${res.status}: ${text}`)
  }
  return res.json()
}

export function useApi<T = any>(path: string | null, refreshInterval = 30000) {
  return useSWR<T>(path ? `/api${path}` : null, fetcher, {
    refreshInterval,
    revalidateOnFocus: false,
    dedupingInterval: 5000,
    errorRetryCount: 3,
    errorRetryInterval: 2000,
    keepPreviousData: true, // Keep showing old data while fetching new data
    onError: (err) => {
      console.warn(`[HUD] ${path || 'disabled'}: ${err.message}`)
    },
  })
}

/** Force-revalidate all SWR caches (for manual refresh) */
export function refreshAll() {
  mutate(
    (key) => typeof key === 'string' && key.startsWith('/api'),
    undefined,
    { revalidate: true }
  )
}
