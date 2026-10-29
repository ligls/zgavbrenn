import { useMemo } from 'react'
import { EMPTY_FILTERS, facetCounts, type Filters, type TriState } from '../lib/filters'
import { BUCKETS, formatMonthKey, formatNumber } from '../lib/rows'
import type { Row, Status } from '../types'
import { LINE_TYPES, STATUSES } from '../types'
import MultiSelect from './MultiSelect'

interface Props {
  rows: Row[]
  filters: Filters
  onChange: (next: Filters) => void
}

function toggleIn<T>(list: T[], value: T): T[] {
  return list.includes(value) ? list.filter((v) => v !== value) : [...list, value]
}

export default function FiltersPanel({ rows, filters, onChange }: Props) {
  const set = (patch: Partial<Filters>) => onChange({ ...filters, ...patch })

  const bucketCounts = useMemo(() => facetCounts(rows, filters, 'buckets', (r) => r.effBucket), [rows, filters])
  const typeCounts = useMemo(() => facetCounts(rows, filters, 'types', (r) => r.effType), [rows, filters])
  const ownerCounts = useMemo(() => facetCounts(rows, filters, 'owners', (r) => r.owner), [rows, filters])
  const closeCounts = useMemo(() => facetCounts(rows, filters, 'closeMonths', (r) => r.close_month), [rows, filters])
  const renewalCounts = useMemo(
    () => facetCounts(rows, filters, 'renewalMonths', (r) => r.estimated_renewal_month),
    [rows, filters],
  )
  const statusCounts = useMemo(() => facetCounts(rows, filters, 'statuses', (r) => r.status), [rows, filters])

  const owners = useMemo(() => {
    const all = Array.from(new Set(rows.map((r) => r.owner))).sort((a, b) => a.localeCompare(b))
    return all.map((o) => ({ value: o, label: o, count: ownerCounts.get(o) ?? 0 }))
  }, [rows, ownerCounts])

  const closeMonths = useMemo(() => Array.from(new Set(rows.map((r) => r.close_month))).sort(), [rows])
  const renewalMonths = useMemo(() => Array.from(new Set(rows.map((r) => r.estimated_renewal_month))).sort(), [rows])

  return (
    <aside className="filters" aria-label="Filters">
      <div className="filters-head">
        <h2>Filters</h2>
        <button type="button" className="link" onClick={() => onChange({ ...EMPTY_FILTERS })}>
          Clear all
        </button>
      </div>

      <label className="field">
        <span className="field-label">Search</span>
        <input
          type="search"
          value={filters.q}
          placeholder="Account, opportunity, notes, phone…"
          onChange={(e) => set({ q: e.target.value })}
        />
        <span className="hint">Accent-insensitive. Several words = all must match.</span>
      </label>

      <fieldset className="field">
        <legend className="field-label">
          Line count bucket
          {filters.buckets.length > 0 && (
            <button type="button" className="link small" onClick={() => set({ buckets: [] })}>
              clear
            </button>
          )}
        </legend>
        <div className="bucket-grid">
          {BUCKETS.map((b) => {
            const n = bucketCounts.get(b) ?? 0
            const on = filters.buckets.includes(b)
            return (
              <button
                key={b}
                type="button"
                className={`chip ${on ? 'on' : ''} ${b === 'Unknown' ? 'flag' : ''} ${n === 0 && !on ? 'zero' : ''}`}
                onClick={() => set({ buckets: toggleIn(filters.buckets, b) })}
                aria-pressed={on}
                title={`${b}: ${formatNumber(n)} opportunities`}
              >
                <span className="chip-label">{b}</span>
                <span className="chip-count">{formatNumber(n)}</span>
              </button>
            )
          })}
        </div>
      </fieldset>

      <fieldset className="field">
        <legend className="field-label">Line type</legend>
        <div className="chip-row">
          {LINE_TYPES.map((t) => {
            const on = filters.types.includes(t)
            return (
              <button
                key={t}
                type="button"
                className={`chip ${on ? 'on' : ''}`}
                onClick={() => set({ types: toggleIn(filters.types, t) })}
                aria-pressed={on}
              >
                <span className="chip-label">{t}</span>
                <span className="chip-count">{formatNumber(typeCounts.get(t) ?? 0)}</span>
              </button>
            )
          })}
        </div>
      </fieldset>

      <div className="field">
        <span className="field-label">Opportunity owner</span>
        <MultiSelect label="Owners" options={owners} selected={filters.owners} onChange={(owners) => set({ owners })} />
      </div>

      <fieldset className="field">
        <legend className="field-label">Close month</legend>
        <div className="chip-row">
          {closeMonths.map((m) => {
            const on = filters.closeMonths.includes(m)
            return (
              <button
                key={m}
                type="button"
                className={`chip ${on ? 'on' : ''}`}
                onClick={() => set({ closeMonths: toggleIn(filters.closeMonths, m) })}
                aria-pressed={on}
              >
                <span className="chip-label">{formatMonthKey(m)}</span>
                <span className="chip-count">{formatNumber(closeCounts.get(m) ?? 0)}</span>
              </button>
            )
          })}
        </div>
      </fieldset>

      <fieldset className="field">
        <legend className="field-label">Estimated renewal (close + 24 mo)</legend>
        <div className="chip-row">
          {renewalMonths.map((m) => {
            const on = filters.renewalMonths.includes(m)
            return (
              <button
                key={m}
                type="button"
                className={`chip ${on ? 'on' : ''}`}
                onClick={() => set({ renewalMonths: toggleIn(filters.renewalMonths, m) })}
                aria-pressed={on}
              >
                <span className="chip-label">{formatMonthKey(m)}</span>
                <span className="chip-count">{formatNumber(renewalCounts.get(m) ?? 0)}</span>
              </button>
            )
          })}
        </div>
      </fieldset>

      <fieldset className="field">
        <legend className="field-label">Work status</legend>
        <div className="chip-row">
          {STATUSES.map((s) => {
            const on = filters.statuses.includes(s)
            return (
              <button
                key={s}
                type="button"
                className={`chip ${on ? 'on' : ''}`}
                onClick={() => set({ statuses: toggleIn(filters.statuses, s as Status) })}
                aria-pressed={on}
              >
                <span className="chip-label">{s}</span>
                <span className="chip-count">{formatNumber(statusCounts.get(s) ?? 0)}</span>
              </button>
            )
          })}
        </div>
        <label className="check">
          <input type="checkbox" checked={filters.followUpDue} onChange={(e) => set({ followUpDue: e.target.checked })} />
          Follow-up due (today or earlier)
        </label>
      </fieldset>

      <TriField label="Has phone" value={filters.hasPhone} onChange={(hasPhone) => set({ hasPhone })} />
      <TriField label="Has Additional Info" value={filters.hasInfo} onChange={(hasInfo) => set({ hasInfo })} />
      <TriField label="Has contract-end hint" value={filters.hasHint} onChange={(hasHint) => set({ hasHint })} />
    </aside>
  )
}

function TriField({ label, value, onChange }: { label: string; value: TriState; onChange: (v: TriState) => void }) {
  return (
    <fieldset className="field">
      <legend className="field-label">{label}</legend>
      <div className="segmented" role="radiogroup" aria-label={label}>
        {(['any', 'yes', 'no'] as TriState[]).map((v) => (
          <button
            key={v}
            type="button"
            role="radio"
            aria-checked={value === v}
            className={value === v ? 'on' : ''}
            onClick={() => onChange(v)}
          >
            {v === 'any' ? 'Any' : v === 'yes' ? 'Yes' : 'No'}
          </button>
        ))}
      </div>
    </fieldset>
  )
}
