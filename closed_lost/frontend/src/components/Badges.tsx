import type { LineType, Row, Status } from '../types'

const STATUS_CLASS: Record<Status, string> = {
  'Not started': 'st-none',
  Called: 'st-called',
  'Left voicemail': 'st-vm',
  'Callback scheduled': 'st-callback',
  'Not interested': 'st-no',
  'Won back': 'st-won',
}

const STATUS_ICON: Record<Status, string> = {
  'Not started': '○',
  Called: '☎',
  'Left voicemail': '✉',
  'Callback scheduled': '⏰',
  'Not interested': '✕',
  'Won back': '★',
}

export function StatusBadge({ status }: { status: Status }) {
  return (
    <span className={`badge status ${STATUS_CLASS[status]}`} title={status}>
      <span aria-hidden="true" className="badge-icon">
        {STATUS_ICON[status]}
      </span>
      {status}
    </span>
  )
}

export function TypeBadge({ type, small }: { type: LineType; small?: boolean }) {
  return <span className={`badge type type-${type.toLowerCase()} ${small ? 'small' : ''}`}>{type}</span>
}

export function UnknownFlag({ compact }: { compact?: boolean }) {
  return (
    <span className="badge flag" title="The parser found no line count. Open the card and set it manually.">
      <span aria-hidden="true">⚠</span> {compact ? 'Unknown' : 'Count unknown — set it'}
    </span>
  )
}

/** "3 MP" / "Unknown" with override + flag markers. */
export function LinesSummary({ row, compact }: { row: Row; compact?: boolean }) {
  if (row.effCount === null) {
    return (
      <span className="lines-summary">
        <UnknownFlag compact={compact} />
        {row.effType !== 'Unknown' && <TypeBadge type={row.effType} small />}
        {row.overridden && <span className="badge override" title="Manually overridden">edited</span>}
      </span>
    )
  }
  return (
    <span className="lines-summary">
      <span className="lines-count">
        {row.effCount}
        <span className="lines-unit"> line{row.effCount === 1 ? '' : 's'}</span>
      </span>
      <TypeBadge type={row.effType} small />
      {row.overridden && <span className="badge override" title="Manually overridden">edited</span>}
    </span>
  )
}
