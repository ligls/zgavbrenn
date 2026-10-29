import type { Dataset, Edit, EditInput } from '../types'

async function handle<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let message = `${res.status} ${res.statusText}`
    try {
      const body = (await res.json()) as { error?: string }
      if (body.error) message = body.error
    } catch {
      /* not JSON */
    }
    throw new Error(message)
  }
  return (await res.json()) as T
}

export async function fetchDataset(): Promise<Dataset> {
  return handle<Dataset>(await fetch('/api/opportunities', { cache: 'no-store' }))
}

export async function fetchEdits(): Promise<Record<string, Edit>> {
  return handle<Record<string, Edit>>(await fetch('/api/edits', { cache: 'no-store' }))
}

export async function saveEdit(rowHash: string, input: EditInput): Promise<Edit> {
  return handle<Edit>(
    await fetch(`/api/edits/${encodeURIComponent(rowHash)}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(input),
    }),
  )
}

export async function deleteEdit(rowHash: string): Promise<void> {
  await handle<unknown>(await fetch(`/api/edits/${encodeURIComponent(rowHash)}`, { method: 'DELETE' }))
}

export function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
