import { useCallback, useEffect, useMemo, useState } from 'react'
import Dashboard from './components/Dashboard'
import DetailDrawer from './components/DetailDrawer'
import FiltersPanel from './components/FiltersPanel'
import OppCards from './components/OppCards'
import OppTable from './components/OppTable'
import EditsMenu from './components/EditsMenu'
import { downloadBlob } from './lib/api'
import { exportFilename, rowsToCsv, rowsToXlsx } from './lib/export'
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
import { createStore, DeclinedDownload, type StoreInfo } from './lib/store'
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
  const [store] = useState(() => createStore())
  const [dataset, setDataset] = useState<Dataset | null>(null)
  const [edits, setEdits] = useState<Record<string, Edit>>({})
  const [editsReady, setEditsReady] = useState(false)
  const [storeInfo, setStoreInfo] = useState<StoreInfo>(store.info)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [names, setNames] = useState<Record<string, string>>({})

  const [filters, setFilters] = useState<Filters>(() => loadPref('cl.filters', EMPTY_FILTERS))
  const [sort, setSort] = useState<Sort>(() => loadPref('cl.sort', { key: 'close_date', dir: 'asc' } as Sort))
  const [layout, setLayout] = useState<Layout>(() => loadScalar('cl.layout', 'cards', ['cards', 'table'] as const))
  const [theme, setTheme] = useState<Theme>(() => loadScalar('cl.theme', 'auto', ['auto', 'light', 'dark'] as const))
  const [showDashboard, setShowDashboard] = useState<boolean>(() => loadScalar('cl.dash', 'on', ['on', 'off'] as const) === 'on')
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [toast, setToast] = useState<string | null>(null)

  // Load the dataset first so the page renders at once; edits (and, in a shared
  // artifact, the live subscription) light up when the store answers.
  useEffect(() => {
    let cancelled = false
    let unsubscribe: (() => void) | null = null
    store.onInfoChange = (info) => !cancelled && setStoreInfo(info)
    store
      .loadDataset()
      .then((ds) => {
        if (cancelled) return
        setDataset(ds)
        return store.loadEdits().then((ed) => {
          if (cancelled) return
          setEdits(ed)
          setEditsReady(true)
          setStoreInfo(store.info)
          if (store.subscribe) {
            unsubscribe = store.subscribe(
              (next) => !cancelled && setEdits(next),
              (message) => !cancelled && setToast(message),
            )
          }
        })
      })
      .catch((e: Error) => !cancelled && setLoadError(e.message))
    return () => {
      cancelled = true
      store.onInfoChange = null
      unsubscribe?.()
    }
  }, [store])

  useEffect(() => savePref('cl.filters', filters), [filters])
  useEffect(() => savePref('cl.sort', sort), [sort])
  useEffect(() => savePref('cl.layout', layout), [layout])
  useEffect(() => savePref('cl.dash', showDashboard ? 'on' : 'off'), [showDashboard])
  useEffect(() => {
    if (store.mode === 'artifact') return // the claude.ai viewer owns the theme
    savePref('cl.theme', theme)
    if (theme === 'auto') document.documentElement.removeAttribute('data-theme')
    else document.documentElement.setAttribute('data-theme', theme)
  }, [theme, store.mode])

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

  // Resolve "saved by" for the open card (shared artifact only).
  const savedById = selectedRow?.edit?.updated_by ?? null
  useEffect(() => {
    if (!savedById || !store.profiles || names[savedById]) return
    let cancelled = false
    store.profiles([savedById]).then((res) => !cancelled && setNames((prev) => ({ ...prev, ...res })))
    return () => {
      cancelled = true
    }
  }, [savedById, store, names])

  const onSave = useCallback(
    async (id: string, input: EditInput) => {
      const saved = await store.saveEdit(id, input)
      setEdits((prev) => ({ ...prev, [id]: saved }))
    },
    [store],
  )

  const onDeleteEdit = useCallback(
    async (id: string) => {
      await store.deleteEdit(id)
      setEdits((prev) => {
        const next = { ...prev }
        delete next[id]
        return next
      })
    },
    [store],
  )

  const toggleSortKey = (key: SortKey) => {
    setSort((s) => (s.key === key ? { key, dir: s.dir === 'asc' ? 'desc' : 'asc' } : { key, dir: key === 'line_count' ? 'desc' : 'asc' }))
  }

  const toggleIn = (list: string[], value: string) => (list.includes(value) ? list.filter((v) => v !== value) : [...list, value])

  const deliver = async (blob: Blob, filename: string, label: string) => {
    try {
      if (store.download) await store.download(filename, blob)
      else downloadBlob(blob, filename)
      setToast(`Exported ${formatNumber(filtered.length)} rows to ${label}`)
    } catch (e) {
      if (e instanceof DeclinedDownload) return
      setToast(`Export failed: ${(e as Error).message}`)
    }
  }
  const exportCsv = () => void deliver(new Blob([rowsToCsv(filtered)], { type: 'text/csv;charset=utf-8' }), exportFilename('csv'), 'CSV')
  const exportExcel = () => {
    let blob: Blob
    try {
      blob = rowsToXlsx(filtered)
    } catch (e) {
      setToast(`Export failed: ${(e as Error).message}`)
      return
    }
    void deliver(blob, exportFilename('xlsx'), 'Excel')
  }
  const editCount = Object.keys(edits).length

  if (loadError) {
    return (
      <div className="boot error-screen">
        <h1>Closed Lost Renewals</h1>
        <p>Could not load the data: {loadError}</p>
        {store.mode === 'server' ? (
          <>
            <p>Run the importer first, then start the server:</p>
            <pre>make import{'\n'}make run</pre>
          </>
        ) : (
          <p>This page seems to be missing its embedded data. Rebuild it with <code>make standalone</code>.</p>
        )}
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
            {store.mode !== 'server' && ` · imported ${dataset.meta.imported_at.replace('T', ' ')}`}
            {dataset.meta.excluded_count
              ? ` · ${formatNumber(dataset.meta.excluded_count)} ${dataset.meta.excluded_label ?? `"${dataset.meta.excluded_name_pattern}"`} opportunities excluded`
              : ''}
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
          {store.mode === 'artifact' && storeInfo.shared && (
            <span className={`shared-pill ${storeInfo.readOnly ? 'readonly' : ''}`} title={storeInfo.readOnly ? storeInfo.message ?? '' : 'Statuses, notes and overrides are shared live with everyone who has this page'}>
              <span className="shared-dot" aria-hidden="true">
                ●
              </span>
              {storeInfo.readOnly ? 'View only' : 'Shared'} · {editsReady ? `${formatNumber(editCount)} edit${editCount === 1 ? '' : 's'}` : 'connecting…'}
            </span>
          )}
          {store.local && editsReady && <EditsMenu store={store.local} edits={edits} onReplace={setEdits} onToast={setToast} />}
          <div className="export">
            <button type="button" onClick={exportCsv} title="Export the current filtered view (with your status and notes)">
              CSV
            </button>
            <button type="button" onClick={exportExcel} title="Export the current filtered view (with your status and notes)">
              Excel
            </button>
          </div>
          <button type="button" className="icon-btn" onClick={() => setShowDashboard((s) => !s)} title={showDashboard ? 'Hide dashboard' : 'Show dashboard'} aria-pressed={showDashboard}>
            📊
          </button>
          {store.mode !== 'artifact' && (
            <button
              type="button"
              className="icon-btn"
              onClick={() => setTheme(theme === 'auto' ? 'dark' : theme === 'dark' ? 'light' : 'auto')}
              title={`Theme: ${theme} (click to change)`}
            >
              {theme === 'dark' ? '🌙' : theme === 'light' ? '☀️' : '◐'}
            </button>
          )}
        </div>
      </header>

      {storeInfo.message && (
        <div className={`banner ${storeInfo.readOnly ? 'warn' : ''}`} role="status">
          {storeInfo.message}
        </div>
      )}

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
          readOnly={storeInfo.readOnly}
          savedBy={savedById ? names[savedById] : undefined}
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
