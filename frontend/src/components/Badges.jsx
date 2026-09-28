const LEASE_STATUS_STYLES = {
  Active: 'bg-emerald-50 text-emerald-700 ring-emerald-600/20',
  'Expiring Soon': 'bg-amber-50 text-amber-700 ring-amber-600/20',
  Expired: 'bg-red-50 text-red-700 ring-red-600/20',
  Unknown: 'bg-gray-100 text-gray-600 ring-gray-500/20',
}

const SEVERITY_STYLES = {
  low: 'bg-gray-100 text-gray-600 ring-gray-500/20',
  medium: 'bg-amber-50 text-amber-700 ring-amber-600/20',
  high: 'bg-red-50 text-red-700 ring-red-600/20',
}

export function LeaseStatusBadge({ status }) {
  const style = LEASE_STATUS_STYLES[status] || LEASE_STATUS_STYLES.Unknown
  return (
    <span className={`inline-flex items-center rounded-md px-2 py-1 text-xs font-medium ring-1 ring-inset ${style}`}>
      {status}
    </span>
  )
}

export function SeverityBadge({ severity }) {
  const style = SEVERITY_STYLES[severity] || SEVERITY_STYLES.low
  return (
    <span className={`inline-flex items-center rounded-md px-2 py-1 text-xs font-medium capitalize ring-1 ring-inset ${style}`}>
      {severity}
    </span>
  )
}
