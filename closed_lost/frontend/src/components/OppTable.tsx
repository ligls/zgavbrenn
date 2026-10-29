import { useVirtualizer } from '@tanstack/react-virtual'
import { useRef } from 'react'
import type { Sort, SortKey } from '../lib/filters'
import { formatDate, formatMonthKey } from '../lib/rows'
import type { Row } from '../types'
import { LinesSummary, StatusBadge } from './Badges'

interface Props {
  rows: Row[]
  sort: Sort
  onSort: (key: SortKey) => void
  onOpen: (id: string) => void
  selectedId: string | null
}

const ROW_HEIGHT = 46

interface Col {
  key: string
  label: string
  sortKey?: SortKey
  className?: string
}

const COLS: Col[] = [
  { key: 'account', label: 'Account', sortKey: 'account_name', className: 'c-account' },
  { key: 'lines', label: 'Lines', sortKey: 'line_count', className: 'c-lines' },
  { key: 'opp', label: 'Opportunity name', className: 'c-opp' },
  { key: 'owner', label: 'Owner', sortKey: 'owner', className: 'c-owner' },
  { key: 'phone', label: 'Phone', className: 'c-phone' },
  { key: 'close', label: 'Closed', sortKey: 'close_date', className: 'c-close' },
  { key: 'renewal', label: 'Renewal', className: 'c-renewal' },
  { key: 'hint', label: 'Contract end', className: 'c-hint' },
  { key: 'status', label: 'Status', sortKey: 'status', className: 'c-status' },
  { key: 'followup', label: 'Follow-up', sortKey: 'follow_up', className: 'c-followup' },
  { key: 'notes', label: 'Notes', className: 'c-notes' },
]

export default function OppTable({ rows, sort, onSort, onOpen, selectedId }: Props) {
  const parentRef = useRef<HTMLDivElement>(null)
  const virtualizer = useVirtualizer({
    count: rows.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => ROW_HEIGHT,
    overscan: 12,
  })

  return (
    <div className="table-wrap" ref={parentRef}>
      <div className="table" role="table" aria-rowcount={rows.length}>
        <div className="thead" role="rowgroup">
          <div className="tr" role="row">
            {COLS.map((c) => {
              const active = c.sortKey && sort.key === c.sortKey
              return (
                <div
                  key={c.key}
                  role="columnheader"
                  aria-sort={active ? (sort.dir === 'asc' ? 'ascending' : 'descending') : undefined}
                  className={`th ${c.className ?? ''} ${c.sortKey ? 'sortable' : ''} ${active ? 'active' : ''}`}
                  onClick={c.sortKey ? () => onSort(c.sortKey as SortKey) : undefined}
                >
                  {c.label}
                  {active && <span className="sort-arrow">{sort.dir === 'asc' ? '▲' : '▼'}</span>}
                </div>
              )
            })}
          </div>
        </div>
        <div className="tbody" role="rowgroup" style={{ height: virtualizer.getTotalSize(), position: 'relative' }}>
          {virtualizer.getVirtualItems().map((v) => {
            const r = rows[v.index]
            return (
              <div
                key={r.id}
                role="row"
                className={`tr body ${r.id === selectedId ? 'selected' : ''} ${r.effCount === null ? 'unknown' : ''}`}
                style={{ transform: `translateY(${v.start}px)`, height: v.size }}
                onClick={() => onOpen(r.id)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') onOpen(r.id)
                }}
                tabIndex={0}
              >
                <div className="td c-account" role="cell" title={r.account_name}>
                  <span className="cell-main">{r.account_name}</span>
                </div>
                <div className="td c-lines" role="cell">
                  <LinesSummary row={r} compact />
                </div>
                <div className="td c-opp" role="cell" title={r.opportunity_name}>
                  {r.opportunity_name}
                </div>
                <div className="td c-owner" role="cell" title={r.owner}>
                  {r.owner}
                </div>
                <div className="td c-phone" role="cell">
                  {r.phone_tel ? (
                    <a href={`tel:${r.phone_tel}`} onClick={(e) => e.stopPropagation()}>
                      {r.phone}
                    </a>
                  ) : (
                    <span className="muted">{r.phone ?? '—'}</span>
                  )}
                </div>
                <div className="td c-close" role="cell">
                  {formatDate(r.close_date)}
                </div>
                <div className="td c-renewal" role="cell">
                  {formatMonthKey(r.estimated_renewal_month)}
                </div>
                <div className="td c-hint" role="cell" title={r.contract_end_hint ?? ''}>
                  {r.contract_end_hint ? (
                    <span className={`hint-pill ${r.contract_end_confidence}`}>
                      {r.contract_end_month ? formatMonthKey(r.contract_end_month) : 'see note'}
                    </span>
                  ) : (
                    <span className="muted">—</span>
                  )}
                </div>
                <div className="td c-status" role="cell">
                  <StatusBadge status={r.status} />
                </div>
                <div className="td c-followup" role="cell">
                  {r.followUp ? formatDate(r.followUp) : <span className="muted">—</span>}
                </div>
                <div className="td c-notes" role="cell" title={r.notes}>
                  {r.notes || <span className="muted">—</span>}
                </div>
              </div>
            )
          })}
        </div>
      </div>
      {rows.length === 0 && <div className="empty">No opportunities match the current filters.</div>}
    </div>
  )
}
