import { NavLink, Outlet } from 'react-router-dom'

const NAV_ITEMS = [
  { to: '/', label: 'Dashboard', end: true },
  { to: '/properties', label: 'Properties' },
  { to: '/leases', label: 'Leases' },
  { to: '/data-quality', label: 'Data Quality' },
  { to: '/risk', label: 'Risk' },
  { to: '/analytics', label: 'Analytics' },
  { to: '/import', label: 'CSV Import' },
  { to: '/insights', label: 'AI Insights' },
]

export default function Layout() {
  return (
    <div className="flex min-h-screen bg-gray-50">
      <aside className="fixed inset-y-0 left-0 hidden w-56 flex-col border-r border-gray-200 bg-white md:flex">
        <div className="flex h-16 items-center border-b border-gray-200 px-5">
          <span className="text-lg font-semibold tracking-tight text-gray-900">PropLens</span>
        </div>
        <nav className="flex-1 space-y-0.5 px-3 py-4">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                `block rounded-md px-3 py-2 text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-gray-900 text-white'
                    : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900'
                }`
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="border-t border-gray-200 px-5 py-4 text-xs text-gray-400">
          Synthetic demo data only
        </div>
      </aside>

      <div className="flex min-h-screen w-full flex-col md:pl-56">
        <header className="flex h-16 items-center justify-between border-b border-gray-200 bg-white px-6 md:hidden">
          <span className="text-lg font-semibold text-gray-900">PropLens</span>
        </header>
        <main className="flex-1 p-6">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
