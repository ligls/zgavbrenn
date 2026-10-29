import { strToU8, zipSync } from 'fflate'

/**
 * Minimal .xlsx writer (no dependency on a spreadsheet library).
 *
 * Produces a single-sheet workbook with inline strings, a bold frozen header
 * row, column widths and an auto-filter - enough for Excel, Numbers and
 * LibreOffice to open it cleanly.  Numbers are written as numeric cells so
 * line counts sort correctly; everything else is text.
 */

export type CellValue = string | number | null | undefined

const XML_HEAD = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
const NS_MAIN = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
const NS_REL = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
const NS_PKG_REL = 'http://schemas.openxmlformats.org/package/2006/relationships'

function esc(s: string): string {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')
}

/** XML 1.0 forbids most C0 control characters; strip them. */
function cleanText(s: string): string {
  // eslint-disable-next-line no-control-regex
  return s.replace(/[\u0000-\u0008\u000B\u000C\u000E-\u001F]/g, '')
}

export function colLetter(index: number): string {
  let n = index + 1
  let out = ''
  while (n > 0) {
    const m = (n - 1) % 26
    out = String.fromCharCode(65 + m) + out
    n = Math.floor((n - 1) / 26)
  }
  return out
}

function cellXml(rowIdx: number, colIdx: number, value: CellValue, styleId = 0): string {
  if (value === null || value === undefined || value === '') return ''
  const ref = `${colLetter(colIdx)}${rowIdx + 1}`
  const s = styleId ? ` s="${styleId}"` : ''
  if (typeof value === 'number' && Number.isFinite(value)) {
    return `<c r="${ref}"${s}><v>${value}</v></c>`
  }
  return `<c r="${ref}"${s} t="inlineStr"><is><t xml:space="preserve">${esc(cleanText(String(value)))}</t></is></c>`
}

export interface XlsxOptions {
  sheetName?: string
  /** Column widths in Excel character units, by column index. */
  widths?: number[]
}

export function buildXlsx(headers: string[], rows: CellValue[][], opts: XlsxOptions = {}): Blob {
  const sheetName = (opts.sheetName ?? 'Sheet1').replace(/[\\/?*[\]:]/g, ' ').slice(0, 31)
  const lastCol = colLetter(Math.max(0, headers.length - 1))
  const lastRow = rows.length + 1

  let sheet = XML_HEAD
  sheet += `<worksheet xmlns="${NS_MAIN}" xmlns:r="${NS_REL}">`
  sheet += `<dimension ref="A1:${lastCol}${lastRow}"/>`
  sheet += '<sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>'
  sheet += '<sheetFormatPr defaultRowHeight="15"/>'
  if (opts.widths && opts.widths.length) {
    sheet += '<cols>'
    opts.widths.forEach((w, i) => {
      sheet += `<col min="${i + 1}" max="${i + 1}" width="${w}" customWidth="1"/>`
    })
    sheet += '</cols>'
  }
  sheet += '<sheetData>'
  sheet += `<row r="1">${headers.map((h, c) => cellXml(0, c, h, 1)).join('')}</row>`
  for (let i = 0; i < rows.length; i++) {
    const row = rows[i]
    let cells = ''
    for (let c = 0; c < row.length; c++) cells += cellXml(i + 1, c, row[c])
    sheet += `<row r="${i + 2}">${cells}</row>`
  }
  sheet += '</sheetData>'
  sheet += `<autoFilter ref="A1:${lastCol}${lastRow}"/>`
  sheet += '</worksheet>'

  const workbook =
    XML_HEAD +
    `<workbook xmlns="${NS_MAIN}" xmlns:r="${NS_REL}">` +
    `<sheets><sheet name="${esc(sheetName)}" sheetId="1" r:id="rId1"/></sheets>` +
    `<definedNames><definedName name="_xlnm._FilterDatabase" localSheetId="0" hidden="1">'${esc(sheetName.replace(/'/g, "''"))}'!$A$1:$${lastCol}$${lastRow}</definedName></definedNames>` +
    '</workbook>'

  const styles =
    XML_HEAD +
    `<styleSheet xmlns="${NS_MAIN}">` +
    '<fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><sz val="11"/><name val="Calibri"/></font></fonts>' +
    '<fills count="2"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill></fills>' +
    '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>' +
    '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>' +
    '<cellXfs count="2"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/><xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1"/></cellXfs>' +
    '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>' +
    '</styleSheet>'

  const workbookRels =
    XML_HEAD +
    `<Relationships xmlns="${NS_PKG_REL}">` +
    `<Relationship Id="rId1" Type="${NS_REL}/worksheet" Target="worksheets/sheet1.xml"/>` +
    `<Relationship Id="rId2" Type="${NS_REL}/styles" Target="styles.xml"/>` +
    '</Relationships>'

  const rootRels =
    XML_HEAD +
    `<Relationships xmlns="${NS_PKG_REL}">` +
    `<Relationship Id="rId1" Type="${NS_REL}/officeDocument" Target="xl/workbook.xml"/>` +
    '</Relationships>'

  const contentTypes =
    XML_HEAD +
    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">' +
    '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>' +
    '<Default Extension="xml" ContentType="application/xml"/>' +
    '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>' +
    '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>' +
    '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>' +
    '</Types>'

  const zipped = zipSync(
    {
      '[Content_Types].xml': strToU8(contentTypes),
      '_rels/.rels': strToU8(rootRels),
      'xl/workbook.xml': strToU8(workbook),
      'xl/_rels/workbook.xml.rels': strToU8(workbookRels),
      'xl/styles.xml': strToU8(styles),
      'xl/worksheets/sheet1.xml': strToU8(sheet),
    },
    { level: 6 },
  )
  return new Blob([zipped as BlobPart], {
    type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  })
}
