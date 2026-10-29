import { useMemo } from 'react'
import { facetCounts, type Filters } from '../lib/filters'
import { BUCKETS, formatNumber } from '../lib/rows'
import type { LineType, Row } from '../types'
import { LINE_TYPES } from '../types'
import BarChart from './BarChart'

interface Props {
  rows: Row[]
  filtered: Row[]
  filters: Filters
  total: number
  onToggleBucket: (bucket: string) => void
  onToggleType: (type: LineType) => void
  onToggleCloseMonth: (month: string) => void
}

export default function Dashboard({ rows, filtered, filters, total, onToggleBucket, onToggleType, onToggleCloseMonth }: Props) {
  const bucketCounts = useMemo(() => facetCounts(rows, filters, 'buckets', (r) => r.effBucket), [rows, filters])
  const typeCounts = useMemo(() => facetCounts(rows, filters, 'types', (r) => r.effType), [rows, filters])
  const monthCounts = useMemo(() => facetCounts(rows, filters, 'closeMonths', (r) => r.close_month), [rows, filters])

  const unknown = filtered.filter((r) => r.effCount === null).length
  const knownLines = filtered.reduce((acc, r) => acc + (r.effCount ?? 0), 0)
  const worked = filtered.filter((r) => r.status !== 'Not started').length
  const withHint = filtered.filter((r) => r.contract_end_hint).length

  const months = useMemo(() => {
    const keys = Array.from(new Set(rows.map((r) => r.close_month))).sort()
    return keys.map((k) => ({
      key: k,
      label: rows.find((r) => r.close_month === k)?.close_month_label ?? k,
      value: monthCounts.get(k) ?? 0,
      selected: filters.closeMonths.includes(k),
    }))
  }, [rows, monthCounts, filters.closeMonths])

  return (
    <section className="dashboard" aria-label="Summary">
      <div className="tiles">
        <Tile label="Opportunities" value={formatNumber(filtered.length)} sub={filtered.length === total ? 'all rows' : `of ${formatNumber(total)}`} />
        <Tile
          label="Unknown line count"
          value={formatNumber(unknown)}
          sub={filtered.length ? `${Math.round((unknown / filtered.length) * 100)}% of shown` : ''}
          tone={unknown > 0 ? 'flag' : undefined}
        />
        <Tile label="Known lines" value={formatNumber(knownLines)} sub="sum of counts shown" />
        <Tile label="Worked" value={formatNumber(worked)} sub="status set" />
        <Tile label="Contract-end hint" value={formatNumber(withHint)} sub="in Additional Info" />
      </div>
      <div className="charts">
        <div className="chart-card wide">
          <h3>By line count bucket</h3>
          <BarChart
            title="Opportunities by line-count bucket"
            bars={BUCKETS.map((b) => ({
              key: b,
              label: b === 'Unknown' ? '?' : b,
              value: bucketCounts.get(b) ?? 0,
              selected: filters.buckets.includes(b),
            }))}
            onToggle={onToggleBucket}
            emphasize={filters.buckets.length > 0}
            flagKeys={['Unknown']}
            height={200}
          />
        </div>
        <div className="chart-card">
          <h3>By line type</h3>
          <BarChart
            title="Opportunities by line type"
            bars={LINE_TYPES.map((t) => ({
              key: t,
              label: t,
              value: typeCounts.get(t) ?? 0,
              selected: filters.types.includes(t),
            }))}
            onToggle={(k) => onToggleType(k as LineType)}
            emphasize={filters.types.length > 0}
            flagKeys={['Unknown']}
            height={200}
            labelAll
          />
        </div>
        <div className="chart-card">
          <h3>By close month</h3>
          <BarChart
            title="Opportunities by close month"
            bars={months}
            onToggle={onToggleCloseMonth}
            emphasize={filters.closeMonths.length > 0}
            height={200}
            labelAll
          />
        </div>
      </div>
    </section>
  )
}

function Tile({ label, value, sub, tone }: { label: string; value: string; sub?: string; tone?: 'flag' }) {
  return (
    <div className={`tile ${tone ?? ''}`}>
      <div className="tile-label">{label}</div>
      <div className="tile-value">{value}</div>
      {sub && <div className="tile-sub">{sub}</div>}
    </div>
  )
}
