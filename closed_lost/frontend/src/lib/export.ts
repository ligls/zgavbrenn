import type { Row } from '../types'
import type { ExportColumn } from './api'

/** Column list shared by the CSV (client) and XLSX (server) exports. */
export const EXPORT_COLUMNS: ExportColumn[] = [
  { key: 'owner', label: 'Opportunity Owner' },
  { key: 'account_name', label: 'Account Name' },
  { key: 'phone', label: 'Phone' },
  { key: 'opportunity_name', label: 'Opportunity Name' },
  { key: 'close_date', label: 'Close Date' },
  { key: 'next_step', label: 'Next Step' },
  { key: 'additional_info', label: 'Additional Info' },
  { key: 'effective_line_count', label: 'Line Count' },
  { key: 'effective_line_type', label: 'Line Type' },
  { key: 'line_bucket', label: 'Bucket (parsed)' },
  { key: 'line_count', label: 'Parsed Count' },
  { key: 'line_type', label: 'Parsed Type' },
  { key: 'mp_count', label: 'MP' },
  { key: 'wls_count', label: 'WLS' },
  { key: 'extraction_source', label: 'Extraction Source' },
  { key: 'line_match', label: 'Matched Text' },
  { key: 'close_month_label', label: 'Close Month' },
  { key: 'estimated_renewal_date', label: 'Estimated Renewal' },
  { key: 'contract_end_hint', label: 'Contract End Hint' },
  { key: 'contract_end_month', label: 'Contract End Month' },
  { key: 'status', label: 'Status' },
  { key: 'notes', label: 'My Notes' },
  { key: 'follow_up_date', label: 'Follow-up Date' },
  { key: 'edited_at', label: 'Last Edited' },
  { key: 'account_name_raw', label: 'Account Name (raw)' },
  { key: 'id', label: 'Row Hash' },
]

export function rowValue(row: Row, key: string): string | number | null {
  switch (key) {
    case 'effective_line_count':
      return row.effCount
    case 'effective_line_type':
      return row.effType
    case 'status':
      return row.status
    case 'notes':
      return row.notes
    case 'follow_up_date':
      return row.followUp
    case 'edited_at':
      return row.edit?.updated_at ?? ''
    case 'types_mentioned':
      return row.types_mentioned.join(', ')
    default: {
      const v = (row as unknown as Record<string, unknown>)[key]
      if (v === null || v === undefined) return null
      if (Array.isArray(v)) return v.join(', ')
      return v as string | number
    }
  }
}

function csvCell(value: string | number | null): string {
  if (value === null || value === undefined) return ''
  const s = String(value)
  if (/[",\n\r]/.test(s)) return `"${s.replace(/"/g, '""')}"`
  return s
}

export function rowsToCsv(rows: Row[]): string {
  const lines = [EXPORT_COLUMNS.map((c) => csvCell(c.label)).join(',')]
  for (const r of rows) {
    lines.push(EXPORT_COLUMNS.map((c) => csvCell(rowValue(r, c.key))).join(','))
  }
  // BOM so Excel opens accented characters correctly.
  return '﻿' + lines.join('\r\n')
}

export function exportFilename(ext: string): string {
  const d = new Date()
  const stamp = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}_${String(d.getHours()).padStart(2, '0')}${String(d.getMinutes()).padStart(2, '0')}`
  return `closed_lost_export_${stamp}.${ext}`
}
