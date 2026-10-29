import { useId, useState } from 'react'

export interface Bar {
  key: string
  label: string
  value: number
  selected?: boolean
}

interface Props {
  bars: Bar[]
  /** Called when a bar is clicked; makes the chart act as a filter. */
  onToggle?: (key: string) => void
  /** When true, unselected bars are drawn in the de-emphasis gray. */
  emphasize?: boolean
  height?: number
  title: string
  /** Bars whose key is in this set get the "flag" (warning) fill, e.g. Unknown. */
  flagKeys?: string[]
  /** Label every bar's value on its cap (for small charts). */
  labelAll?: boolean
}

/**
 * Column chart drawn as inline SVG. One series, one hue; the emphasis form
 * (selected = blue, rest = gray) is used when the chart doubles as a filter.
 */
export default function BarChart({ bars, onToggle, emphasize, height = 150, title, flagKeys = [], labelAll }: Props) {
  const [hover, setHover] = useState<number | null>(null)
  const uid = useId()
  const max = Math.max(1, ...bars.map((b) => b.value))
  const padL = 8
  const padR = 8
  const padT = 18
  const padB = 22
  const width = Math.max(240, bars.length * 34)
  const plotW = width - padL - padR
  const plotH = height - padT - padB
  const slot = plotW / bars.length
  const barW = Math.min(24, slot * 0.7)
  const flagSet = new Set(flagKeys)

  // round the axis max to a clean number for the two gridlines
  const niceMax = niceCeil(max)
  const y = (v: number) => padT + plotH - (v / niceMax) * plotH

  const hovered = hover !== null ? bars[hover] : null

  return (
    <div className="chart" aria-label={title}>
      <svg
        viewBox={`0 0 ${width} ${height}`}
        width="100%"
        height={height}
        preserveAspectRatio="none"
        role="img"
        aria-labelledby={`${uid}-title`}
        onMouseLeave={() => setHover(null)}
      >
        <title id={`${uid}-title`}>{title}</title>
        {/* gridlines */}
        {[0.5, 1].map((f) => (
          <line
            key={f}
            x1={padL}
            x2={width - padR}
            y1={y(niceMax * f)}
            y2={y(niceMax * f)}
            className="grid"
          />
        ))}
        <text x={padL} y={y(niceMax) - 4} className="axis-text">
          {compact(niceMax)}
        </text>
        {/* baseline */}
        <line x1={padL} x2={width - padR} y1={padT + plotH} y2={padT + plotH} className="baseline" />
        {bars.map((b, i) => {
          const h = Math.max(b.value > 0 ? 2 : 0, (b.value / niceMax) * plotH)
          const x = padL + i * slot + (slot - barW) / 2
          const top = padT + plotH - h
          const cls = ['bar']
          if (flagSet.has(b.key)) cls.push('flag')
          if (emphasize) cls.push(b.selected ? 'selected' : 'dim')
          if (hover === i) cls.push('hover')
          const showLabel = labelAll || hover === i
          return (
            <g
              key={b.key}
              className={onToggle ? 'bar-group clickable' : 'bar-group'}
              onMouseEnter={() => setHover(i)}
              onFocus={() => setHover(i)}
              onBlur={() => setHover(null)}
              onClick={onToggle ? () => onToggle(b.key) : undefined}
              onKeyDown={
                onToggle
                  ? (e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault()
                        onToggle(b.key)
                      }
                    }
                  : undefined
              }
              tabIndex={onToggle ? 0 : -1}
              role={onToggle ? 'button' : undefined}
              aria-pressed={onToggle ? !!b.selected : undefined}
              aria-label={`${b.label}: ${b.value.toLocaleString('en-CA')}`}
            >
              {/* hit target larger than the mark */}
              <rect x={padL + i * slot} y={padT} width={slot} height={plotH + padB} fill="transparent" />
              {/* rounded data end, square at the baseline */}
              <path d={roundedTopRect(x, top, barW, h, 4)} className={cls.join(' ')} />
              {showLabel && b.value > 0 && (
                <text x={x + barW / 2} y={top - 4} textAnchor="middle" className="value-text">
                  {b.value.toLocaleString('en-CA')}
                </text>
              )}
              <text
                x={x + barW / 2}
                y={padT + plotH + 14}
                textAnchor="middle"
                className={`axis-text ${hover === i ? 'strong' : ''}`}
              >
                {b.label}
              </text>
            </g>
          )
        })}
      </svg>
      {hovered && (
        <div className="chart-tooltip" role="status">
          <strong>{hovered.value.toLocaleString('en-CA')}</strong> <span>{hovered.label}</span>
          {onToggle && <span className="muted"> · click to {hovered.selected ? 'remove' : 'filter'}</span>}
        </div>
      )}
    </div>
  )
}

function roundedTopRect(x: number, y: number, w: number, h: number, r: number): string {
  if (h <= 0) return ''
  const rr = Math.min(r, w / 2, h)
  return [
    `M${x},${y + h}`,
    `V${y + rr}`,
    `Q${x},${y} ${x + rr},${y}`,
    `H${x + w - rr}`,
    `Q${x + w},${y} ${x + w},${y + rr}`,
    `V${y + h}`,
    'Z',
  ].join(' ')
}

function niceCeil(v: number): number {
  if (v <= 10) return 10
  const mag = Math.pow(10, Math.floor(Math.log10(v)))
  const n = v / mag
  const step = n <= 1 ? 1 : n <= 2 ? 2 : n <= 2.5 ? 2.5 : n <= 5 ? 5 : 10
  return step * mag
}

function compact(v: number): string {
  if (v >= 1000) return `${(v / 1000).toFixed(v % 1000 === 0 ? 0 : 1)}K`
  return String(v)
}
