import { useCallback, useEffect, useMemo, useState } from 'react'
import Dashboard from './components/Dashboard'
import DetailDrawer from './components/DetailDrawer'
import FiltersPanel from './components/FiltersPanel'
import OppCards from './components/OppCards'
import OppTable from './components/OppTable'
import { deleteEdit, downloadBlob, exportXlsx, fetchDataset, fetchEdits, saveEdit } from './lib/api'
import { EXPORT_COLUMNS, exportFilename, rowsToCsv } from './lib/export'
import {
  applyFilters,
  EMPTY_FILTERS,
  isFilterActive,
  SORT_LABELS,
  sortRows,
  type Filters,
  type Sort,
  type SortKey,
} from './lib/filters'
import { buildRow, formatNumber } from './lib/rows'
import type { Dataset, Edit, EditInput, LineType, Row } from './types'

type Layout = 'cards' | 'table'
type Theme = 'auto' | 'light' | 'dark'

function loadPref<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key)
    return raw ? ({ ...fallback, ...(JSON.parse(raw) as object) } as T) : fallback
  } catch {
    return fallback
  }
}
function loadScalar<T extends string>(key: string, fallback: T, allowed: readonly T[]): T {
  try {
    const raw = localStorage.getItem(key) as T | null
    return raw && allowed.includes(raw) ? raw : fallback
  } catch {
    return fallback
  }
}
function savePref(key: string, value: unknown) {
  try {
    localStorage.setItem(key, typeof value === 'string' ? value : JSON.stringify(value))
  } catch {
    /* private mode etc. */
  }
}

