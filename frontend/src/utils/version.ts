/** VBR 版本标识：从构建号推断大版本，并生成统一的展示文案。 */

export type VersionPreference = 'auto' | '12' | '13'

export const VERSION_PREFERENCE_OPTIONS: { value: VersionPreference; label: string }[] = [
  { value: 'auto', label: '自动检测' },
  { value: '12', label: 'VBR 12' },
  { value: '13', label: 'VBR 13' },
]

/** 构建号首段即大版本，例如 12.3.2.3617 → 12。 */
export function vbrMajor(build?: string | null): '12' | '13' | null {
  if (!build) return null
  const major = /^\s*(\d+)/.exec(build)?.[1]
  return major === '12' || major === '13' ? major : null
}

/** 版本标签文案；尚未探测到构建号时回退到用户选择的版本。 */
export function versionLabel(
  build?: string | null,
  preference?: VersionPreference | string | null,
): string {
  const major = vbrMajor(build)
  if (major) return `VBR ${major}`
  if (preference === '12' || preference === '13') return `VBR ${preference}`
  return '待检测'
}

export function preferenceLabel(preference?: VersionPreference | string | null): string {
  if (preference === '12') return 'VBR 12'
  if (preference === '13') return 'VBR 13'
  return '自动检测'
}
