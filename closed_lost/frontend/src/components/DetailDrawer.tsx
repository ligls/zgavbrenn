import { useEffect, useState } from 'react'
import { bucketFor, formatDate, formatMonthKey } from '../lib/rows'
import type { EditInput, LineType, Row, Status } from '../types'
import { LINE_TYPES, STATUSES } from '../types'
import { TypeBadge, UnknownFlag } from './Badges'

interface Props {
  row: Row
  index: number
  total: number
  onClose: () => void
  onPrev: () => void
  onNext: () => void
  onSave: (id: string, input: EditInput) => Promise<void>
  onDeleteEdit: (id: string) => Promise<void>
}

interface FormState {
  countOverride: string
  typeOverride: '' | LineType
  status: Status
  notes: string
  followUp: string
}

function formFromRow(row: Row): FormState {
  return {
    countOverride: row.edit?.line_count_override === null || row.edit?.line_count_override === undefined ? '' : String(row.edit.line_count_override),
    typeOverride: (row.edit?.line_type_override as LineType | null) ?? '',
    status: row.status,
    notes: row.notes,
    followUp: row.followUp ?? '',
  }
}

export default function DetailDrawer({ row, index, total, onClose, onPrev, onNext, onSave, onDeleteEdit }: Props) {
  const [form, setForm] = useState<FormState>(() => formFromRow(row))
  const [saving, setSaving] = useState(false)
  const [savedAt, setSavedAt] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setForm(formFromRow(row))
    setError(null)
    setSavedAt(null)
  }, [row.id, row.edit?.updated_at]) // eslint-disable-line react-hooks/exhaustive-deps

  const dirty = JSON.stringify(form) !== JSON.stringify(formFromRow(row))

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null
      const typing = target && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.tagName === 'SELECT')
      if (e.key === 'Escape') {
        onClose()
      } else if (!typing && e.key === 'ArrowLeft') {
        onPrev()
      } else if (!typing && e.key === 'ArrowRight') {
        onNext()
      }
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onClose, onPrev, onNext])

  const toInput = (): EditInput | string => {
    let count: number | null = null
    if (form.countOverride.trim() !== '') {
      const n = Number(form.countOverride)
      if (!Number.isInteger(n) || n < 0) return 'Line count override must be a whole number.'
      count = n
    }
    return {
      line_count_override: count,
      line_type_override: form.typeOverride === '' ? null : form.typeOverride,
      status: form.status,
      notes: form.notes,
      follow_up_date: form.followUp || null,
    }
  }

  const save = async (then?: () => void) => {
    const input = toInput()
    if (typeof input === 'string') {
      setError(input)
      return
    }
    setSaving(true)
    setError(null)
    try {
      await onSave(row.id, input)
      setSavedAt(Date.now())
      then?.()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setSaving(false)
    }
  }

  const resetAll = async () => {
    if (!row.edit) return
    if (!window.confirm('Remove the saved status, notes, follow-up and overrides for this opportunity?')) return
    setSaving(true)
    try {
      await onDeleteEdit(row.id)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setSaving(false)
    }
  }

  const effCount = form.countOverride.trim() !== '' && Number.isInteger(Number(form.countOverride)) ? Number(form.countOverride) : row.line_count
  const effType = form.typeOverride || row.line_type

  return (
    <div className="drawer-backdrop" onClick={onClose}>
      <aside className="drawer" onClick={(e) => e.stopPropagation()} aria-label="Opportunity details">
        <header className="drawer-head">
          <div className="drawer-nav">
            <button type="button" onClick={onPrev} disabled={index <= 0} title="Previous (←)">
              ←
            </button>
            <span className="muted">
              {index + 1} of {total.toLocaleString('en-CA')}
            </span>
            <button type="button" onClick={onNext} disabled={index >= total - 1} title="Next (→)">
              →
            </button>
          </div>
          <button type="button" className="icon-btn" onClick={onClose} title="Close (Esc)" aria-label="Close">
            ✕
          </button>
        </header>

        <div className="drawer-body">
          <h2 className="drawer-title">{row.account_name}</h2>
          {row.account_name_repaired && (
            <div className="raw-note">
              Repaired from <code>{row.account_name_raw}</code>
            </div>
          )}
          <div className="drawer-opp">{row.opportunity_name}</div>
          {row.opportunity_name !== row.opportunity_name_raw && (
            <div className="raw-note">
              Raw: <code>{row.opportunity_name_raw}</code>
            </div>
          )}

          <section className="drawer-section">
            <h4>Source columns</h4>
            <dl className="kv">
              <dt>Opportunity Owner</dt>
              <dd>{row.owner}</dd>
              <dt>Account Name</dt>
              <dd>{row.account_name}</dd>
              <dt>Phone</dt>
              <dd>{row.phone_tel ? <a href={`tel:${row.phone_tel}`}>{row.phone}</a> : <span className="muted">{row.phone ?? 'none'}</span>}</dd>
              <dt>Opportunity Name</dt>
              <dd>{row.opportunity_name}</dd>
              <dt>Close Date</dt>
              <dd>
                {formatDate(row.close_date)} <span className="muted">({row.close_month_label})</span>
              </dd>
              <dt>Next Step</dt>
              <dd>{row.next_step ?? <span className="muted">empty</span>}</dd>
              <dt>Additional Info</dt>
              <dd className="prewrap">{row.additional_info ?? <span className="muted">empty</span>}</dd>
            </dl>
          </section>

          <section className="drawer-section">
            <h4>Derived</h4>
            <dl className="kv">
              <dt>Line count</dt>
              <dd>
                {row.line_count === null ? <UnknownFlag compact /> : `${row.line_count} (parsed)`}
                {row.mp_count !== null || row.wls_count !== null ? (
                  <span className="muted">
                    {' '}
                    · MP {row.mp_count ?? '—'} · WLS {row.wls_count ?? '—'}
                  </span>
                ) : null}
              </dd>
              <dt>Line type</dt>
              <dd>
                <TypeBadge type={row.line_type} />
                {row.types_mentioned.length > 1 && (
                  <span className="muted"> mentions {row.types_mentioned.join(' + ')}</span>
                )}
              </dd>
              <dt>Bucket</dt>
              <dd>
                {bucketFor(effCount)}
                {bucketFor(effCount) !== row.line_bucket && <span className="muted"> (parsed: {row.line_bucket})</span>}
              </dd>
              <dt>Matched text</dt>
              <dd>
                {row.line_match ? (
                  <>
                    <code>{row.line_match}</code>{' '}
                    <span className="muted">
                      from {row.extraction_source === 'name' ? 'Opportunity Name' : row.extraction_source === 'additional_info' ? 'Additional Info' : 'no field (type only)'}
                    </span>
                  </>
                ) : (
                  <span className="muted">nothing matched</span>
                )}
              </dd>
              <dt>Estimated renewal</dt>
              <dd>
                {formatDate(row.estimated_renewal_date)} <span className="muted">(close + 24 months)</span>
              </dd>
              <dt>Contract-end hint</dt>
              <dd>
                {row.contract_end_hint ? (
                  <>
                    <span className={`hint-pill ${row.contract_end_confidence}`}>
                      {row.contract_end_month ? formatMonthKey(row.contract_end_month) : 'no month'}
                    </span>{' '}
                    <q>{row.contract_end_hint}</q>
                    <span className="muted"> · {row.contract_end_confidence} confidence</span>
                  </>
                ) : (
                  <span className="muted">none found</span>
                )}
              </dd>
              <dt>Row</dt>
              <dd className="muted">
                xlsx row {row.row_number} · hash {row.id}
              </dd>
            </dl>
          </section>

          <section className="drawer-section edit">
            <h4>Your work</h4>
            <div className="form-grid">
              <label>
                <span>Line count override</span>
                <input
                  type="number"
                  min={0}
                  inputMode="numeric"
                  placeholder={row.line_count === null ? 'unknown' : `parsed: ${row.line_count}`}
                  value={form.countOverride}
                  onChange={(e) => setForm({ ...form, countOverride: e.target.value })}
                />
              </label>
              <label>
                <span>Line type override</span>
                <select value={form.typeOverride} onChange={(e) => setForm({ ...form, typeOverride: e.target.value as '' | LineType })}>
                  <option value="">parsed: {row.line_type}</option>
                  {LINE_TYPES.map((t) => (
                    <option key={t} value={t}>
                      {t}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                <span>Status</span>
                <select value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value as Status })}>
                  {STATUSES.map((s) => (
                    <option key={s} value={s}>
                      {s}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                <span>Follow-up date</span>
                <input type="date" value={form.followUp} onChange={(e) => setForm({ ...form, followUp: e.target.value })} />
              </label>
              <label className="span2">
                <span>Notes</span>
                <textarea rows={5} value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} placeholder="Call notes, contact name, pricing…" />
              </label>
            </div>
            <div className="effective">
              Effective: <strong>{effCount === null ? 'Unknown' : `${effCount} line${effCount === 1 ? '' : 's'}`}</strong> · <TypeBadge type={effType} small /> · bucket {bucketFor(effCount)}
            </div>
            {error && <div className="error">{error}</div>}
            <div className="form-actions">
              <button type="button" className="primary" disabled={saving || !dirty} onClick={() => void save()}>
                {saving ? 'Saving…' : 'Save'}
              </button>
              <button type="button" disabled={saving || index >= total - 1} onClick={() => void save(onNext)} title="Save and open the next opportunity">
                Save &amp; next →
              </button>
              {row.edit && (
                <button type="button" className="danger link" disabled={saving} onClick={() => void resetAll()}>
                  Remove saved edits
                </button>
              )}
              {savedAt && !dirty && <span className="saved">Saved ✓</span>}
              {row.edit?.updated_at && <span className="muted small">last saved {row.edit.updated_at.replace('T', ' ')}</span>}
            </div>
          </section>
        </div>
      </aside>
    </div>
  )
}
