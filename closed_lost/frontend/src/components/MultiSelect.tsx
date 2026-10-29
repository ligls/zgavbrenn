import { useEffect, useMemo, useRef, useState } from 'react'
import { normalize } from '../lib/normalize'

export interface Option {
  value: string
  label: string
  count: number
}

interface Props {
  label: string
  options: Option[]
  selected: string[]
  onChange: (next: string[]) => void
  placeholder?: string
  /** Options with a zero count are hidden unless selected. */
  hideZero?: boolean
}

/** Searchable multi-select used for the ~650 Opportunity Owners. */
export default function MultiSelect({ label, options, selected, onChange, placeholder, hideZero = true }: Props) {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const rootRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (!open) return
    const onDoc = (e: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) setOpen(false)
    }
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', onDoc)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDoc)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  const selectedSet = useMemo(() => new Set(selected), [selected])
  const visible = useMemo(() => {
    const q = normalize(query)
    const list = options.filter((o) => {
      if (selectedSet.has(o.value)) return true
      if (hideZero && o.count === 0) return false
      return q === '' || normalize(o.label).includes(q)
    })
    list.sort((a, b) => {
      const sa = selectedSet.has(a.value) ? 0 : 1
      const sb = selectedSet.has(b.value) ? 0 : 1
      if (sa !== sb) return sa - sb
      if (b.count !== a.count) return b.count - a.count
      return a.label.localeCompare(b.label)
    })
    return list.slice(0, 400)
  }, [options, query, selectedSet, hideZero])

  const toggle = (value: string) => {
    if (selectedSet.has(value)) onChange(selected.filter((v) => v !== value))
    else onChange([...selected, value])
  }

  return (
    <div className="multiselect" ref={rootRef}>
      <button
        type="button"
        className={`ms-trigger ${selected.length ? 'has-value' : ''}`}
        onClick={() => {
          setOpen((o) => !o)
          setTimeout(() => inputRef.current?.focus(), 0)
        }}
        aria-haspopup="listbox"
        aria-expanded={open}
      >
        <span className="ms-label">
          {selected.length === 0 ? (placeholder ?? `All ${label.toLowerCase()}`) : selected.length === 1 ? selected[0] : `${selected.length} ${label.toLowerCase()} selected`}
        </span>
        <span className="ms-caret" aria-hidden="true">
          ▾
        </span>
      </button>
      {open && (
        <div className="ms-popover" role="listbox" aria-multiselectable="true" aria-label={label}>
          <div className="ms-search">
            <input
              ref={inputRef}
              type="search"
              value={query}
              placeholder={`Search ${label.toLowerCase()}…`}
              onChange={(e) => setQuery(e.target.value)}
            />
            {selected.length > 0 && (
              <button type="button" className="link" onClick={() => onChange([])}>
                Clear
              </button>
            )}
          </div>
          <div className="ms-list">
            {visible.length === 0 && <div className="ms-empty">No match</div>}
            {visible.map((o) => (
              <label key={o.value} className={`ms-item ${selectedSet.has(o.value) ? 'selected' : ''}`}>
                <input type="checkbox" checked={selectedSet.has(o.value)} onChange={() => toggle(o.value)} />
                <span className="ms-item-label">{o.label}</span>
                <span className="ms-count">{o.count.toLocaleString('en-CA')}</span>
              </label>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
