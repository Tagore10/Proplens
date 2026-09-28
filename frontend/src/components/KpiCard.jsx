export default function KpiCard({ label, value, sublabel, tone = 'default' }) {
  const toneClass = {
    default: 'text-gray-900',
    warning: 'text-amber-700',
    danger: 'text-red-700',
    good: 'text-emerald-700',
  }[tone]

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
      <p className="text-xs font-medium uppercase tracking-wide text-gray-500">{label}</p>
      <p className={`mt-2 text-2xl font-semibold ${toneClass}`}>{value}</p>
      {sublabel && <p className="mt-1 text-xs text-gray-400">{sublabel}</p>}
    </div>
  )
}
