import { NavLink } from 'react-router-dom'
import {
  ChartBarIcon,
  InboxIcon,
  SparklesIcon,
  BuildingLibraryIcon,
  Cog6ToothIcon,
} from '@heroicons/react/24/outline'

const NAV = [
  { to: '/dashboard',       label: 'Dashboard',        icon: ChartBarIcon },
  { to: '/inbox',           label: 'Bandeja de Entrada', icon: InboxIcon },
  { to: '/classifications', label: 'Análisis IA',       icon: SparklesIcon },
  { to: '/lenders',         label: 'Lenders',           icon: BuildingLibraryIcon },
]

export default function Sidebar() {
  return (
    <aside className="flex flex-col w-60 shrink-0 bg-navy-900 min-h-screen">
      {/* Logo */}
      <div className="flex items-center gap-3 px-6 py-5 border-b border-navy-800">
        <div className="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center text-white font-bold text-sm select-none">
          AP
        </div>
        <div>
          <p className="text-white font-semibold text-sm leading-tight">AcentoPartners</p>
          <p className="text-navy-300 text-xs">Waiver Management</p>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3 py-4 space-y-0.5">
        <p className="px-3 mb-2 text-navy-400 text-[10px] font-semibold uppercase tracking-widest">
          Operaciones
        </p>
        {NAV.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-150 ${
                isActive
                  ? 'bg-blue-600 text-white shadow-sm'
                  : 'text-navy-200 hover:bg-navy-800 hover:text-white'
              }`
            }
          >
            <Icon className="w-5 h-5 shrink-0" />
            {label}
          </NavLink>
        ))}

        <div className="pt-4">
          <p className="px-3 mb-2 text-navy-400 text-[10px] font-semibold uppercase tracking-widest">
            Configuración
          </p>
          <NavLink
            to="/lenders"
            className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium text-navy-300 hover:bg-navy-800 hover:text-white transition-all duration-150"
          >
            <Cog6ToothIcon className="w-5 h-5 shrink-0" />
            Base de Conocimiento
          </NavLink>
        </div>
      </nav>

      {/* Footer */}
      <div className="px-4 py-4 border-t border-navy-800">
        <p className="text-navy-500 text-[10px] text-center">v0.1.0 · FastAPI + Ollama</p>
      </div>
    </aside>
  )
}
