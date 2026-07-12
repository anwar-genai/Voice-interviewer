import React, { useState } from 'react'
import type { Job } from '../../lib/types'

// Short, always-visible fields vs. the long free-text ones we tuck behind a toggle.
const PRIMARY: [keyof Job, string][] = [
  ['job_title', 'Title'],
  ['job_type', 'Employment'],
  ['location', 'Location'],
  ['start_date', 'Start date'],
]
const DETAIL: [keyof Job, string][] = [
  ['qualifications', 'Requirements'],
  ['responsibilities', 'Responsibilities'],
  ['benefits', 'Benefits'],
]

const Row: React.FC<{ label: string; value: string }> = ({ label, value }) => (
  <div className="job-card-row">
    <dt>{label}</dt>
    <dd>{value}</dd>
  </div>
)

/**
 * Human-readable job card. Only fields the extractor actually found are shown,
 * and the long free-text fields collapse so the card stays scannable.
 */
export const JobPreview: React.FC<{ job: Partial<Job>; title?: string }> = ({ job, title = 'Parsed job details' }) => {
  const [expanded, setExpanded] = useState(false)
  const primary = PRIMARY.filter(([k]) => job[k])
  const detail = DETAIL.filter(([k]) => job[k])
  if (primary.length === 0 && detail.length === 0) return null
  return (
    <div className="preview-section">
      <h3 className="preview-title">{title}</h3>
      <dl className="job-card">
        {primary.map(([k, label]) => <Row key={k} label={label} value={job[k]!} />)}
        {expanded && detail.map(([k, label]) => <Row key={k} label={label} value={job[k]!} />)}
      </dl>
      {detail.length > 0 && (
        <button type="button" className="link-toggle" aria-expanded={expanded} onClick={() => setExpanded((v) => !v)}>
          {expanded ? 'Show less' : `Show full details (${detail.length})`}
        </button>
      )}
      <p className="hint-line">Only details found in the posting are shown — anything missing is left out.</p>
    </div>
  )
}
