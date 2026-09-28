import { useState, useRef } from 'react'
import { uploadPropertiesCsv } from '../api/client'
import PageHeader from '../components/PageHeader'
import ChartPanel from '../components/ChartPanel'
import { LoadingState, ErrorState, EmptyState } from '../components/States'

const STATUS_STYLES = {
  success: 'border-emerald-200 bg-emerald-50 text-emerald-800',
  partial: 'border-amber-200 bg-amber-50 text-amber-800',
  rejected: 'border-red-200 bg-red-50 text-red-800',
  empty: 'border-gray-200 bg-gray-50 text-gray-700',
  error: 'border-red-200 bg-red-50 text-red-800',
}

const REQUIRED_COLUMNS = 'id, name'
const OPTIONAL_COLUMNS = 'city, state, property_type, area_sqft, occupancy_pct, annual_revenue, ' +
  'operating_expenses, property_value, tenant_name, lease_start, lease_end, annual_rent'

export default function ImportCsv() {
  const [file, setFile] = useState(null)
  const [isDragging, setIsDragging] = useState(false)
  const [status, setStatus] = useState('idle') // idle | uploading | done | error
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const inputRef = useRef(null)

  const pickFile = (f) => {
    if (!f) return
    setFile(f)
    setResult(null)
    setError(null)
    setStatus('idle')
  }

  const onDrop = (e) => {
    e.preventDefault()
    setIsDragging(false)
    const dropped = e.dataTransfer.files?.[0]
    pickFile(dropped)
  }

  const doUpload = () => {
    if (!file) return
    setStatus('uploading')
    setError(null)
    uploadPropertiesCsv(file)
      .then((d) => { setResult(d); setStatus('done') })
      .catch((err) => {
        setError(err.response?.data?.detail || err.message)
        setStatus('error')
      })
  }

  const reset = () => {
    setFile(null)
    setResult(null)
    setError(null)
    setStatus('idle')
    if (inputRef.current) inputRef.current.value = ''
  }

  return (
    <div>
      <PageHeader title="CSV Import" subtitle="Upload a properties CSV — validated against the same rules as the Data Quality engine" />

      <ChartPanel title="Upload File">
        <div
          onDragOver={(e) => { e.preventDefault(); setIsDragging(true) }}
          onDragLeave={() => setIsDragging(false)}
          onDrop={onDrop}
          onClick={() => inputRef.current?.click()}
          className={`cursor-pointer rounded-lg border-2 border-dashed px-6 py-10 text-center transition-colors ${
            isDragging ? 'border-gray-500 bg-gray-50' : 'border-gray-300 hover:border-gray-400'
          }`}
        >
          <input
            ref={inputRef}
            type="file"
            accept=".csv"
            className="hidden"
            onChange={(e) => pickFile(e.target.files?.[0])}
          />
          <p className="text-sm font-medium text-gray-700">
            {file ? file.name : 'Drop a CSV file here, or click to browse'}
          </p>
          <p className="mt-1 text-xs text-gray-400">
            {file ? `${(file.size / 1024).toFixed(1)} KB` : 'Only .csv files, up to 5 MB'}
          </p>
        </div>

        <div className="mt-3 text-xs text-gray-500">
          <p><span className="font-medium text-gray-700">Required columns:</span> {REQUIRED_COLUMNS}</p>
          <p className="mt-1"><span className="font-medium text-gray-700">Optional columns:</span> {OPTIONAL_COLUMNS}</p>
        </div>

        <div className="mt-4 flex gap-2">
          <button
            onClick={doUpload}
            disabled={!file || status === 'uploading'}
            className="rounded-md bg-gray-900 px-4 py-2 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-40 hover:bg-gray-800"
          >
            {status === 'uploading' ? 'Uploading…' : 'Upload & Validate'}
          </button>
          {(file || result) && (
            <button
              onClick={reset}
              className="rounded-md border border-gray-300 px-4 py-2 text-sm font-medium text-gray-600 hover:bg-gray-50"
            >
              Clear
            </button>
          )}
        </div>
      </ChartPanel>

      {status === 'uploading' && (
        <div className="mt-6">
          <LoadingState label="Validating and importing…" />
        </div>
      )}

      {status === 'error' && (
        <div className="mt-6">
          <ErrorState message={error} onRetry={doUpload} />
        </div>
      )}

      {status === 'done' && result && (
        <div className="mt-6 space-y-6">
          <div className={`rounded-lg border px-4 py-3 text-sm font-medium ${STATUS_STYLES[result.status] || STATUS_STYLES.empty}`}>
            {result.message}
          </div>

          <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
            <SummaryCard label="Total Rows" value={result.total_rows} />
            <SummaryCard label="Imported" value={result.valid_rows} tone="good" />
            <SummaryCard label="Rejected" value={result.rejected_rows} tone={result.rejected_rows > 0 ? 'danger' : 'default'} />
            <SummaryCard label="Warnings" value={result.issue_counts.warning || 0} tone={result.issue_counts.warning ? 'warning' : 'default'} />
          </div>

          {result.imported_property_ids.length > 0 && (
            <ChartPanel title={`Imported Properties (${result.imported_property_ids.length})`}>
              <div className="flex flex-wrap gap-2">
                {result.imported_property_ids.map((id) => (
                  <span key={id} className="rounded-md bg-gray-100 px-2 py-1 text-xs font-medium text-gray-700">{id}</span>
                ))}
              </div>
            </ChartPanel>
          )}

          {result.row_issues.length > 0 ? (
            <ChartPanel title={`Row Issues (${result.row_issues.length})`}>
              <div className="table-scroll overflow-x-auto">
                <table className="w-full min-w-[600px] text-sm">
                  <thead>
                    <tr className="text-left text-xs uppercase tracking-wide text-gray-500">
                      <th className="py-1.5">Row</th>
                      <th className="py-1.5">Field</th>
                      <th className="py-1.5">Severity</th>
                      <th className="py-1.5">Message</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {result.row_issues.map((issue, i) => (
                      <tr key={i}>
                        <td className="py-1.5 text-gray-600">{issue.row_number}</td>
                        <td className="py-1.5 text-gray-500">{issue.field || '—'}</td>
                        <td className="py-1.5">
                          <span className={`inline-flex items-center rounded-md px-2 py-1 text-xs font-medium ring-1 ring-inset ${
                            issue.severity === 'reject'
                              ? 'bg-red-50 text-red-700 ring-red-600/20'
                              : 'bg-amber-50 text-amber-700 ring-amber-600/20'
                          }`}>
                            {issue.severity === 'reject' ? 'Rejected' : 'Warning'}
                          </span>
                        </td>
                        <td className="py-1.5 text-gray-600">{issue.message}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </ChartPanel>
          ) : (
            result.total_rows > 0 && <EmptyState message="No issues found — every row was clean." />
          )}
        </div>
      )}
    </div>
  )
}

function SummaryCard({ label, value, tone = 'default' }) {
  const toneClass = {
    default: 'text-gray-900',
    good: 'text-emerald-700',
    warning: 'text-amber-700',
    danger: 'text-red-700',
  }[tone]
  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
      <p className="text-xs font-medium uppercase tracking-wide text-gray-500">{label}</p>
      <p className={`mt-2 text-2xl font-semibold ${toneClass}`}>{value}</p>
    </div>
  )
}
