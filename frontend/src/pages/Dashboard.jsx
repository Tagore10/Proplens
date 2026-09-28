import { useEffect, useState } from 'react'
import {
  LineChart, Line, BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts'
import { getDashboardSummary } from '../api/client'
import PageHeader from '../components/PageHeader'
import KpiCard from '../components/KpiCard'
import ChartPanel from '../components/ChartPanel'
import { LoadingState, ErrorState, EmptyState } from '../components/States'
import { formatCurrency, formatPercent, formatMonth } from '../utils/format'

const RISK_COLORS = { Low: '#10b981', Medium: '#f59e0b', High: '#ef4444' }
const TYPE_COLORS = ['#334155', '#64748b', '#94a3b8', '#0ea5e9', '#6366f1']

export default function Dashboard() {
  const [data, setData] = useState(null)
  const [status, setStatus] = useState('loading') // loading | error | ready
  const [error, setError] = useState(null)

  const load = () => {
    setStatus('loading')
    getDashboardSummary()
      .then((d) => {
        setData(d)
        setStatus('ready')
      })
      .catch((err) => {
        setError(err.message)
        setStatus('error')
      })
  }

  useEffect(load, [])

  if (status === 'loading') return <LoadingState label="Loading dashboard…" />
  if (status === 'error') return <ErrorState message={error} onRetry={load} />
  if (!data) return <EmptyState />

  return (
    <div>
      <PageHeader title="Dashboard" subtitle="Portfolio overview — synthetic demo data" />

      {/* KPI Cards */}
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <KpiCard label="Total Properties" value={data.total_properties} />
        <KpiCard label="Portfolio Value" value={formatCurrency(data.total_portfolio_value)} />
        <KpiCard label="Annual Revenue" value={formatCurrency(data.annual_revenue)} />
        <KpiCard label="Avg. Occupancy" value={formatPercent(data.average_occupancy)} />
        <KpiCard
          label="High Risk Properties"
          value={data.high_risk_properties}
          tone={data.high_risk_properties > 0 ? 'danger' : 'good'}
        />
        <KpiCard
          label="Leases Expiring (90d)"
          value={data.leases_expiring_90_days}
          tone={data.leases_expiring_90_days > 0 ? 'warning' : 'good'}
        />
        <KpiCard
          label="Data Quality Score"
          value={formatPercent(data.data_quality_score)}
          tone={data.data_quality_score >= 70 ? 'good' : data.data_quality_score >= 50 ? 'warning' : 'danger'}
        />
      </div>

      {/* Charts */}
      <div className="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <ChartPanel title="Revenue Trend (12 months)">
          {data.revenue_by_month.length === 0 ? (
            <EmptyState message="No revenue history available." />
          ) : (
            <ResponsiveContainer width="100%" height={260}>
              <LineChart data={data.revenue_by_month}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis dataKey="month" tickFormatter={formatMonth} tick={{ fontSize: 12 }} />
                <YAxis tickFormatter={(v) => formatCurrency(v)} tick={{ fontSize: 11 }} width={70} />
                <Tooltip formatter={(v) => formatCurrency(v)} labelFormatter={formatMonth} />
                <Line type="monotone" dataKey="revenue" stroke="#334155" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          )}
        </ChartPanel>

        <ChartPanel title="Occupancy Trend (12 months)">
          {data.occupancy_trend.length === 0 ? (
            <EmptyState message="No occupancy history available." />
          ) : (
            <ResponsiveContainer width="100%" height={260}>
              <LineChart data={data.occupancy_trend}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis dataKey="month" tickFormatter={formatMonth} tick={{ fontSize: 12 }} />
                <YAxis tickFormatter={(v) => `${v}%`} tick={{ fontSize: 11 }} width={45} domain={[0, 100]} />
                <Tooltip formatter={(v) => `${v}%`} labelFormatter={formatMonth} />
                <Line type="monotone" dataKey="avg_occupancy" stroke="#0ea5e9" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          )}
        </ChartPanel>

        <ChartPanel title="Revenue by City">
          {data.revenue_by_city.length === 0 ? (
            <EmptyState message="No city data available." />
          ) : (
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={data.revenue_by_city} layout="vertical" margin={{ left: 20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis type="number" tickFormatter={(v) => formatCurrency(v)} tick={{ fontSize: 11 }} />
                <YAxis type="category" dataKey="city" tick={{ fontSize: 12 }} width={80} />
                <Tooltip formatter={(v) => formatCurrency(v)} />
                <Bar dataKey="revenue" fill="#334155" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </ChartPanel>

        <ChartPanel title="Property Type Distribution">
          {data.property_type_distribution.length === 0 ? (
            <EmptyState message="No property type data available." />
          ) : (
            <ResponsiveContainer width="100%" height={260}>
              <PieChart>
                <Pie
                  data={data.property_type_distribution}
                  dataKey="count"
                  nameKey="type"
                  cx="50%"
                  cy="50%"
                  outerRadius={90}
                  label={(entry) => entry.type}
                >
                  {data.property_type_distribution.map((entry, i) => (
                    <Cell key={entry.type} fill={TYPE_COLORS[i % TYPE_COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          )}
        </ChartPanel>

        <ChartPanel title="Risk Distribution">
          {data.risk_distribution.length === 0 ? (
            <EmptyState message="No risk data available." />
          ) : (
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={data.risk_distribution}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis dataKey="category" tick={{ fontSize: 12 }} />
                <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
                <Tooltip />
                <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                  {data.risk_distribution.map((entry) => (
                    <Cell key={entry.category} fill={RISK_COLORS[entry.category] || '#94a3b8'} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )}
        </ChartPanel>

        <ChartPanel title="Lease Expirations (next 12 months)">
          {data.lease_expirations_by_month.length === 0 ? (
            <EmptyState message="No upcoming lease expirations." />
          ) : (
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={data.lease_expirations_by_month}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis dataKey="month" tick={{ fontSize: 11 }} />
                <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
                <Tooltip />
                <Bar dataKey="expiring_leases" fill="#f59e0b" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </ChartPanel>
      </div>
    </div>
  )
}
