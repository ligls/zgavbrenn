import { gunzipSync, strFromU8 } from 'fflate'
import type { Dataset, Edit, EditInput } from '../types'
import { deleteEdit as apiDeleteEdit, fetchDataset, fetchEdits, saveEdit as apiSaveEdit } from './api'

/**
 * Where the data and your edits live.
 *
 * - ServerStore:   the Flask app (data/opportunities.json + SQLite edits).
 * - LocalStore:    the single-file build opened from disk. The dataset is
 *                  embedded in the HTML (gzip + base64 in <script id="cl-data">),
 *                  edits live in the browser's localStorage and can be saved to /
 *                  loaded from a JSON file, or auto-saved to a file picked once
 *                  per session (Chrome/Edge File System Access API).
 * - ArtifactStore: the same embedded page published as a claude.ai artifact.
 *                  Edits are shared documents in the artifact's `db` capability
 *                  (one document per row hash, live for every viewer); files are
 *                  handed to the viewer through the `downloads` capability. When
 *                  the view cannot run `db`, it degrades to LocalStore behaviour.
 */

export interface StoreInfo {
  /** Edits are shared with everyone who opens the page. */
  shared: boolean
  /** This viewer cannot write shared edits. */
  readOnly: boolean
  /** Short notice for the banner, or null. */
  message: string | null
}

