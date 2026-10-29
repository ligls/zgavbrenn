import { gunzipSync, strFromU8 } from 'fflate'
import type { Dataset, Edit, EditInput } from '../types'
import { deleteEdit as apiDeleteEdit, fetchDataset, fetchEdits, saveEdit as apiSaveEdit } from './api'

/**
 * Where the data and your edits live.
 *
 * - ServerStore: the Flask app (data/opportunities.json + SQLite edits).
 * - LocalStore: the single-file build. The dataset is embedded in the HTML
 *   (gzip + base64 in <script id="cl-data">), edits are kept in the browser's
 *   localStorage and can be saved to / loaded from a JSON file, or auto-saved
 *   to a file picked once per session (Chrome/Edge File System Access API).
 */
export interface Store {
  readonly mode: 'server' | 'standalone'
  loadDataset(): Promise<Dataset>
  loadEdits(): Promise<Record<string, Edit>>
  saveEdit(id: string, input: EditInput): Promise<Edit>
  deleteEdit(id: string): Promise<void>
}

export interface EditsFile {
  format: 'closed-lost-edits'
  version: 1
  exported_at: string
  source_file?: string
  edits: Edit[]
}

const LS_EDITS_KEY = 'cl.edits.v1'
const DATA_ELEMENT_ID = 'cl-data'

// ---------------------------------------------------------------- helpers

function nowIso(): string {
  return new Date().toISOString().slice(0, 19)
}

function readEmbedded(): { dataset: Dataset; edits: Edit[] } | null {
  const el = document.getElementById(DATA_ELEMENT_ID)
  const b64 = el?.textContent?.trim()
  if (!b64) return null
  const bin = atob(b64)
  const bytes = new Uint8Array(bin.length)
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i)
  const json = strFromU8(gunzipSync(bytes))
  const payload = JSON.parse(json) as Dataset & { initial_edits?: Edit[] }
  return { dataset: { meta: payload.meta, opportunities: payload.opportunities }, edits: payload.initial_edits ?? [] }
}

export function isStandalone(): boolean {
  const el = document.getElementById(DATA_ELEMENT_ID)
  return !!el && (el.textContent?.trim().length ?? 0) > 0
}

/** Keep the edit with the latest updated_at for each row. */
export function mergeEdits(...sources: Array<Record<string, Edit> | Edit[] | null | undefined>): Record<string, Edit> {
  const out: Record<string, Edit> = {}
  for (const src of sources) {
    if (!src) continue
    const list = Array.isArray(src) ? src : Object.values(src)
    for (const e of list) {
      if (!e || typeof e.row_hash !== 'string') continue
      const prev = out[e.row_hash]
      if (!prev || (e.updated_at ?? '') >= (prev.updated_at ?? '')) out[e.row_hash] = e
    }
  }
  return out
}

export function parseEditsFile(text: string): Edit[] {
  const parsed = JSON.parse(text) as unknown
  if (Array.isArray(parsed)) return parsed as Edit[]
  if (parsed && typeof parsed === 'object') {
    const obj = parsed as Partial<EditsFile> & Record<string, unknown>
    if (Array.isArray(obj.edits)) return obj.edits as Edit[]
    // a plain {row_hash: edit} map
    return Object.values(obj).filter((v): v is Edit => !!v && typeof v === 'object' && 'row_hash' in (v as object))
  }
  throw new Error('Not an edits file')
}

export function editsToFile(edits: Record<string, Edit>, sourceFile?: string): EditsFile {
  return {
    format: 'closed-lost-edits',
    version: 1,
    exported_at: nowIso(),
    source_file: sourceFile,
    edits: Object.values(edits).sort((a, b) => a.row_hash.localeCompare(b.row_hash)),
  }
}

// ---------------------------------------------------------------- server

class ServerStore implements Store {
  readonly mode = 'server' as const
  loadDataset() {
    return fetchDataset()
  }
  loadEdits() {
    return fetchEdits()
  }
  saveEdit(id: string, input: EditInput) {
    return apiSaveEdit(id, input)
  }
  deleteEdit(id: string) {
    return apiDeleteEdit(id)
  }
}

// ---------------------------------------------------------------- standalone

