import { useEffect, useState } from 'react'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts'
import { getRevenueForecast, getOccupancyForecast } from '../api/client'
import ChartPanel from './ChartPanel'
import { LoadingState, ErrorState, EmptyState } from './States'
import { formatCurrency, formatMonth } from '../utils/format'

const HORIZON_OPTIONS = [3, 6, 12]

// Merges historical + forecast series into one array Recharts can plot as two
// differently-styled lines that visually connect at the handoff point.
function mergeForForChart(historical, forecast) {
  const merged = historical.map((p) => ({ month: p.month, historical: p.value, forecast: null }))
  if (merged.length > 0) {
    // Duplicate the last historical value into the forecast series so the
    // dashed forecast line starts exactly where the solid line ends, instead
    // of leaving a visible gap.
    merged[merged.length - 1].forecast = merged[merged.length - 1].historical
  }
  forecast.forEach((p) => merged.push({ month: p.month, historical: null, forecast: p.value }))
  return merged
}

export default function ForecastPanel() {
  const [metric, setMetric] = useState('revenue')
  const [horizon, setHorizon] = useState(3)
  const [data, setData] = useState(null)
  const [status, setStatus] = useState('loading')
  const [error, setError] = useState(null)

  const load = () => {
    setStatus('loading')
    const fetcher = metric === 'revenue' ? getRevenueForecast : getOccupancyForecast
    fetcher({ horizon_months: horizon })
      .then((d) => { setData(d); setStatus('ready') })
      .catch((err) => { setError(err.message); setStatus('error') })
  }

  useEffect(load, [metric, horizon])

  const valueFormatter = metric === 'revenue' ? (v) => formatCurrency(v) : (v) => `${v?.toFixed(1)}%`

  return (
    <ChartPanel title="Portfolio Forecast" className="lg:col-span-2">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex gap-2">
          {['revenue', 'occupancy'].map((m) => (
            <button
              key={m}
              onClick={() => setMetric(m)}
              className={`rounded-md border px-3 py-1.5 text-xs font-medium capitalize ${
                metric === m ? 'border-gray-900 bg-gray-900 text-white' : 'border-gray-300 text-gray-600 hover:bg-gray-50'
              }`}
            >
              {m}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-500">Forecast horizon:</span>
          {HORIZON_OPTIONS.map((h) => (
            <button
              key={h}
              onClick={() => setHorizon(h)}
              className={`rounded-md border px-2.5 py-1 text-xs font-medium ${
                horizon === h ? 'border-gray-900 bg-gray-900 text-white' : 'border-gray-300 text-gray-600 hover:bg-gray-50'
              }`}
            >
              {h}mo
            </button>
          ))}
        </div>
      </div>

      {status === 'loading' && <LoadingState label="Training model and generating forecast…" />}
      {status === 'error' && <ErrorState message={error} onRetry={load} />}

      {status === 'ready' && data && (
        <>
          {data.note && (
            <div className="mb-3 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-700">
              {data.note}
            </div>
          )}

          {data.historical.length === 0 && data.forecast.length === 0 ? (
            <EmptyState message="No data available to forecast." />
          ) : (
            <ResponsiveContainer width="100%" height={280}>
              <LineChart data={mergeForForChart(data.historical, data.forecast)}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis dataKey="month" tickFormatter={formatMonth} tick={{ fontSize: 12 }} />
                <YAxis tickFormatter={valueFormatter} tick={{ fontSize: 11 }} width={70} />
                <Tooltip formatter={(v) => (v === null ? '—' : valueFormatter(v))} labelFormatter={formatMonth} />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                <Line type="monotone" dataKey="historical" name="Historical" stroke="#334155" strokeWidth={2} dot={false} connectNulls={false} />
                <Line type="monotone" dataKey="forecast" name="Forecast" stroke="#0ea5e9" strokeWidth={2} strokeDasharray="6 4" dot={false} connectNulls={false} />
              </LineChart>
            </ResponsiveContainer>
          )}

          {data.model_performance && (
            <div className="mt-4 grid grid-cols-2 gap-3 border-t border-gray-100 pt-4 text-xs md:grid-cols-4">
              <ModelStat label="MAE" value={metric === 'revenue' ? formatCurrency(data.model_performance.mae) : data.model_performance.mae.toFixed(2)} />
              <ModelStat label="RMSE" value={metric === 'revenue' ? formatCurrency(data.model_performance.rmse) : data.model_performance.rmse.toFixed(2)} />
              <ModelStat label="R²" value={data.model_performance.r2.toFixed(3)} />
              <ModelStat label="Evaluated on" value={`${data.model_performance.test_rows} rows since ${data.model_performance.test_cutoff_month}`} />
            </div>
          )}

          <p className="mt-3 text-[11px] leading-relaxed text-gray-400">{data.disclaimer}</p>
        </>
      )}
    </ChartPanel>
  )
}

function ModelStat({ label, value }) {
  return (
    <div>
      <p className="text-gray-400">{label}</p>
      <p className="font-medium text-gray-700">{value}</p>
    </div>
  )
}
