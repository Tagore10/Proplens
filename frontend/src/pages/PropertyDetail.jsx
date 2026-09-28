import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'
import { getPropertyDetail, getPropertyRiskDetail } from '../api/client'
import PageHeader from '../components/PageHeader'
import RiskBadge from '../components/RiskBadge'
import { LeaseStatusBadge } from '../components/Badges'
import ChartPanel from '../components/ChartPanel'
import { LoadingState, ErrorState, EmptyState } from '../components/States'
import { formatCurrency, formatPercent, formatDate, formatMonth } from '../utils/format'

export default function PropertyDetail() {
  const { propertyId } = useParams()
  const [property, setProperty] = useState(null)
  const [risk, setRisk] = useState(null)
  const [status, setStatus] = useState('loading')
  const [error, setError] = useState(null)

  const load = () => {
    setStatus('loading')
    Promise.all([getPropertyDetail(propertyId), getPropertyRiskDetail(propertyId)])
      .then(([p, r]) => {
        setProperty(p)
        setRisk(r)
        setStatus('ready')
      })
      .catch((err) => {
        setError(err.response?.status === 404 ? `Property '${propertyId}' not found` : err.message)
        setStatus('error')
      })
  }

  useEffect(load, [propertyId])

  if (status === 'loading') return <LoadingState label="Loading property…" />
  if (status === 'error') return <ErrorState message={error} onRetry={load} />
  if (!property) return <EmptyState />

  return (
    <div>
      <Link to="/properties" className="text-sm text-gray-500 hover:text-gray-700">← Back to Properties</Link>

      <div className="mt-2 flex items-start justify-between">
        <PageHeader
          title={property.name}
          subtitle={`${property.id} · ${property.city || 'Unknown city'}, ${property.state || '—'} · ${property.property_type || 'Unknown type'}`}
        />
        <RiskBadge category={property.risk_category} />
      </div>

      {/* Core metrics */}
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <Metric label="Occupancy" value={formatPercent(property.occupancy_pct)} />
        <Metric label="Annual Revenue" value={formatCurrency(property.annual_revenue)} />
        <Metric label="Operating Expenses" value={formatCurrency(property.operating_expenses)} />
        <Metric label="Net Operating Income" value={formatCurrency(property.net_operating_income)} />
        <Metric label="Property Value" value={formatCurrency(property.property_value)} />
        <Metric label="Area" value={property.area_sqft ? `${property.area_sqft.toLocaleString('en-IN')} sq ft` : '—'} />
        <Metric label="Tenants" value={property.num_tenants} />
        <Metric label="Risk Score" value={property.risk_score ?? '—'} />
      </div>

      {/* Risk breakdown */}
      {risk && (
        <ChartPanel title="Risk Factor Breakdown" className="mt-6">
          {risk.reasons.length > 0 && (
            <ul className="mb-4 list-inside list-disc space-y-1 text-sm text-gray-700">
              {risk.reasons.map((r, i) => (
                <li key={i}>{r}</li>
              ))}
            </ul>
          )}
          <div className="space-y-2">
            {risk.factors.map((f) => (
              <div key={f.name} className="flex items-center gap-3">
                <span className="w-36 shrink-0 text-xs capitalize text-gray-500">{f.name.replace('_', ' ')}</span>
                <div className="h-2 flex-1 rounded-full bg-gray-100">
                  <div
                    className="h-2 rounded-full bg-gray-700"
                    style={{ width: `${f.value}%` }}
                  />
                </div>
                <span className="w-24 shrink-0 text-right text-xs text-gray-500">
                  {f.value.toFixed(0)} × {(f.weight * 100).toFixed(0)}% = {f.contribution.toFixed(1)}
                </span>
              </div>
            ))}
          </div>
        </ChartPanel>
      )}

      {/* History charts */}
      <div className="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <ChartPanel title="Revenue History (12 months)">
          {property.history.length === 0 ? (
            <EmptyState message="No history available." />
          ) : (
            <ResponsiveContainer width="100%" height={220}>
              <LineChart data={property.history}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis dataKey="month" tickFormatter={formatMonth} tick={{ fontSize: 11 }} />
                <YAxis tickFormatter={(v) => formatCurrency(v)} tick={{ fontSize: 10 }} width={70} />
                <Tooltip formatter={(v) => formatCurrency(v)} labelFormatter={formatMonth} />
                <Line type="monotone" dataKey="revenue" stroke="#334155" strokeWidth={2} dot={false} connectNulls />
              </LineChart>
            </ResponsiveContainer>
          )}
        </ChartPanel>
        <ChartPanel title="Occupancy History (12 months)">
          {property.history.length === 0 ? (
            <EmptyState message="No history available." />
          ) : (
            <ResponsiveContainer width="100%" height={220}>
              <LineChart data={property.history}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis dataKey="month" tickFormatter={formatMonth} tick={{ fontSize: 11 }} />
                <YAxis tickFormatter={(v) => `${v}%`} tick={{ fontSize: 10 }} width={45} domain={[0, 100]} />
                <Tooltip formatter={(v) => `${v}%`} labelFormatter={formatMonth} />
                <Line type="monotone" dataKey="occupancy_pct" stroke="#0ea5e9" strokeWidth={2} dot={false} connectNulls />
              </LineChart>
            </ResponsiveContainer>
          )}
        </ChartPanel>
      </div>

      {/* Tenants */}
      <ChartPanel title={`Tenants (${property.tenants.length})`} className="mt-6">
        {property.tenants.length === 0 ? (
          <EmptyState message="No tenants on file." />
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs uppercase tracking-wide text-gray-500">
                <th className="py-1.5">Tenant</th>
                <th className="py-1.5">Industry</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {property.tenants.map((t) => (
                <tr key={t.id}>
                  <td className="py-1.5">{t.tenant_name}</td>
                  <td className="py-1.5 text-gray-500">{t.industry || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </ChartPanel>

      {/* Leases */}
      <ChartPanel title={`Leases (${property.leases.length})`} className="mt-6">
        {property.leases.length === 0 ? (
          <EmptyState message="No leases on file." />
        ) : (
          <div className="table-scroll overflow-x-auto">
            <table className="w-full min-w-[640px] text-sm">
              <thead>
                <tr className="text-left text-xs uppercase tracking-wide text-gray-500">
                  <th className="py-1.5">Tenant</th>
                  <th className="py-1.5">Start</th>
                  <th className="py-1.5">End</th>
                  <th className="py-1.5">Annual Rent</th>
                  <th className="py-1.5">Days to Expiry</th>
                  <th className="py-1.5">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {property.leases.map((l) => (
                  <tr key={l.id}>
                    <td className="py-1.5">{l.tenant_name || '—'}</td>
                    <td className="py-1.5 text-gray-500">{formatDate(l.lease_start)}</td>
                    <td className="py-1.5 text-gray-500">{formatDate(l.lease_end)}</td>
                    <td className="py-1.5 text-gray-500">{formatCurrency(l.annual_rent)}</td>
                    <td className="py-1.5 text-gray-500">{l.days_to_expiry ?? '—'}</td>
                    <td className="py-1.5"><LeaseStatusBadge status={l.lease_status} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </ChartPanel>
    </div>
  )
}

function Metric({ label, value }) {
  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
      <p className="text-xs font-medium uppercase tracking-wide text-gray-500">{label}</p>
      <p className="mt-1 text-lg font-semibold text-gray-900">{value}</p>
    </div>
  )
}
