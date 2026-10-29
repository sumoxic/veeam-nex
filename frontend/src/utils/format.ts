/** 展示层的通用格式化工具。 */

/** 后端返回的是无时区的 UTC ISO 字符串，统一按本地时区展示。 */
export function formatDateTime(value?: string | null): string {
  if (!value) return '-'
  const normalized = /[zZ]|[+-]\d{2}:?\d{2}$/.test(value) ? value : `${value}Z`
  const d = new Date(normalized)
  if (Number.isNaN(d.getTime())) return value
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(
    d.getMinutes(),
  )}:${pad(d.getSeconds())}`
}

export function formatDuration(ms?: number | null): string {
  if (ms === null || ms === undefined) return '-'
  if (ms < 1000) return `${ms} ms`
  const s = ms / 1000
  if (s < 60) return `${s.toFixed(1)} 秒`
  const m = Math.floor(s / 60)
  const rest = Math.round(s % 60)
  if (m < 60) return `${m} 分 ${rest} 秒`
  const h = Math.floor(m / 60)
  return `${h} 小时 ${m % 60} 分`
}

export function formatPercent(value?: number | null, digits = 1): string {
  if (value === null || value === undefined) return '-'
  return `${value.toFixed(digits)}%`
}

export function formatBytes(bytes?: number | null): string {
  if (bytes === null || bytes === undefined) return '-'
  const units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']
  let v = bytes
  let i = 0
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024
    i += 1
  }
  return `${v.toFixed(2)} ${units[i]}`
}

/** 秒级时长 → 人类可读（用于告警冷却、令牌有效期等）。 */
export function formatMinutes(minutes?: number | null): string {
  if (minutes === null || minutes === undefined) return '-'
  if (minutes < 60) return `${minutes} 分钟`
  if (minutes % 1440 === 0) return `${minutes / 1440} 天`
  return `${Math.floor(minutes / 60)} 小时 ${minutes % 60} 分`
}
