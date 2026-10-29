/** Accent-insensitive, case-insensitive text normalisation ("Métodex" -> "metodex"). */
export function normalize(text: string | null | undefined): string {
  if (!text) return ''
  return text
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .replace(/œ/g, 'oe')
    .replace(/æ/g, 'ae')
    .replace(/ß/g, 'ss')
    .toLowerCase()
}

export function digitsOnly(text: string | null | undefined): string {
  return (text ?? '').replace(/\D/g, '')
}

/** Split a search query into normalised tokens; every token must match. */
export function queryTokens(query: string): string[] {
  return normalize(query)
    .split(/\s+/)
    .map((t) => t.trim())
    .filter(Boolean)
}

export function matchesQuery(blob: string, tokens: string[]): boolean {
  for (const t of tokens) {
    if (!blob.includes(t)) return false
  }
  return true
}
