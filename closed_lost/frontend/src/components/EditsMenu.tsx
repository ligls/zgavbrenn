import { useEffect, useRef, useState } from 'react'
import { downloadBlob } from '../lib/api'
import { editsToFile, LocalStore, mergeEdits, parseEditsFile } from '../lib/store'
import type { Edit } from '../types'

interface Props {
  store: LocalStore
  edits: Record<string, Edit>
  onReplace: (edits: Record<string, Edit>) => void
  onToast: (message: string) => void
}

/**
 * Standalone-file persistence controls: how many edits exist, save them to a
 * JSON file, load (merge) a file, and optionally keep a file auto-saved.
 */
export default function EditsMenu({ store, edits, onReplace, onToast }: Props) {
  const [open, setOpen] = useState(false)
  const [autoFile, setAutoFile] = useState<string | null>(store.autoSaveFile)
  const [error, setError] = useState<string | null>(null)
  const rootRef = useRef<HTMLDivElement>(null)
  const fileRef = useRef<HTMLInputElement>(null)
  const count = Object.keys(edits).length

  useEffect(() => {
    store.onPersist = (info) => {
      setAutoFile(info.file)
      setError(info.error)
    }
    return () => {
      store.onPersist = null
    }
  }, [store])

  useEffect(() => {
    if (!open) return
    const onDoc = (e: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [open])

  const saveToFile = () => {
    const payload = editsToFile(edits, store.sourceFile)
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' })
    const stamp = payload.exported_at.slice(0, 10)
    downloadBlob(blob, `closed_lost_edits_${stamp}.json`)
    onToast(`Saved ${count} edit${count === 1 ? '' : 's'} to a JSON file`)
    setOpen(false)
  }

  const loadFromFile = async (file: File) => {
    try {
      const incoming = parseEditsFile(await file.text())
      const merged = mergeEdits(edits, incoming)
      onReplace(store.replaceAll(merged))
      onToast(`Loaded ${incoming.length} edit${incoming.length === 1 ? '' : 's'} from ${file.name} (newest wins)`)
    } catch (e) {
      onToast(`Could not load ${file.name}: ${(e as Error).message}`)
    }
    setOpen(false)
  }

  const startAutoSave = async () => {
    try {
      const name = await store.chooseAutoSaveFile()
      onToast(`Auto-saving edits to ${name}`)
    } catch (e) {
      if ((e as Error).name !== 'AbortError') onToast(`Auto-save not available: ${(e as Error).message}`)
    }
    setOpen(false)
  }

  return (
    <div className="edits-menu" ref={rootRef}>
      <button type="button" className={`edits-trigger ${error ? 'has-error' : ''}`} onClick={() => setOpen((o) => !o)} aria-haspopup="menu" aria-expanded={open}>
        <span className="edits-dot" aria-hidden="true">
          {autoFile ? '●' : '○'}
        </span>
        {count} edit{count === 1 ? '' : 's'}
        {autoFile && <span className="muted"> · auto-saved</span>}
        <span className="ms-caret" aria-hidden="true">
          ▾
        </span>
      </button>
      {open && (
        <div className="edits-popover" role="menu">
          <div className="edits-note">
            Your statuses, notes and overrides are stored in this browser (local storage). Save them to a file
            regularly to keep them safe or move them to another computer.
          </div>
          <button type="button" role="menuitem" onClick={saveToFile} disabled={count === 0}>
            Save edits to a JSON file…
          </button>
          <button type="button" role="menuitem" onClick={() => fileRef.current?.click()}>
            Load edits from a JSON file…
          </button>
          <input
            ref={fileRef}
            type="file"
            accept="application/json,.json"
            hidden
            onChange={(e) => {
              const f = e.target.files?.[0]
              if (f) void loadFromFile(f)
              e.target.value = ''
            }}
          />
          {LocalStore.supportsAutoSave &&
            (autoFile ? (
              <button type="button" role="menuitem" onClick={() => { store.stopAutoSave(); setOpen(false) }}>
                Stop auto-saving to {autoFile}
              </button>
            ) : (
              <button type="button" role="menuitem" onClick={() => void startAutoSave()}>
                Auto-save to a file (this session)…
              </button>
            ))}
          {error && <div className="edits-error">Last file write failed: {error}</div>}
        </div>
      )}
    </div>
  )
}
