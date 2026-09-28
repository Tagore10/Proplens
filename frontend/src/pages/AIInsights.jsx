import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { askInsightQuestion, getInsightExamples } from '../api/client'
import PageHeader from '../components/PageHeader'
import ChartPanel from '../components/ChartPanel'
import { LoadingState, ErrorState, EmptyState } from '../components/States'

const CATEGORY_STYLES = {
  portfolio_kpi: 'bg-slate-50 text-slate-700 ring-slate-600/20',
  risk: 'bg-red-50 text-red-700 ring-red-600/20',
  lease: 'bg-amber-50 text-amber-700 ring-amber-600/20',
  data_quality: 'bg-purple-50 text-purple-700 ring-purple-600/20',
  analytics: 'bg-blue-50 text-blue-700 ring-blue-600/20',
  forecast: 'bg-sky-50 text-sky-700 ring-sky-600/20',
  property_detail: 'bg-emerald-50 text-emerald-700 ring-emerald-600/20',
  unsupported: 'bg-gray-100 text-gray-600 ring-gray-500/20',
  not_found: 'bg-gray-100 text-gray-600 ring-gray-500/20',
}

export default function AIInsights() {
  const [examples, setExamples] = useState([])
  const [provider, setProvider] = useState(null)
  const [question, setQuestion] = useState('')
  const [status, setStatus] = useState('idle') // idle | loading | done | error
  const [answer, setAnswer] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    getInsightExamples()
      .then((d) => { setExamples(d.examples); setProvider(d.provider) })
      .catch(() => {})
  }, [])

  const ask = (q) => {
    const text = (q ?? question).trim()
    if (!text) return
    setQuestion(text)
    setStatus('loading')
    setError(null)
    askInsightQuestion(text)
      .then((d) => { setAnswer(d); setStatus('done') })
      .catch((err) => { setError(err.message); setStatus('error') })
  }

  const onSubmit = (e) => {
    e.preventDefault()
    ask()
  }

  const isNoAnswer = answer && (answer.category === 'unsupported' || answer.category === 'not_found')

  return (
    <div>
      <PageHeader
        title="AI Insights"
        subtitle="Ask a question about the portfolio — answers are grounded in the same data and engines the rest of PropLens uses"
      />

      <ChartPanel title="Ask a Question">
        <form onSubmit={onSubmit} className="flex flex-col gap-3 sm:flex-row">
          <input
            type="text"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="e.g. Which properties are high risk?"
            className="flex-1 rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-gray-500 focus:outline-none"
          />
          <button
            type="submit"
            disabled={status === 'loading' || !question.trim()}
            className="rounded-md bg-gray-900 px-4 py-2 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-40 hover:bg-gray-800"
          >
            {status === 'loading' ? 'Thinking…' : 'Ask'}
          </button>
        </form>

        {examples.length > 0 && (
          <div className="mt-4">
            <p className="mb-2 text-xs font-medium uppercase tracking-wide text-gray-500">Example questions</p>
            <div className="flex flex-wrap gap-2">
              {examples.map((ex) => (
                <button
                  key={ex}
                  onClick={() => ask(ex)}
                  className="rounded-full border border-gray-300 px-3 py-1.5 text-xs text-gray-600 hover:bg-gray-50"
                >
                  {ex}
                </button>
              ))}
            </div>
          </div>
        )}

        {provider && (
          <p className="mt-4 text-[11px] text-gray-400">
            Answering engine: <span className="font-medium text-gray-500">{provider}</span> — a deterministic,
            rule-based layer that reads directly from PropLens's own analytics, risk, data-quality and forecasting
            services (no external AI API or paid key required).
          </p>
        )}
      </ChartPanel>

      {status === 'loading' && (
        <div className="mt-6"><LoadingState label="Looking up the answer…" /></div>
      )}

      {status === 'error' && (
        <div className="mt-6"><ErrorState message={error} onRetry={() => ask()} /></div>
      )}

      {status === 'done' && answer && (
        <div className="mt-6 space-y-4">
          <ChartPanel title="Answer">
            <p className="mb-3 text-xs text-gray-400">“{answer.question}”</p>

            <div className={`rounded-lg border px-4 py-3 text-sm ${
              isNoAnswer ? 'border-gray-200 bg-gray-50 text-gray-600' : 'border-gray-200 bg-white text-gray-900'
            }`}>
              {answer.answer}
            </div>

            <div className="mt-3 flex flex-wrap items-center gap-2 text-xs">
              <span className={`inline-flex items-center rounded-md px-2 py-1 font-medium capitalize ring-1 ring-inset ${
                CATEGORY_STYLES[answer.category] || CATEGORY_STYLES.unsupported
              }`}>
                {answer.category.replace('_', ' ')}
              </span>
              {answer.source !== 'none' && (
                <span className="text-gray-400">source: {answer.source}</span>
              )}
            </div>
          </ChartPanel>

          {answer.supporting_data && Object.keys(answer.supporting_data).length > 0 && (
            <ChartPanel title="Supporting Data">
              <dl className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm md:grid-cols-3">
                {Object.entries(answer.supporting_data).map(([key, value]) => (
                  <div key={key}>
                    <dt className="text-xs text-gray-400">{key.replace(/_/g, ' ')}</dt>
                    <dd className="font-medium text-gray-800">
                      {typeof value === 'object' && value !== null ? JSON.stringify(value) : String(value)}
                    </dd>
                  </div>
                ))}
              </dl>
            </ChartPanel>
          )}

          {answer.records && answer.records.length > 0 && (
            <ChartPanel title={`Relevant Records (${answer.records.length})`}>
              <div className="table-scroll overflow-x-auto">
                <table className="w-full min-w-[500px] text-sm">
                  <thead>
                    <tr className="text-left text-xs uppercase tracking-wide text-gray-500">
                      {Object.keys(answer.records[0]).map((key) => (
                        <th key={key} className="py-1.5 pr-4">{key.replace(/_/g, ' ')}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {answer.records.map((rec, i) => (
                      <tr key={i}>
                        {Object.entries(rec).map(([key, value]) => (
                          <td key={key} className="py-1.5 pr-4 text-gray-600">
                            {key === 'property_id' ? (
                              <Link to={`/properties/${value}`} className="text-gray-900 hover:underline">{value}</Link>
                            ) : Array.isArray(value) ? (
                              value.join('; ')
                            ) : (
                              String(value)
                            )}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </ChartPanel>
          )}
        </div>
      )}

      {status === 'idle' && (
        <div className="mt-6">
          <EmptyState message="Ask a question above, or pick one of the examples, to see a grounded answer from PropLens's own data." />
        </div>
      )}
    </div>
  )
}
