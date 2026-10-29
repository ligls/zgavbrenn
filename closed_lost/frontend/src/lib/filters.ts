import type { Row, Status } from '../types'
import { matchesQuery, queryTokens } from './normalize'
import { todayIso } from './rows'

export type TriState = 'any' | 'yes' | 'no'

export interface Filters {
  q: string
  buckets: string[]
  types: string[]
  owners: string[]
  closeMonths: string[]
  renewalMonths: string[]
  statuses: Status[]
  hasPhone: TriState
  hasInfo: TriState
  hasHint: TriState
  followUpDue: boolean
}

export const EMPTY_FILTERS: Filters = {
  q: '',
  buckets: [],
  types: [],
  owners: [],
  closeMonths: [],
  renewalMonths: [],
  statuses: [],
  hasPhone: 'any',
  hasInfo: 'any',
  hasHint: 'any',
  followUpDue: false,
}

export function isFilterActive(f: Filters): boolean {
  return (
    f.q.trim() !== '' ||
    f.buckets.length > 0 ||
    f.types.length > 0 ||
    f.owners.length > 0 ||
    f.closeMonths.length > 0 ||
    f.renewalMonths.length > 0 ||
    f.statuses.length > 0 ||
    f.hasPhone !== 'any' ||
    f.hasInfo !== 'any' ||
    f.hasHint !== 'any' ||
    f.followUpDue
  )
}

function tri(state: TriState, value: boolean): boolean {
  if (state === 'any') return true
  return state === 'yes' ? value : !value
}

/** Which facet to ignore so its own option counts stay stable while you click them. */
export type Facet = 'buckets' | 'types' | 'owners' | 'closeMonths' | 'renewalMonths' | 'statuses' | null

export function rowMatches(row: Row, f: Filters, tokens: string[], skip: Facet = null, today = todayIso()): boolean {
  if (skip !== 'buckets' && f.buckets.length && !f.buckets.includes(row.effBucket)) return false
  if (skip !== 'types' && f.types.length && !f.types.includes(row.effType)) return false
  if (skip !== 'owners' && f.owners.length && !f.owners.includes(row.owner)) return false
  if (skip !== 'closeMonths' && f.closeMonths.length && !f.closeMonths.includes(row.close_month)) return false
  if (skip !== 'renewalMonths' && f.renewalMonths.length && !f.renewalMonths.includes(row.estimated_renewal_month))
    return false
  if (skip !== 'statuses' && f.statuses.length && !f.statuses.includes(row.status)) return false
  if (!tri(f.hasPhone, !!row.phone)) return false
  if (!tri(f.hasInfo, !!row.additional_info)) return false
  if (!tri(f.hasHint, !!row.contract_end_hint)) return false
  if (f.followUpDue && !(row.followUp && row.followUp <= today)) return false
  if (tokens.length && !matchesQuery(row.searchBlob, tokens)) return false
  return true
}

export function applyFilters(rows: Row[], f: Filters): Row[] {
  const tokens = queryTokens(f.q)
  const today = todayIso()
  return rows.filter((r) => rowMatches(r, f, tokens, null, today))
}

/** Counts per option for one facet, computed with every other filter applied. */
export function facetCounts(rows: Row[], f: Filters, facet: Exclude<Facet, null>, key: (r: Row) => string): Map<string, number> {
  const tokens = queryTokens(f.q)
  const today = todayIso()
  const counts = new Map<string, number>()
  for (const r of rows) {
    if (!rowMatches(r, f, tokens, facet, today)) continue
    const k = key(r)
    counts.set(k, (counts.get(k) ?? 0) + 1)
  }
  return counts
}

// ---------------------------------------------------------------- sorting

export type SortKey = 'line_count' | 'close_date' | 'account_name' | 'owner' | 'status' | 'follow_up'
export type SortDir = 'asc' | 'desc'

export interface Sort {
  key: SortKey
  dir: SortDir
}

export const SORT_LABELS: Record<SortKey, string> = {
  line_count: 'Line count',
  close_date: 'Close date',
  account_name: 'Account name',
  owner: 'Owner',
  status: 'Status',
  follow_up: 'Follow-up date',
}

const STATUS_ORDER: Record<Status, number> = {
  'Not started': 0,
  Called: 1,
  'Left voicemail': 2,
  'Callback scheduled': 3,
  'Not interested': 4,
  'Won back': 5,
}

const collator = new Intl.Collator('fr-CA', { sensitivity: 'base', numeric: true })

export function sortRows(rows: Row[], sort: Sort): Row[] {
  const dir = sort.dir === 'asc' ? 1 : -1
  const out = rows.slice()
  out.sort((a, b) => {
    let c = 0
    switch (sort.key) {
      case 'line_count': {
        // Unknown counts always sink to the bottom, whatever the direction.
        const an = a.effCount === null
        const bn = b.effCount === null
        if (an && bn) c = 0
        else if (an) return 1
        else if (bn) return -1
        else c = (a.effCount as number) - (b.effCount as number)
        break
      }
      case 'close_date':
        c = a.close_date.localeCompare(b.close_date)
        break
      case 'account_name':
        c = collator.compare(a.account_name, b.account_name)
        break
      case 'owner':
        c = collator.compare(a.owner, b.owner)
        break
      case 'status':
        c = STATUS_ORDER[a.status] - STATUS_ORDER[b.status]
        break
      case 'follow_up': {
        const af = a.followUp
        const bf = b.followUp
        if (!af && !bf) c = 0
        else if (!af) return 1
        else if (!bf) return -1
        else c = af.localeCompare(bf)
        break
      }
    }
    if (c === 0) c = collator.compare(a.account_name, b.account_name) || a.row_number - b.row_number
    return c * dir
  })
  return out
}
