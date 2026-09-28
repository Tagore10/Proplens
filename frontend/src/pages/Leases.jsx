import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { getLeases } from '../api/client'
import PageHeader from '../components/PageHeader'
import { LeaseStatusBadge } from '../components/Badges'
import Pagination from '../components/Pagination'
import { LoadingState, ErrorState, EmptyState } from '../components/States'
import { formatCurrency, formatDate } from '../utils/format'

const PAGE_SIZE = 20
const STATUS_OPTIONS = ['Active', 'Expiring Soon', 'Expired']

export default function Leases() {
  const [rows, setRows] = useState([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [status, setStatus] = useState('loading')
  const [error, setError] = useState(null)

  const [statusFilter, setStatusFilter] = useState('')
  const [sortBy, setSortBy] = useState('lease_end')
  const [sortDir, setSortDir] = useState('asc')

  const load = () => {
    setStatus('loading')
    getLeases({
      status: statusFilter || undefined,
      sort_by: sortBy,
      sort_dir: sortDir,
      page,
      page_size: PAGE_SIZE,
    })
      .then((d) => {
        setRows(d.leases)
        setTotal(d.total)
        setStatus('ready')
      })
      .catch((err) => {
        setError(err.message)
        setStatus('error')
      })
  }

  useEffect(load, [statusFilter, sortBy, sortDir, page])

  const toggleSort = (field) => {
    if (sortBy === field) {
      setSortDir(sortDir === 'asc' ? 'desc' : 'asc')
    } else {
      setSortBy(field)
      setSortDir('asc')
    }
    setPage(1)
  }

  return (
    <div>
      <PageHeader title="Leases" subtitle={`${total} leases across the portfolio`} />

      <div className="mb-4 flex flex-wrap gap-3">
        <select
          value={statusFilter}
          onChange={(e) => { setStatusFilter(e.target.value); setPage(1) }}
          className="rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:border-gray-500 focus:outline-none"
        >
          <option value="">All Statuses</option>
          {STATUS_OPTIONS.map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
        <select
          value={sortBy}
          onChange={(e) => { setSortBy(e.target.value); setPage(1) }}
          className="rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:border-gray-500 focus:outline-none"
        >
          <option value="lease_end">Sort by Lease End</option>
          <option value="lease_start">Sort by Lease Start</option>
          <option value="annual_rent">Sort by Annual Rent</option>
        </select>
        <button
          onClick={() => toggleSort(sortBy)}
          className="rounded-md border border-gray-300 px-3 py-1.5 text-xs font-medium text-gray-600 hover:bg-gray-50"
        >
          {sortDir === 'asc' ? '↑ Ascending' : '↓ Descending'}
        </button>
      </div>

      <div className="overflow-hidden rounded-lg border border-gray-200 bg-white shadow-sm">
        {status === 'loading' && <LoadingState label="Loading leases…" />}
        {status === 'error' && <ErrorState message={error} onRetry={load} />}
        {status === 'ready' && rows.length === 0 && <EmptyState message="No leases match this filter." />}

        {status === 'ready' && rows.length > 0 && (
          <>
            <div className="table-scroll overflow-x-auto">
              <table className="w-full min-w-[900px] divide-y divide-gray-200 text-sm">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-4 py-2 text-left text-xs font-medium uppercase tracking-wide text-gray-500">Property</th>
                    <th className="px-4 py-2 text-left text-xs font-medium uppercase tracking-wide text-gray-500">Tenant</th>
                    <th className="px-4 py-2 text-left text-xs font-medium uppercase tracking-wide text-gray-500">Start</th>
                    <th className="px-4 py-2 text-left text-xs font-medium uppercase tracking-wide text-gray-500">End</th>
                    <th className="px-4 py-2 text-left text-xs font-medium uppercase tracking-wide text-gray-500">Annual Rent</th>
                    <th className="px-4 py-2 text-left text-xs font-medium uppercase tracking-wide text-gray-500">Days to Expiry</th>
                    <th className="px-4 py-2 text-left text-xs font-medium uppercase tracking-wide text-gray-500">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {rows.map((l) => (
                    <tr key={l.id} className="hover:bg-gray-50">
                      <td className="px-4 py-2.5">
                        {l.property_id ? (
                          <Link to={`/properties/${l.property_id}`} className="font-medium text-gray-900 hover:underline">
                            {l.property_name || l.property_id}
                          </Link>
                        ) : (
                          <span className="text-gray-400">—</span>
                        )}
                      </td>
                      <td className="px-4 py-2.5 text-gray-600">{l.tenant_name || '—'}</td>
                      <td className="px-4 py-2.5 text-gray-600">{formatDate(l.lease_start)}</td>
                      <td className="px-4 py-2.5 text-gray-600">{formatDate(l.lease_end)}</td>
                      <td className="px-4 py-2.5 text-gray-600">{formatCurrency(l.annual_rent)}</td>
                      <td className="px-4 py-2.5 text-gray-600">{l.days_to_expiry ?? '—'}</td>
                      <td className="px-4 py-2.5"><LeaseStatusBadge status={l.lease_status} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pagination page={page} pageSize={PAGE_SIZE} total={total} onPageChange={setPage} />
          </>
        )}
      </div>
    </div>
  )
}
