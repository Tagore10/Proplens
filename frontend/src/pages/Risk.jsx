import { useEffect, useState, Fragment } from 'react'
import { Link } from 'react-router-dom'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import { getRiskProperties } from '../api/client'
import PageHeader from '../components/PageHeader'
import ChartPanel from '../components/ChartPanel'
import RiskBadge from '../components/RiskBadge'
import Pagination from '../components/Pagination'
import { LoadingState, ErrorState, EmptyState } from '../components/States'

const PAGE_SIZE = 15
const RISK_COLORS = { Low: '#10b981', Medium: '#f59e0b', High: '#ef4444' }

const FACTOR_LABELS = {
  occupancy: 'Occupancy',
  lease_expiry: 'Lease Expiry',
  revenue_trend: 'Revenue Trend',
  opex: 'Operating Expense',
  data_quality: 'Data Quality',
}

export default function Risk() {
  const [summary, setSummary] = useState(null)
  const [rows, setRows] = useState([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [status, setStatus] = useState('loading')
  const [error, setError] = useState(null)
  const [categoryFilter, setCategoryFilter] = useState('')
  const [expandedId, setExpandedId] = useState(null)

  const load = () => {
    setStatus('loading')
    getRiskProperties({ risk_category: categoryFilter || undefined, page, page_size: PAGE_SIZE })
      .then((d) => {
        setSummary({ total_properties: d.total_properties, low_risk: d.low_risk, medium_risk: d.medium_risk, high_risk: d.high_risk })
        setRows(d.properties)
        setTotal(d.total)
        setStatus('ready')
      })
      .catch((err) => { setError(err.message); setStatus('error') })
  }

  useEffect(load, [categoryFilter, page])

  const distributionData = summary
    ? [
        { category: 'Low', count: summary.low_risk },
        { category: 'Medium', count: summary.medium_risk },
        { category: 'High', count: summary.high_risk },
      ]
    : []

  return (
    <div>
      <PageHeader title="Risk" subtitle="Explainable, weighted property risk scoring" />

      {status === 'loading' && !summary && <LoadingState label="Running risk scan…" />}
      {status === 'error' && <ErrorState message={error} onRetry={load} />}

      {summary && (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
          <ChartPanel title="Portfolio Risk Distribution" className="lg:col-span-1">
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={distributionData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis dataKey="category" tick={{ fontSize: 12 }} />
                <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
                <Tooltip />
                <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                  {distributionData.map((entry) => (
                    <Cell key={entry.category} fill={RISK_COLORS[entry.category]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </ChartPanel>

          <div className="grid grid-cols-3 gap-4 lg:col-span-2">
            <SummaryCard label="Low Risk" value={summary.low_risk} tone="good" />
            <SummaryCard label="Medium Risk" value={summary.medium_risk} tone="warning" />
            <SummaryCard label="High Risk" value={summary.high_risk} tone="danger" />
          </div>
        </div>
      )}

      <div className="mt-6 mb-4 flex flex-wrap gap-3">
        {['', 'Low', 'Medium', 'High'].map((c) => (
          <button
            key={c || 'all'}
            onClick={() => { setCategoryFilter(c); setPage(1) }}
            className={`rounded-md border px-3 py-1.5 text-xs font-medium ${
              categoryFilter === c ? 'border-gray-900 bg-gray-900 text-white' : 'border-gray-300 text-gray-600 hover:bg-gray-50'
            }`}
          >
            {c || 'All'}
          </button>
        ))}
      </div>

      <div className="overflow-hidden rounded-lg border border-gray-200 bg-white shadow-sm">
        {status === 'loading' && summary && <LoadingState label="Loading…" />}
        {status === 'ready' && rows.length === 0 && <EmptyState message="No properties match this filter." />}

        {status === 'ready' && rows.length > 0 && (
          <>
            <table className="w-full text-sm">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-2 text-left text-xs font-medium uppercase tracking-wide text-gray-500">Property</th>
                  <th className="px-4 py-2 text-left text-xs font-medium uppercase tracking-wide text-gray-500">Score</th>
                  <th className="px-4 py-2 text-left text-xs font-medium uppercase tracking-wide text-gray-500">Category</th>
                  <th className="px-4 py-2 text-left text-xs font-medium uppercase tracking-wide text-gray-500">Top Reasons</th>
                  <th className="px-4 py-2"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {rows.map((r) => (
                  <Fragment key={r.property_id}>
                    <tr className="hover:bg-gray-50">
                      <td className="px-4 py-2.5">
                        <Link to={`/properties/${r.property_id}`} className="font-medium text-gray-900 hover:underline">
                          {r.property_name}
                        </Link>
                      </td>
                      <td className="px-4 py-2.5 text-gray-600">{r.risk_score.toFixed(1)}</td>
                      <td className="px-4 py-2.5"><RiskBadge category={r.risk_category} /></td>
                      <td className="px-4 py-2.5 text-xs text-gray-500">
                        {r.reasons.length > 0 ? r.reasons.join(' · ') : 'No major risk factors'}
                      </td>
                      <td className="px-4 py-2.5 text-right">
                        <button
                          onClick={() => setExpandedId(expandedId === r.property_id ? null : r.property_id)}
                          className="text-xs text-gray-500 underline hover:text-gray-700"
                        >
                          {expandedId === r.property_id ? 'Hide' : 'Factors'}
                        </button>
                      </td>
                    </tr>
                    {expandedId === r.property_id && (
                      <tr className="bg-gray-50">
                        <td colSpan={5} className="px-4 py-3">
                          <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
                            {Object.entries(r.factors).map(([name, f]) => (
                              <div key={name} className="rounded-md border border-gray-200 bg-white p-2">
                                <p className="text-xs text-gray-500">{FACTOR_LABELS[name] || name}</p>
                                <p className="text-sm font-semibold text-gray-900">{f.value.toFixed(0)}</p>
                                <p className="text-[10px] text-gray-400">weight {(f.weight * 100).toFixed(0)}%</p>
                              </div>
                            ))}
                          </div>
                        </td>
                      </tr>
                    )}
                  </Fragment>
                ))}
              </tbody>
            </table>
            <Pagination page={page} pageSize={PAGE_SIZE} total={total} onPageChange={setPage} />
          </>
        )}
      </div>
    </div>
  )
}

function SummaryCard({ label, value, tone }) {
  const toneClass = { good: 'text-emerald-700', warning: 'text-amber-700', danger: 'text-red-700' }[tone]
  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
      <p className="text-xs font-medium uppercase tracking-wide text-gray-500">{label}</p>
      <p className={`mt-2 text-2xl font-semibold ${toneClass}`}>{value}</p>
    </div>
  )
}
