import { useVirtualizer } from '@tanstack/react-virtual'
import { useEffect, useRef, useState } from 'react'
import { formatDate, formatMonthKey } from '../lib/rows'
import type { Row } from '../types'
import { LinesSummary, StatusBadge } from './Badges'

interface Props {
  rows: Row[]
  onOpen: (id: string) => void
  selectedId: string | null
}

/** Virtualised card grid: each virtual item is one row of N cards. */
export default function OppCards({ rows, onOpen, selectedId }: Props) {
  const parentRef = useRef<HTMLDivElement>(null)
  const [columns, setColumns] = useState(2)

  useEffect(() => {
    const el = parentRef.current
    if (!el) return
    const update = () => {
      const w = el.clientWidth
      setColumns(w >= 1500 ? 3 : w >= 980 ? 2 : 1)
    }
    update()
    const ro = new ResizeObserver(update)
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  const rowCount = Math.ceil(rows.length / columns)
  const virtualizer = useVirtualizer({
    count: rowCount,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 236,
    overscan: 4,
    measureElement: (el) => el.getBoundingClientRect().height,
  })

  return (
    <div className="cards-wrap" ref={parentRef}>
      <div style={{ height: virtualizer.getTotalSize(), position: 'relative' }}>
        {virtualizer.getVirtualItems().map((v) => {
          const start = v.index * columns
          const slice = rows.slice(start, start + columns)
          return (
            <div
              key={v.key}
              ref={virtualizer.measureElement}
              data-index={v.index}
              className="card-row"
              style={{
                position: 'absolute',
                top: 0,
                left: 0,
                width: '100%',
                transform: `translateY(${v.start}px)`,
                gridTemplateColumns: `repeat(${columns}, minmax(0, 1fr))`,
              }}
            >
              {slice.map((r) => (
                <OppCard key={r.id} row={r} selected={r.id === selectedId} onOpen={() => onOpen(r.id)} />
              ))}
            </div>
          )
        })}
      </div>
      {rows.length === 0 && <div className="empty">No opportunities match the current filters.</div>}
    </div>
  )
}

function OppCard({ row: r, selected, onOpen }: { row: Row; selected: boolean; onOpen: () => void }) {
  return (
    <article
      className={`card ${selected ? 'selected' : ''} ${r.effCount === null ? 'unknown' : ''}`}
      onClick={onOpen}
      onKeyDown={(e) => {
        if (e.key === 'Enter') onOpen()
      }}
      tabIndex={0}
      aria-label={`${r.account_name}, ${r.effCount ?? 'unknown'} ${r.effType} lines`}
    >
      <header className="card-head">
        <div className="card-title">
          <h3>{r.account_name}</h3>
          <div className="card-sub">{r.opportunity_name}</div>
        </div>
        <LinesSummary row={r} />
      </header>

      <dl className="card-grid">
        <div>
          <dt>Owner</dt>
          <dd>{r.owner}</dd>
        </div>
        <div>
          <dt>Phone</dt>
          <dd>
            {r.phone_tel ? (
              <a href={`tel:${r.phone_tel}`} onClick={(e) => e.stopPropagation()}>
                {r.phone}
              </a>
            ) : (
              <span className="muted">{r.phone ?? 'none'}</span>
            )}
          </dd>
        </div>
        <div>
          <dt>Closed</dt>
          <dd>{formatDate(r.close_date)}</dd>
        </div>
        <div>
          <dt>Est. renewal</dt>
          <dd>{formatMonthKey(r.estimated_renewal_month)}</dd>
        </div>
        <div>
          <dt>Next step</dt>
          <dd>{r.next_step ?? <span className="muted">—</span>}</dd>
        </div>
        <div>
          <dt>Contract end</dt>
          <dd>
            {r.contract_end_hint ? (
              <span className={`hint-pill ${r.contract_end_confidence}`} title={r.contract_end_hint}>
                {r.contract_end_month ? formatMonthKey(r.contract_end_month) : r.contract_end_hint}
              </span>
            ) : (
              <span className="muted">—</span>
            )}
          </dd>
        </div>
      </dl>

      {r.additional_info && (
        <p className="card-info" title={r.additional_info}>
          {r.additional_info}
        </p>
      )}

      <footer className="card-foot">
        <StatusBadge status={r.status} />
        {r.followUp && <span className="followup">Follow-up {formatDate(r.followUp)}</span>}
        {r.notes && <span className="note-preview" title={r.notes}>📝 {r.notes}</span>}
        {r.line_match && (
          <span className="matched" title={`Matched ${r.line_match} in ${r.extraction_source === 'name' ? 'Opportunity Name' : r.extraction_source === 'additional_info' ? 'Additional Info' : 'no field'}`}>
            {r.line_match}
          </span>
        )}
      </footer>
    </article>
  )
}