export default function App() {
  const [dataset, setDataset] = useState<Dataset | null>(null)
  const [edits, setEdits] = useState<Record<string, Edit>>({})
  const [loadError, setLoadError] = useState<string | null>(null)

  const [filters, setFilters] = useState<Filters>(() => loadPref('cl.filters', EMPTY_FILTERS))
  const [sort, setSort] = useState<Sort>(() => loadPref('cl.sort', { key: 'close_date', dir: 'asc' } as Sort))
  const [layout, setLayout] = useState<Layout>(() => loadScalar('cl.layout', 'cards', ['cards', 'table'] as const))
  const [theme, setTheme] = useState<Theme>(() => loadScalar('cl.theme', 'auto', ['auto', 'light', 'dark'] as const))
  const [showDashboard, setShowDashboard] = useState<boolean>(() => loadScalar('cl.dash', 'on', ['on', 'off'] as const) === 'on')
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [toast, setToast] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    Promise.all([fetchDataset(), fetchEdits()])
      .then(([ds, ed]) => {
        if (cancelled) return
        setDataset(ds)
        setEdits(ed)
      })
      .catch((e: Error) => !cancelled && setLoadError(e.message))
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => savePref('cl.filters', filters), [filters])
  useEffect(() => savePref('cl.sort', sort), [sort])
  useEffect(() => savePref('cl.layout', layout), [layout])
  useEffect(() => savePref('cl.dash', showDashboard ? 'on' : 'off'), [showDashboard])
  useEffect(() => {
    savePref('cl.theme', theme)
    if (theme === 'auto') document.documentElement.removeAttribute('data-theme')
    else document.documentElement.setAttribute('data-theme', theme)
  }, [theme])

  useEffect(() => {
    if (!toast) return
    const t = setTimeout(() => setToast(null), 3500)
    return () => clearTimeout(t)
  }, [toast])

  const rows: Row[] = useMemo(() => {
    if (!dataset) return []
    return dataset.opportunities.map((o) => buildRow(o, edits[o.id] ?? null))
  }, [dataset, edits])

  const filtered = useMemo(() => sortRows(applyFilters(rows, filters), sort), [rows, filters, sort])
  const total = dataset?.meta.row_count ?? rows.length

  const selectedIndex = selectedId ? filtered.findIndex((r) => r.id === selectedId) : -1
  const selectedRow = selectedIndex >= 0 ? filtered[selectedIndex] : (rows.find((r) => r.id === selectedId) ?? null)

  const onSave = useCallback(async (id: string, input: EditInput) => {
    const saved = await saveEdit(id, input)
    setEdits((prev) => ({ ...prev, [id]: saved }))
  }, [])

  const onDeleteEdit = useCallback(async (id: string) => {
    await deleteEdit(id)
    setEdits((prev) => {
      const next = { ...prev }
      delete next[id]
      return next
    })
  }, [])

  const toggleSortKey = (key: SortKey) => {
    setSort((s) => (s.key === key ? { key, dir: s.dir === 'asc' ? 'desc' : 'asc' } : { key, dir: key === 'line_count' ? 'desc' : 'asc' }))
  }

  const toggleIn = (list: string[], value: string) => (list.includes(value) ? list.filter((v) => v !== value) : [...list, value])

  const exportCsv = () => {
    const blob = new Blob([rowsToCsv(filtered)], { type: 'text/csv;charset=utf-8' })
    downloadBlob(blob, exportFilename('csv'))
    setToast(`Exported ${formatNumber(filtered.length)} rows to CSV`)
  }
  const exportExcel = async () => {
    try {
      const blob = await exportXlsx(
        filtered.map((r) => r.id),
        EXPORT_COLUMNS,
      )
      downloadBlob(blob, exportFilename('xlsx'))
      setToast(`Exported ${formatNumber(filtered.length)} rows to Excel`)
    } catch (e) {
      setToast(`Export failed: ${(e as Error).message}`)
    }
  }

  if (loadError) {
    return (
      <div className="boot error-screen">
        <h1>Closed Lost Renewals</h1>
        <p>Could not load the data: {loadError}</p>
        <p>
          Run the importer first, then start the server:
        </p>
        <pre>
          make import{'\n'}make run
        </pre>
      </div>
    )
  }
  if (!dataset) {
    return (
      <div className="boot">
        <h1>Closed Lost Renewals</h1>
        <p>Loading…</p>
      </div>
    )
  }

  return (
    <div className={`app ${selectedRow ? 'has-drawer' : ''}`}>
      <header className="topbar">
        <div className="brand">
          <h1>Closed Lost Renewals</h1>
          <span className="brand-sub">
            Q4 2024 Closed Lost · renewals due Q4 2026 · {dataset.meta.source_file}
          </span>
        </div>
        <div className="count">
          <strong>{formatNumber(filtered.length)}</strong> of {formatNumber(total)}
          {isFilterActive(filters) && (
            <button type="button" className="link" onClick={() => setFilters({ ...EMPTY_FILTERS })}>
              Clear filters
            </button>
          )}
        </div>
        <div className="toolbar">
          <label className="sort">
            <span className="sr-only">Sort by</span>
            <select value={sort.key} onChange={(e) => setSort({ ...sort, key: e.target.value as SortKey })}>
              {(Object.keys(SORT_LABELS) as SortKey[]).map((k) => (
                <option key={k} value={k}>
                  Sort: {SORT_LABELS[k]}
                </option>
              ))}
            </select>
            <button
              type="button"
              className="icon-btn"
              title={sort.dir === 'asc' ? 'Ascending — click for descending' : 'Descending — click for ascending'}
              onClick={() => setSort({ ...sort, dir: sort.dir === 'asc' ? 'desc' : 'asc' })}
            >
              {sort.dir === 'asc' ? '↑' : '↓'}
            </button>
          </label>
          <div className="segmented" role="radiogroup" aria-label="Layout">
            <button type="button" role="radio" aria-checked={layout === 'cards'} className={layout === 'cards' ? 'on' : ''} onClick={() => setLayout('cards')}>
              Cards
            </button>
            <button type="button" role="radio" aria-checked={layout === 'table'} className={layout === 'table' ? 'on' : ''} onClick={() => setLayout('table')}>
              Table
            </button>
          </div>
          <div className="export">
            <button type="button" onClick={exportCsv} title="Export the current filtered view (with your status and notes)">
              CSV
            </button>
            <button type="button" onClick={() => void exportExcel()} title="Export the current filtered view (with your status and notes)">
              Excel
            </button>
          </div>
          <button type="button" className="icon-btn" onClick={() => setShowDashboard((s) => !s)} title={showDashboard ? 'Hide dashboard' : 'Show dashboard'} aria-pressed={showDashboard}>
            📊
          </button>
          <button
            type="button"
            className="icon-btn"
            onClick={() => setTheme(theme === 'auto' ? 'dark' : theme === 'dark' ? 'light' : 'auto')}
            title={`Theme: ${theme} (click to change)`}
          >
            {theme === 'dark' ? '🌙' : theme === 'light' ? '☀️' : '◐'}
          </button>
        </div>
      </header>

      {showDashboard && (
        <Dashboard
          rows={rows}
          filtered={filtered}
          filters={filters}
          total={total}
          onToggleBucket={(b) => setFilters({ ...filters, buckets: toggleIn(filters.buckets, b) })}
          onToggleType={(t: LineType) => setFilters({ ...filters, types: toggleIn(filters.types, t) })}
          onToggleCloseMonth={(m) => setFilters({ ...filters, closeMonths: toggleIn(filters.closeMonths, m) })}
        />
      )}

      <div className="main">
        <FiltersPanel rows={rows} filters={filters} onChange={setFilters} />
        <section className="results" aria-label="Opportunities">
          {layout === 'table' ? (
            <OppTable rows={filtered} sort={sort} onSort={toggleSortKey} onOpen={setSelectedId} selectedId={selectedId} />
          ) : (
            <OppCards rows={filtered} onOpen={setSelectedId} selectedId={selectedId} />
          )}
        </section>
      </div>

      {selectedRow && (
        <DetailDrawer
          row={selectedRow}
          index={Math.max(0, selectedIndex)}
          total={filtered.length}
          onClose={() => setSelectedId(null)}
          onPrev={() => selectedIndex > 0 && setSelectedId(filtered[selectedIndex - 1].id)}
          onNext={() => selectedIndex >= 0 && selectedIndex < filtered.length - 1 && setSelectedId(filtered[selectedIndex + 1].id)}
          onSave={onSave}
          onDeleteEdit={onDeleteEdit}
        />
      )}

      {toast && (
        <div className="toast" role="status">
          {toast}
        </div>
      )}
    </div>
  )
}
