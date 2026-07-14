import React, { useState } from 'react'
import { api } from '../../lib/api'
import { useInterview } from '../InterviewContext'

/** Step 2: upload a PDF resume (click or drag-and-drop) and extract its text. */
export const ResumeUpload: React.FC = () => {
  const { resume, setResume } = useInterview()
  const [fileName, setFileName] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [dragging, setDragging] = useState(false)

  async function onPick(file: File) {
    if (file.type !== 'application/pdf' && !file.name.toLowerCase().endsWith('.pdf')) {
      setError('Please choose a PDF file.')
      return
    }
    setFileName(file.name)
    setResume('')
    setError('')
    setLoading(true)
    try {
      setResume(await api.uploadResume(file))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to parse resume')
    } finally {
      setLoading(false)
    }
  }

  function onDrop(e: React.DragEvent) {
    e.preventDefault()
    setDragging(false)
    const file = e.dataTransfer.files?.[0]
    if (file) onPick(file)
  }

  return (
    <div className="step-section">
      <div className="step-header">
        <div className="step-number" aria-hidden="true">2</div>
        <h2 className="step-title">Your resume</h2>
      </div>

      <div className="input-group">
        <label className="input-label" htmlFor="resume-upload">Upload resume (PDF)</label>
        <div
          className={`file-upload ${dragging ? 'dragging' : ''}`}
          onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
        >
          <input
            type="file"
            id="resume-upload"
            accept="application/pdf"
            onChange={(e) => {
              const file = e.target.files?.[0]
              if (file) onPick(file)
            }}
          />
          <label htmlFor="resume-upload" className={`file-upload-label ${fileName ? 'has-file' : ''}`}>
            {fileName ? (
              <span className="file-primary">📄 {fileName}</span>
            ) : (
              <>
                <span className="file-icon" aria-hidden="true">⬆</span>
                <span className="file-primary">Drag &amp; drop your résumé</span>
                <span className="file-hint">or click to browse · PDF, up to 10&nbsp;MB</span>
              </>
            )}
          </label>
        </div>
        {loading && (
          <div className="status-badge status-ready" role="status">
            <span className="loading-spinner" /> Parsing your resume…
          </div>
        )}
        {resume && !loading && <div className="status-badge status-connected" role="status">✅ Resume parsed</div>}
        {error && <div className="status-badge status-error" role="alert">⚠️ {error}</div>}
      </div>

      {resume && (
        <div className="preview-section">
          <h3 className="preview-title">📝 Resume content</h3>
          <div className="preview-content">{resume.substring(0, 500)}…</div>
        </div>
      )}
    </div>
  )
}
