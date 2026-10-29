export type LineType = 'MP' | 'WLS' | 'Both' | 'Unknown'
export type ExtractionSource = 'name' | 'additional_info' | 'none'
export type Status =
  | 'Not started'
  | 'Called'
  | 'Left voicemail'
  | 'Callback scheduled'
  | 'Not interested'
  | 'Won back'

export const STATUSES: Status[] = [
  'Not started',
  'Called',
  'Left voicemail',
  'Callback scheduled',
  'Not interested',
  'Won back',
]
export const LINE_TYPES: LineType[] = ['MP', 'WLS', 'Both', 'Unknown']

/** One row of data/opportunities.json, exactly as the importer wrote it. */
export interface Opportunity {
  id: string
  row_number: number
  owner: string
  account_name: string
  account_name_raw: string
  account_name_repaired: boolean
  phone: string | null
  phone_tel: string | null
  opportunity_name: string
  opportunity_name_raw: string
  close_date: string
  close_month: string
  close_month_label: string
  next_step: string | null
  additional_info: string | null
  line_count: number | null
  line_type: LineType
  mp_count: number | null
  wls_count: number | null
  types_mentioned: string[]
  extraction_source: ExtractionSource
  line_match: string
  line_bucket: string
  estimated_renewal_date: string
  estimated_renewal_month: string
  estimated_renewal_month_label: string
  contract_end_hint: string | null
  contract_end_month: string | null
  contract_end_confidence: 'high' | 'low' | null
}

export interface Meta {
  source_file: string
  imported_at: string
  row_count: number
  parser_version: string
  buckets: string[]
  line_types: LineType[]
  statuses: Status[]
  excluded_name_pattern?: string | null
  excluded_count?: number
}

export interface Dataset {
  meta: Meta
  opportunities: Opportunity[]
}

/** One row of the SQLite edits table. */
export interface Edit {
  row_hash: string
  line_count_override: number | null
  line_type_override: LineType | null
  status: Status
  notes: string
  follow_up_date: string | null
  updated_at: string
}

export type EditInput = Omit<Edit, 'row_hash' | 'updated_at'>

/** Opportunity merged with its edit plus the derived values the UI filters on. */
export interface Row extends Opportunity {
  edit: Edit | null
  effCount: number | null
  effType: LineType
  effBucket: string
  overridden: boolean
  status: Status
  notes: string
  followUp: string | null
  searchBlob: string
}
