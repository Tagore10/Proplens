import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { getDataQualityReport, getDataQualityIssues } from '../api/client'
import PageHeader from '../components/PageHeader'
import ChartPanel from '../components/ChartPanel'
import { SeverityBadge } from '../components/Badges'
import Pagination from '../components/Pagination'
import { LoadingState, ErrorState, EmptyState } from '../components/States'
import { formatPercent } from '../utils/format'

const PAGE_SIZE = 15

const CATEGORY_LABELS = {
  missing_value: 'Missing Values',
  duplicate: 'Duplicates',
  invalid_value: 'Invalid Values',
  date_issue: 'Date Issues',
  outlier: 'Outliers',
  location_mismatch: 'Location Mismatches',
}

const ENTITY_TYPES = ['property', 'tenant', 'lease']

export default function DataQuality() {
  const [report, setReport] = useState(null)
  const [reportStatus, setReportStatus] = useState('loading')
  const [reportError, setReportError] = useState(null)

  const [issues, setIssues] = useState([])
  const [issuesTotal, setIssuesTotal] = useState(0)
  const [issuesStatus, setIssuesStatus] = useState('loading')
  const [issuesError, setIssuesError] = useState(null)

  const [issueType, setIssueType] = useState('')
  const [entityType, setEntityType] = useState('')
  const [page, setPage] = useState(1)

  const loadReport = () => {
    setReportStatus('loading')
    getDataQualityReport()
      .then((d) => { setReport(d); setReportStatus('ready') })
      .catch((err) => { setReportError(err.message); setReportStatus('error') })
  }

  const loadIssues = () => {
    setIssuesStatus('loading')
    getDataQualityIssues({
      issue_type: issueType || undefined,
      entity_type: entityType || undefined,
      page,
      page_size: PAGE_SIZE,
    })
      .then((d) => { setIssues(d.issues); setIssuesTotal(d.total); setIssuesStatus('ready') })
      .catch((err) => { setIssuesError(err.message); setIssuesStatus('error') })
  }

  useEffect(loadReport, [])
  useEffect(loadIssues, [issueType, entityType, page])

  const scoreTone = (score) => (score >= 70 ? 'text-emerald-700' : score >= 50 ? 'text-amber-700' : 'text-red-700')

  return (
    <div>
      <PageHeader title="Data Quality" subtitle="Rule-based detection across properties, tenants, and leases" />

      {reportStatus === 'loading' && <LoadingState label="Running data quality scan…" />}
      {reportStatus === 'error' && <ErrorState message={reportError} onRetry={loadReport} />}

      {reportStatus === 'ready' && report && (
        <>
          <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
            <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm md:col-span-2">
              <p className="text-xs font-medium uppercase tracking-wide text-gray-500">Overall Score</p>
              <p className={`mt-2 text-3xl font-semibold ${scoreTone(report.overall_score)}`}>
                {formatPercent(report.overall_score)}
              </p>
              <p className="mt-1 text-xs text-gray-400">{report.total_issues} total issues detected</p>
            </div>
            {Object.entries(CATEGORY_LABELS).map(([key, label]) => {
              const countKey = {
                missing_value: 'missing_values',
                duplicate: 'duplicates',
                invalid_value: 'invalid_values',
                date_issue: 'date_issues',
                outlier: 'outliers',
                location_mismatch: 'location_mismatches',
              }[key]
              return (
                <button
                  key={key}
                  onClick={() => { setIssueType(issueType === key ? '' : key); setPage(1) }}
                  className={`rounded-lg border p-4 text-left shadow-sm transition-colors ${
                    issueType === key ? 'border-gray-900 bg-gray-900 text-white' : 'border-gray-200 bg-white hover:bg-gray-50'
                  }`}
                >
                  <p className={`text-xs font-medium uppercase tracking-wide ${issueType === key ? 'text-gray-300' : 'text-gray-500'}`}>
                    {label}
                  </p>
                  <p className="mt-2 text-2xl font-semibold">{report.breakdown[key] ?? report[countKey] ?? 0}</p>
                </button>
              )
            })}
          </div>

          <ChartPanel title="Affected Records" className="mt-6">
            <div className="mb-3 flex flex-wrap items-center gap-3">
              <select
                value={issueType}
                onChange={(e) => { setIssueType(e.target.value); setPage(1) }}
                className="rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:border-gray-500 focus:outline-none"
              >
                <option value="">All Issue Types</option>
                {Object.entries(CATEGORY_LABELS).map(([key, label]) => (
                  <option key={key} value={key}>{label}</option>
                ))}
              </select>
              <select
                value={entityType}
                onChange={(e) => { setEntityType(e.target.value); setPage(1) }}
                className="rounded-md border border-gray-300 px-3 py-1.5 text-sm capitalize focus:border-gray-500 focus:outline-none"
              >
                <option value="">All Entity Types</option>
                {ENTITY_TYPES.map((t) => (
                  <option key={t} value={t} className="capitalize">{t}</option>
                ))}
              </select>
              {(issueType || entityType) && (
                <button
                  onClick={() => { setIssueType(''); setEntityType(''); setPage(1) }}
                  className="text-xs text-gray-500 underline hover:text-gray-700"
                >
                  Clear filters
                </button>
              )}
            </div>

            {issuesStatus === 'loading' && <LoadingState label="Loading issues…" />}
            {issuesStatus === 'error' && <ErrorState message={issuesError} onRetry={loadIssues} />}
            {issuesStatus === 'ready' && issues.length === 0 && <EmptyState message="No issues match this filter." />}

            {issuesStatus === 'ready' && issues.length > 0 && (
              <>
                <div className="table-scroll overflow-x-auto">
                  <table className="w-full min-w-[700px] text-sm">
                    <thead>
                      <tr className="text-left text-xs uppercase tracking-wide text-gray-500">
                        <th className="py-1.5">Entity</th>
                        <th className="py-1.5">Field</th>
                        <th className="py-1.5">Description</th>
                        <th className="py-1.5">Severity</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                      {issues.map((issue) => (
                        <tr key={issue.id}>
                          <td className="py-1.5">
                            {issue.entity_type === 'property' && issue.entity_id ? (
                              <Link to={`/properties/${issue.entity_id}`} className="capitalize text-gray-900 hover:underline">
                                {issue.entity_type}: {issue.entity_id}
                              </Link>
                            ) : (
                              <span className="capitalize text-gray-600">{issue.entity_type}: {issue.entity_id || '—'}</span>
                            )}
                          </td>
                          <td className="py-1.5 text-gray-500">{issue.field || '—'}</td>
                          <td className="py-1.5 text-gray-600">{issue.description}</td>
                          <td className="py-1.5"><SeverityBadge severity={issue.severity} /></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <Pagination page={page} pageSize={PAGE_SIZE} total={issuesTotal} onPageChange={setPage} />
              </>
            )}
          </ChartPanel>
        </>
      )}
    </div>
  )
}
