import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { getProperties, getPropertyFilterOptions } from '../api/client'
import PageHeader from '../components/PageHeader'
import RiskBadge from '../components/RiskBadge'
import Pagination from '../components/Pagination'
import { LoadingState, ErrorState, EmptyState } from '../components/States'
import { formatCurrency, formatPercent } from '../utils/format'

const PAGE_SIZE = 15

export default function Properties() {
  const [rows, setRows] = useState([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [status, setStatus] = useState('loading')
  const [error, setError] = useState(null)

  const [filterOptions, setFilterOptions] = useState({ cities: [], property_types: [], risk_categories: [] })

  const [search, setSearch] = useState('')
  const [city, setCity] = useState('')
  const [propertyType, setPropertyType] = useState('')
  const [riskCategory, setRiskCategory] = useState('')
  const [sortBy, setSortBy] = useState('name')
  const [sortDir, setSortDir] = useState('asc')

  useEffect(() => {
    getPropertyFilterOptions().then(setFilterOptions).catch(() => {})
  }, [])

  const load = () => {
    setStatus('loading')
    getProperties({
      search: search || undefined,
      city: city || undefined,
      property_type: propertyType || undefined,
      risk_category: riskCategory || undefined,
      sort_by: sortBy,
      sort_dir: sortDir,
      page,
      page_size: PAGE_SIZE,
    })
      .then((d) => {
        setRows(d.properties)
        setTotal(d.total)
        setStatus('ready')
      })
      .catch((err) => {
        setError(err.message)
        setStatus('error')
      })
  }

  useEffect(load, [search, city, propertyType, riskCategory, sortBy, sortDir, page])

  // Any filter change should reset to page 1
  const updateFilter = (setter) => (value) => {
    setter(value)
    setPage(1)
  }

  const toggleSort = (field) => {
    if (sortBy === field) {
      setSortDir(sortDir === 'asc' ? 'desc' : 'asc')
    } else {
      setSortBy(field)
      setSortDir('asc')
    }
    setPage(1)
  }

  const SortHeader = ({ field, children }) => (
    <th
      className="cursor-pointer select-none px-4 py-2 text-left text-xs font-medium uppercase tracking-wide text-gray-500 hover:text-gray-700"
      onClick={() => toggleSort(field)}
    >
      {children} {sortBy === field ? (sortDir === 'asc' ? '↑' : '↓') : ''}
    </th>
  )

  return (
    <div>
      <PageHeader title="Properties" subtitle={`${total} properties in the portfolio`} />

      {/* Filters */}
      <div className="mb-4 flex flex-wrap gap-3">
        <input
          type="text"
          placeholder="Search name or city…"
          value={search}
          onChange={(e) => updateFilter(setSearch)(e.target.value)}
          className="w-56 rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:border-gray-500 focus:outline-none"
        />
        <select
          value={city}
          onChange={(e) => updateFilter(setCity)(e.target.value)}
          className="rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:border-gray-500 focus:outline-none"
        >
          <option value="">All Cities</option>
          {filterOptions.cities.map((c) => (
            <option key={c} value={c}>{c}</option>
          ))}
        </select>
        <select
          value={propertyType}
          onChange={(e) => updateFilter(setPropertyType)(e.target.value)}
          className="rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:border-gray-500 focus:outline-none"
        >
          <option value="">All Types</option>
          {filterOptions.property_types.map((t) => (
            <option key={t} value={t}>{t}</option>
          ))}
        </select>
        <select
          value={riskCategory}
          onChange={(e) => updateFilter(setRiskCategory)(e.target.value)}
          className="rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:border-gray-500 focus:outline-none"
        >
          <option value="">All Risk Levels</option>
          {filterOptions.risk_categories.map((r) => (
            <option key={r} value={r}>{r}</option>
          ))}
        </select>
      </div>

      <div className="overflow-hidden rounded-lg border border-gray-200 bg-white shadow-sm">
        {status === 'loading' && <LoadingState label="Loading properties…" />}
        {status === 'error' && <ErrorState message={error} onRetry={load} />}
        {status === 'ready' && rows.length === 0 && <EmptyState message="No properties match these filters." />}

        {status === 'ready' && rows.length > 0 && (
          <>
            <div className="table-scroll overflow-x-auto">
              <table className="w-full min-w-[900px] divide-y divide-gray-200 text-sm">
                <thead className="bg-gray-50">
                  <tr>
                    <SortHeader field="name">Property</SortHeader>
                    <SortHeader field="city">City</SortHeader>
                    <th className="px-4 py-2 text-left text-xs font-medium uppercase tracking-wide text-gray-500">Type</th>
                    <SortHeader field="occupancy_pct">Occupancy</SortHeader>
                    <SortHeader field="annual_revenue">Annual Revenue</SortHeader>
                    <SortHeader field="property_value">Value</SortHeader>
                    <th className="px-4 py-2 text-left text-xs font-medium uppercase tracking-wide text-gray-500">Tenants</th>
                    <th className="px-4 py-2 text-left text-xs font-medium uppercase tracking-wide text-gray-500">Risk</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {rows.map((p) => (
                    <tr key={p.id} className="hover:bg-gray-50">
                      <td className="px-4 py-2.5">
                        <Link to={`/properties/${p.id}`} className="font-medium text-gray-900 hover:underline">
                          {p.name}
                        </Link>
                        <div className="text-xs text-gray-400">{p.id}</div>
                      </td>
                      <td className="px-4 py-2.5 text-gray-600">{p.city || '—'}</td>
                      <td className="px-4 py-2.5 text-gray-600">{p.property_type || '—'}</td>
                      <td className="px-4 py-2.5 text-gray-600">{formatPercent(p.occupancy_pct)}</td>
                      <td className="px-4 py-2.5 text-gray-600">{formatCurrency(p.annual_revenue)}</td>
                      <td className="px-4 py-2.5 text-gray-600">{formatCurrency(p.property_value)}</td>
                      <td className="px-4 py-2.5 text-gray-600">{p.num_tenants}</td>
                      <td className="px-4 py-2.5"><RiskBadge category={p.risk_category} /></td>
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
