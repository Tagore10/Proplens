import { useEffect, useState } from 'react'
import {
  LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts'
import { getPortfolioAnalytics, getRevenueAnalytics, getOccupancyAnalytics } from '../api/client'
import PageHeader from '../components/PageHeader'
import KpiCard from '../components/KpiCard'
import ChartPanel from '../components/ChartPanel'
import ForecastPanel from '../components/ForecastPanel'
import { LoadingState, ErrorState, EmptyState } from '../components/States'
import { formatCurrency, formatPercent, formatMonth } from '../utils/format'

export default function Analytics() {
  const [portfolio, setPortfolio] = useState(null)
  const [revenue, setRevenue] = useState(null)
  const [occupancy, setOccupancy] = useState(null)
  const [status, setStatus] = useState('loading')
  const [error, setError] = useState(null)

  const load = () => {
    setStatus('loading')
    Promise.all([getPortfolioAnalytics(), getRevenueAnalytics(), getOccupancyAnalytics()])
      .then(([p, r, o]) => {
        setPortfolio(p)
        setRevenue(r)
        setOccupancy(o)
        setStatus('ready')
      })
      .catch((err) => { setError(err.message); setStatus('error') })
  }

  useEffect(load, [])

  if (status === 'loading') return <LoadingState label="Loading analytics…" />
  if (status === 'error') return <ErrorState message={error} onRetry={load} />
  if (!portfolio) return <EmptyState />

  const growthTone = (v) => (v === null || v === undefined ? 'default' : v >= 0 ? 'good' : 'danger')
  const formatGrowth = (v) => (v === null || v === undefined ? 'Not enough history' : `${v > 0 ? '+' : ''}${v.toFixed(2)}%`)

  return (
    <div>
      <PageHeader title="Analytics" subtitle="Portfolio financial performance and trends" />

      {/* Financial KPIs */}
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <KpiCard label="Total Revenue" value={formatCurrency(portfolio.total_revenue)} />
        <KpiCard label="Total Operating Expenses" value={formatCurrency(portfolio.total_operating_expenses)} />
        <KpiCard label="Net Operating Income" value={formatCurrency(portfolio.net_operating_income)} />
        <KpiCard label="NOI Margin" value={formatPercent(portfolio.noi_margin_pct)} />
        <KpiCard label="Operating Expense Ratio" value={formatPercent(portfolio.operating_expense_ratio_pct)} />
        <KpiCard label="Average Occupancy" value={formatPercent(portfolio.average_occupancy)} />
        <KpiCard
          label="Revenue Growth (MoM)"
          value={formatGrowth(portfolio.revenue_growth_mom_pct)}
          tone={growthTone(portfolio.revenue_growth_mom_pct)}
        />
        <KpiCard
          label="Revenue Growth (3-mo)"
          value={formatGrowth(portfolio.revenue_growth_3mo_pct)}
          tone={growthTone(portfolio.revenue_growth_3mo_pct)}
        />
      </div>

      {/* Trends */}
      <div className="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <ChartPanel title="Monthly Revenue Trend">
          {revenue.monthly_trend.length === 0 ? (
            <EmptyState message="No revenue history available." />
          ) : (
            <ResponsiveContainer width="100%" height={240}>
              <LineChart data={revenue.monthly_trend}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis dataKey="month" tickFormatter={formatMonth} tick={{ fontSize: 12 }} />
                <YAxis tickFormatter={(v) => formatCurrency(v)} tick={{ fontSize: 11 }} width={70} />
                <Tooltip formatter={(v) => formatCurrency(v)} labelFormatter={formatMonth} />
                <Line type="monotone" dataKey="revenue" stroke="#334155" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          )}
        </ChartPanel>

        <ChartPanel title="Monthly Occupancy Trend">
          {occupancy.monthly_trend.length === 0 ? (
            <EmptyState message="No occupancy history available." />
          ) : (
            <ResponsiveContainer width="100%" height={240}>
              <LineChart data={occupancy.monthly_trend}>
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
          {portfolio.revenue_by_city.length === 0 ? (
            <EmptyState message="No city data available." />
          ) : (
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={portfolio.revenue_by_city} layout="vertical" margin={{ left: 20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis type="number" tickFormatter={(v) => formatCurrency(v)} tick={{ fontSize: 11 }} />
                <YAxis type="category" dataKey="city" tick={{ fontSize: 12 }} width={80} />
                <Tooltip formatter={(v) => formatCurrency(v)} />
                <Bar dataKey="revenue" fill="#334155" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </ChartPanel>

        <ChartPanel title="Revenue by Property Type">
          {portfolio.revenue_by_property_type.length === 0 ? (
            <EmptyState message="No property type data available." />
          ) : (
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={portfolio.revenue_by_property_type}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis dataKey="property_type" tick={{ fontSize: 11 }} />
                <YAxis tickFormatter={(v) => formatCurrency(v)} tick={{ fontSize: 11 }} width={70} />
                <Tooltip formatter={(v) => formatCurrency(v)} />
                <Bar dataKey="revenue" fill="#6366f1" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </ChartPanel>

        <ChartPanel title="Occupancy by Property Type" className="lg:col-span-2">
          {portfolio.occupancy_by_property_type.length === 0 ? (
            <EmptyState message="No property type data available." />
          ) : (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={portfolio.occupancy_by_property_type}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis dataKey="property_type" tick={{ fontSize: 12 }} />
                <YAxis tickFormatter={(v) => `${v}%`} tick={{ fontSize: 11 }} domain={[0, 100]} />
                <Tooltip formatter={(v) => `${v}%`} />
                <Bar dataKey="avg_occupancy" fill="#0ea5e9" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </ChartPanel>

        <ForecastPanel />
      </div>
    </div>
  )
}