type FileHandle = {
  name: string
  createWritable(): Promise<{ write(data: Blob | string): Promise<void>; close(): Promise<void> }>
  queryPermission?(opts: { mode: 'readwrite' }): Promise<'granted' | 'denied' | 'prompt'>
  requestPermission?(opts: { mode: 'readwrite' }): Promise<'granted' | 'denied' | 'prompt'>
}
type SaveFilePicker = (opts: {
  suggestedName?: string
  types?: Array<{ description: string; accept: Record<string, string[]> }>
}) => Promise<FileHandle>

export class LocalStore implements Store {
  readonly mode = 'standalone' as const
  private embedded = readEmbedded()
  private edits: Record<string, Edit> = {}
  private fileHandle: FileHandle | null = null
  private writeTimer: number | null = null
  /** Called after every persist so the UI can show the state. */
  onPersist: ((info: { count: number; file: string | null; error: string | null }) => void) | null = null

  get sourceFile(): string | undefined {
    return this.embedded?.dataset.meta.source_file
  }

  async loadDataset(): Promise<Dataset> {
    if (!this.embedded) throw new Error('No embedded dataset found in this file.')
    return this.embedded.dataset
  }

  async loadEdits(): Promise<Record<string, Edit>> {
    let local: Record<string, Edit> | null = null
    try {
      const raw = localStorage.getItem(LS_EDITS_KEY)
      local = raw ? (JSON.parse(raw) as Record<string, Edit>) : null
    } catch {
      local = null
    }
    this.edits = mergeEdits(this.embedded?.edits ?? [], local)
    this.persist()
    return { ...this.edits }
  }

  async saveEdit(id: string, input: EditInput): Promise<Edit> {
    const edit: Edit = { row_hash: id, ...input, updated_at: nowIso() }
    this.edits[id] = edit
    this.persist()
    return edit
  }

  async deleteEdit(id: string): Promise<void> {
    delete this.edits[id]
    this.persist()
  }

  /** Replace every edit (after loading a file). */
  replaceAll(edits: Record<string, Edit>): Record<string, Edit> {
    this.edits = { ...edits }
    this.persist()
    return { ...this.edits }
  }

  currentEdits(): Record<string, Edit> {
    return { ...this.edits }
  }

  // ----- files -----------------------------------------------------------

  static get supportsAutoSave(): boolean {
    return typeof (window as unknown as { showSaveFilePicker?: unknown }).showSaveFilePicker === 'function'
  }

  get autoSaveFile(): string | null {
    return this.fileHandle?.name ?? null
  }

  /** Ask for a file once; afterwards every edit is written to it. */
  async chooseAutoSaveFile(): Promise<string> {
    const picker = (window as unknown as { showSaveFilePicker: SaveFilePicker }).showSaveFilePicker
    const handle = await picker({
      suggestedName: 'closed_lost_edits.json',
      types: [{ description: 'Closed Lost edits (JSON)', accept: { 'application/json': ['.json'] } }],
    })
    this.fileHandle = handle
    await this.writeFile()
    return handle.name
  }

  stopAutoSave() {
    this.fileHandle = null
    this.notify(null)
  }

  private persist() {
    try {
      localStorage.setItem(LS_EDITS_KEY, JSON.stringify(this.edits))
    } catch {
      /* quota / private mode: the file options still work */
    }
    if (this.fileHandle) {
      if (this.writeTimer) window.clearTimeout(this.writeTimer)
      this.writeTimer = window.setTimeout(() => void this.writeFile(), 400)
    } else {
      this.notify(null)
    }
  }

  private async writeFile() {
    if (!this.fileHandle) return
    try {
      const writable = await this.fileHandle.createWritable()
      await writable.write(JSON.stringify(editsToFile(this.edits, this.sourceFile), null, 2))
      await writable.close()
      this.notify(null)
    } catch (e) {
      this.notify((e as Error).message || 'could not write the file')
    }
  }

  private notify(error: string | null) {
    this.onPersist?.({ count: Object.keys(this.edits).length, file: this.fileHandle?.name ?? null, error })
  }
}

export function createStore(): Store {
  return isStandalone() ? new LocalStore() : new ServerStore()
}