export interface Store {
  readonly mode: 'server' | 'standalone' | 'artifact'
  loadDataset(): Promise<Dataset>
  loadEdits(): Promise<Record<string, Edit>>
  saveEdit(id: string, input: EditInput): Promise<Edit>
  deleteEdit(id: string): Promise<void>
  /** Live updates from other people (shared stores). Returns an unsubscribe. */
  subscribe?(onEdits: (edits: Record<string, Edit>) => void, onError?: (message: string) => void): () => void
  /** Hand a generated file to the viewer where direct downloads are blocked. */
  download?(filename: string, blob: Blob): Promise<void>
  /** Resolve people ids to display names ("you" for the viewer). */
  profiles?(ids: string[]): Promise<Record<string, string>>
  info: StoreInfo
  /** Fired when `info` changes after load (e.g. a refused write). */
  onInfoChange: ((info: StoreInfo) => void) | null
  /** Present when edits live in this browser (LocalStore, or an artifact view without db). */
  local?: LocalStore
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
const EDITS_COLLECTION = 'edits'

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

/** The claude.ai artifact runtime exposes window.claude.use(). */
function hasArtifactRuntime(): boolean {
  const w = window as unknown as { claude?: { use?: unknown } }
  return typeof w.claude?.use === 'function'
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
  info: StoreInfo = { shared: true, readOnly: false, message: null }
  onInfoChange: ((info: StoreInfo) => void) | null = null
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

// ---------------------------------------------------------------- standalone (browser storage)

type FileHandle = {
  name: string
  createWritable(): Promise<{ write(data: Blob | string): Promise<void>; close(): Promise<void> }>
}
type SaveFilePicker = (opts: {
  suggestedName?: string
  types?: Array<{ description: string; accept: Record<string, string[]> }>
}) => Promise<FileHandle>

export class LocalStore implements Store {
  readonly mode = 'standalone' as const
  info: StoreInfo = { shared: false, readOnly: false, message: null }
  onInfoChange: ((info: StoreInfo) => void) | null = null
  readonly local: LocalStore = this
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

// ---------------------------------------------------------------- claude.ai artifact (shared db)

// Minimal views of the runtime contract (0.2.x) this page relies on.
interface DbDocSnap {
  id: string
  exists: boolean
  data(): Record<string, unknown> | undefined
}
interface DbQuerySnap {
  docs: DbDocSnap[]
}
interface DbError {
  code: string
  message: string
}
interface DbDocRef {
  set(data: Record<string, unknown>): Promise<void>
  delete(): Promise<void>
}
interface DbCollectionRef {
  doc(id: string): DbDocRef
  get(): Promise<DbQuerySnap>
  onSnapshot(next: (snap: DbQuerySnap) => void, error?: (e: DbError) => void): () => void
}
interface DbNs {
  collection(path: string): DbCollectionRef
}
interface UserNs {
  id(): Promise<string | null>
  can(name: string): Promise<boolean | null>
  profiles(ids: readonly string[]): Promise<Record<string, { name: string; isMe: boolean }>>
}
interface DownloadsNs {
  save(req: { filename: string; data: Blob | string }): Promise<{ status: string }>
}
interface ClaudeRuntime {
  use(name: 'db'): Promise<DbNs | null>
  use(name: 'user'): Promise<UserNs | null>
  use(name: 'downloads'): Promise<DownloadsNs | null>
}

const READ_ONLY_MESSAGE =
  'You can browse but not save: ask the owner to share this page with you as a Contributor (or Editor).'

function toEdit(id: string, data: Record<string, unknown> | undefined): Edit | null {
  if (!data) return null
  return {
    row_hash: id,
    line_count_override: typeof data.line_count_override === 'number' ? data.line_count_override : null,
    line_type_override: (data.line_type_override as Edit['line_type_override']) ?? null,
    status: (data.status as Edit['status']) ?? 'Not started',
    notes: typeof data.notes === 'string' ? data.notes : '',
    follow_up_date: typeof data.follow_up_date === 'string' ? data.follow_up_date : null,
    updated_at: typeof data.updated_at === 'string' ? data.updated_at : '',
    updated_by: typeof data.updated_by === 'string' ? data.updated_by : null,
  }
}

function describeDbError(e: unknown, fallback: string): string {
  const err = e as Partial<DbError> | undefined
  switch (err?.code) {
    case 'invalid_argument':
      return READ_ONLY_MESSAGE
    case 'quota_exceeded':
      return 'The shared store is full. Ask the owner to clean up old edits.'
    case 'resource_exhausted':
      return 'Too many saves at once. Wait a moment and try again.'
    case 'revoked':
      return 'Your access to this page changed. Reload to continue.'
    case 'unavailable':
      return 'The shared store is temporarily unavailable. Try again in a moment.'
    default:
      return err?.message || fallback
  }
}

export class ArtifactStore implements Store {
  readonly mode = 'artifact' as const
  info: StoreInfo = { shared: false, readOnly: false, message: null }
  onInfoChange: ((info: StoreInfo) => void) | null = null
  local?: LocalStore
  private embedded = readEmbedded()
  private db: DbNs | null = null
  private user: UserNs | null = null
  private downloads: DownloadsNs | null = null
  private userId: string | null = null
  private edits: Record<string, Edit> = {}

  private runtime(): ClaudeRuntime {
    return (window as unknown as { claude: ClaudeRuntime }).claude
  }

  private setInfo(info: StoreInfo) {
    this.info = info
    this.onInfoChange?.(info)
  }

  async loadDataset(): Promise<Dataset> {
    if (!this.embedded) throw new Error('No embedded dataset found in this page.')
    return this.embedded.dataset
  }

  async loadEdits(): Promise<Record<string, Edit>> {
    const rt = this.runtime()
    const [db, user, downloads] = await Promise.all([rt.use('db'), rt.use('user'), rt.use('downloads')])
    this.downloads = downloads
    if (!db) {
      // This view cannot run the shared store: keep working in this browser.
      this.local = new LocalStore()
      this.setInfo({
        shared: false,
        readOnly: false,
        message:
          'Shared saving is not available in this view, so your edits stay in this browser. Use the edits menu to save them to a file.',
      })
      return this.local.loadEdits()
    }
    this.db = db
    this.user = user
    this.userId = user ? await user.id() : null
    const canWrite = user ? await user.can('data.write') : null
    this.setInfo({
      shared: true,
      readOnly: canWrite === false,
      message: canWrite === false ? READ_ONLY_MESSAGE : null,
    })
    const snap = await db.collection(EDITS_COLLECTION).get()
    this.edits = {}
    for (const d of snap.docs) {
      const e = toEdit(d.id, d.data())
      if (e) this.edits[d.id] = e
    }
    return { ...this.edits }
  }

  subscribe(onEdits: (edits: Record<string, Edit>) => void, onError?: (message: string) => void): () => void {
    if (!this.db) return () => {}
    return this.db.collection(EDITS_COLLECTION).onSnapshot(
      (snap) => {
        const next: Record<string, Edit> = {}
        for (const d of snap.docs) {
          const e = toEdit(d.id, d.data())
          if (e) next[d.id] = e
        }
        this.edits = next
        onEdits({ ...next })
      },
      (err) => onError?.(describeDbError(err, 'Live updates stopped. Reload the page to reconnect.')),
    )
  }

  async saveEdit(id: string, input: EditInput): Promise<Edit> {
    if (this.local) return this.local.saveEdit(id, input)
    const edit: Edit = { row_hash: id, ...input, updated_at: nowIso(), updated_by: this.userId }
    try {
      await this.db!.collection(EDITS_COLLECTION).doc(id).set(edit as unknown as Record<string, unknown>)
    } catch (e) {
      if ((e as Partial<DbError>)?.code === 'invalid_argument') {
        this.setInfo({ ...this.info, readOnly: true, message: READ_ONLY_MESSAGE })
      }
      throw new Error(describeDbError(e, 'Could not save the edit.'))
    }
    this.edits[id] = edit
    return edit
  }

  async deleteEdit(id: string): Promise<void> {
    if (this.local) return this.local.deleteEdit(id)
    try {
      await this.db!.collection(EDITS_COLLECTION).doc(id).delete()
    } catch (e) {
      if ((e as Partial<DbError>)?.code === 'invalid_argument') {
        this.setInfo({ ...this.info, readOnly: true, message: READ_ONLY_MESSAGE })
      }
      throw new Error(describeDbError(e, 'Could not remove the edit.'))
    }
    delete this.edits[id]
  }

  async download(filename: string, blob: Blob): Promise<void> {
    if (!this.downloads) throw new Error('Downloads are not available in this view.')
    try {
      await this.downloads.save({ filename, data: blob })
    } catch (e) {
      const code = (e as { code?: string })?.code
      if (code === 'declined') throw new DeclinedDownload()
      throw new Error((e as Error)?.message || 'The file could not be saved.')
    }
  }

  async profiles(ids: string[]): Promise<Record<string, string>> {
    const out: Record<string, string> = {}
    if (!this.user || ids.length === 0) return out
    const ps = await this.user.profiles(ids)
    for (const id of ids) {
      const p = ps[id]
      out[id] = p ? (p.isMe ? 'you' : p.name || 'a colleague') : 'a colleague'
    }
    return out
  }
}

/** Thrown when the viewer cancels a download prompt; not an error to show. */
export class DeclinedDownload extends Error {
  constructor() {
    super('Download cancelled')
    this.name = 'DeclinedDownload'
  }
}

export function createStore(): Store {
  if (isStandalone()) return hasArtifactRuntime() ? new ArtifactStore() : new LocalStore()
  return new ServerStore()
}
