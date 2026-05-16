import { Fragment } from 'react'
import { useLocation } from 'react-router-dom'
import { Menu, Transition } from '@headlessui/react'
import { ChevronDownIcon, ArrowRightOnRectangleIcon, UserCircleIcon } from '@heroicons/react/24/outline'

const TITLES = {
  '/dashboard':       'Dashboard',
  '/inbox':           'Bandeja de Entrada',
  '/classifications': 'Análisis IA',
  '/lenders':         'Gestión de Lenders',
}

export default function TopBar() {
  const { pathname } = useLocation()
  const title = TITLES[pathname] ?? 'AcentoPartners'

  return (
    <header className="h-14 bg-white border-b border-slate-200 flex items-center justify-between px-6 shrink-0 sticky top-0 z-30">
      <h1 className="text-sm font-semibold text-slate-800">{title}</h1>

      <Menu as="div" className="relative">
        <Menu.Button className="flex items-center gap-2 px-3 py-1.5 rounded-lg hover:bg-slate-100 transition-colors text-slate-700">
          <div className="w-7 h-7 rounded-full bg-navy-900 text-white text-xs font-bold flex items-center justify-center select-none">
            AP
          </div>
          <span className="text-sm font-medium">Admin</span>
          <ChevronDownIcon className="w-4 h-4 text-slate-400" />
        </Menu.Button>

        <Transition
          as={Fragment}
          enter="transition ease-out duration-100"
          enterFrom="transform opacity-0 scale-95"
          enterTo="transform opacity-100 scale-100"
          leave="transition ease-in duration-75"
          leaveFrom="transform opacity-100 scale-100"
          leaveTo="transform opacity-0 scale-95"
        >
          <Menu.Items className="absolute right-0 mt-2 w-52 bg-white rounded-xl shadow-modal border border-slate-100 py-1 focus:outline-none z-50">
            <div className="px-4 py-3 border-b border-slate-100">
              <p className="text-xs font-semibold text-slate-900">AcentoPartners</p>
              <p className="text-xs text-slate-400 truncate">lender-insurance@acentopartners.com</p>
            </div>
            <Menu.Item>
              {({ active }) => (
                <button
                  className={`flex w-full items-center gap-2.5 px-4 py-2.5 text-sm ${active ? 'bg-slate-50 text-slate-900' : 'text-slate-700'}`}
                >
                  <UserCircleIcon className="w-4 h-4 text-slate-400" />
                  Perfil
                </button>
              )}
            </Menu.Item>
            <Menu.Item>
              {({ active }) => (
                <button
                  className={`flex w-full items-center gap-2.5 px-4 py-2.5 text-sm text-red-600 ${active ? 'bg-red-50' : ''}`}
                >
                  <ArrowRightOnRectangleIcon className="w-4 h-4" />
                  Cerrar sesión
                </button>
              )}
            </Menu.Item>
          </Menu.Items>
        </Transition>
      </Menu>
    </header>
  )
}
