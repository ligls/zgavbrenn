import type { Edit, LineType, Opportunity, Row } from '../types'
import { digitsOnly, normalize } from './normalize'

export const BUCKETS: string[] = [
  ...Array.from({ length: 20 }, (_, i) => String(i + 1)),
  '21-25',
  '26-30',
  '31+',
  'Unknown',
]

export function bucketFor(count: number | null): string {
  if (count === null || count === undefined || Number.isNaN(count)) return 'Unknown'
  if (count <= 20) return String(count)
  if (count <= 25) return '21-25'
  if (count <= 30) return '26-30'
  return '31+'
}

/** Merge the imported opportunity with its saved edit and precompute derived fields. */
export function buildRow(opp: Opportunity, edit: Edit | null): Row {
  const effCount =
    edit && edit.line_count_override !== null && edit.line_count_override !== undefined
      ? edit.line_count_override
      : opp.line_count
  const effType: LineType = (edit?.line_type_override as LineType | null) ?? opp.line_type
  const overridden =
    !!edit &&
    ((edit.line_count_override !== null && edit.line_count_override !== undefined) || !!edit.line_type_override)
  const status = edit?.status ?? 'Not started'
  const notes = edit?.notes ?? ''
  const followUp = edit?.follow_up_date ?? null

  const searchBlob = [
    normalize(opp.account_name),
    normalize(opp.account_name_raw),
    normalize(opp.opportunity_name),
    normalize(opp.additional_info),
    normalize(opp.owner),
    normalize(opp.phone),
    digitsOnly(opp.phone),
    normalize(notes),
  ].join(' \u0001 ')

  return {
    ...opp,
    edit,
    effCount,
    effType,
    effBucket: bucketFor(effCount),
    overridden,
    status,
    notes,
    followUp,
    searchBlob,
  }
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return ''
  const [y, m, d] = iso.split('-').map(Number)
  if (!y || !m || !d) return iso
  const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
  return `${d} ${months[m - 1]} ${y}`
}

export function formatMonthKey(key: string | null | undefined): string {
  if (!key) return ''
  const [y, m] = key.split('-').map(Number)
  const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
  if (!y || !m) return key
  return `${months[m - 1]} ${y}`
}

export function todayIso(): string {
  const d = new Date()
  const mm = String(d.getMonth() + 1).padStart(2, '0')
  const dd = String(d.getDate()).padStart(2, '0')
  return `${d.getFullYear()}-${mm}-${dd}`
}

export function formatNumber(n: number): string {
  return n.toLocaleString('en-CA')
}
