import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import {
  EnvelopeIcon,
  ClipboardDocumentCheckIcon,
  BuildingLibraryIcon,
  ExclamationTriangleIcon,
  ArrowRightIcon,
  CheckCircleIcon,
  SparklesIcon,
  ChartBarIcon,
} from '@heroicons/react/24/outline'
import { emailsApi, classificationsApi, lendersApi } from '../lib/api'
import Badge from '../components/ui/Badge'
import Spinner from '../components/ui/Spinner'

// ── KPI card ──────────────────────────────────────────────────────
function KpiCard({ label, value, sub, icon: Icon, color = 'blue', to }) {
  const palette = {
    blue:    { bg: 'bg-blue-50',    text: 'text-blue-600',    border: 'border-blue-100' },
    emerald: { bg: 'bg-emerald-50', text: 'text-emerald-600', border: 'border-emerald-100' },
    amber:   { bg: 'bg-amber-50',   text: 'text-amber-600',   border: 'border-amber-100' },
    navy:    { bg: 'bg-navy-900/5', text: 'text-navy-900',    border: 'border-navy-900/10' },
    red:     { bg: 'bg-red-50',     text: 'text-red-600',     border: 'border-red-100' },
    purple:  { bg: 'bg-purple-50',  text: 'text-purple-600',  border: 'border-purple-100' },
  }[color]

  const inner = (
    <div className={`bg-white rounded-xl border ${palette.border} px-5 py-4 flex items-start gap-4 h-full`}>
      <div className={`w-10 h-10 rounded-lg flex items-center justify-center shrink-0 ${palette.bg} ${palette.text}`}>
        <Icon className="w-5 h-5" />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide">{label}</p>
        <p className="text-3xl font-bold text-slate-900 mt-0.5 leading-none">{value ?? '—'}</p>
        {sub && <p className="text-xs text-slate-400 mt-1">{sub}</p>}
      </div>
      {to && <ArrowRightIcon className="w-4 h-4 text-slate-300 shrink-0 mt-0.5" />}
    </div>
  )

  return to ? (
    <Link to={to} className="block hover:scale-[1.01] transition-transform">{inner}</Link>
  ) : (
    <div>{inner}</div>
  )
}

// ── Bar chart (horizontal) ─────────────────────────────────────────
function HorizontalBar({ label, count, total, color = 'bg-blue-500' }) {
  const pct = total > 0 ? Math.round((count / total) * 100) : 0
  return (
    <div className="flex items-center gap-3">
      <p className="text-sm text-slate-700 w-36 shrink-0 truncate" title={label}>{label}</p>
      <div className="flex-1 h-2 rounded-full bg-slate-100">
        <div className={`h-full rounded-full ${color} transition-all`} style={{ width: `${pct}%` }} />
      </div>
      <p className="text-xs text-slate-500 w-8 text-right font-mono">{count}</p>
    </div>
  )
}

// ── Section card ──────────────────────────────────────────────────
function Section({ title, icon: Icon, to, toLabel, children, loading }) {
  return (
    <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
      <div className="flex items-center justify-between px-5 py-4 border-b border-slate-100">
        <div className="flex items-center gap-2">
          <Icon className="w-4 h-4 text-slate-400" />
          <h2 className="text-sm font-semibold text-slate-800">{title}</h2>
        </div>
        {to && (
          <Link to={to} className="text-xs text-blue-600 hover:text-blue-800 flex items-center gap-1">
            {toLabel ?? 'Ver todo'} <ArrowRightIcon className="w-3 h-3" />
          </Link>
        )}
      </div>
      <div className="px-5 py-4">
        {loading ? (
          <div className="flex items-center gap-2 text-slate-400 py-4 justify-center">
            <Spinner size="sm" /> <span className="text-sm">Cargando…</span>
          </div>
        ) : children}
      </div>
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────────
export default function DashboardPage() {
  const [emailStats, setEmailStats]           = useState(null)
  const [classStats, setClassStats]           = useState(null)
  const [lenders, setLenders]                 = useState([])
  const [emailLoading, setEmailLoading]       = useState(true)
  const [classLoading, setClassLoading]       = useState(true)
  const [lenderLoading, setLenderLoading]     = useState(true)

  useEffect(() => {
    emailsApi.stats()
      .then(setEmailStats)
      .catch(() => setEmailStats(null))
      .finally(() => setEmailLoading(false))

    classificationsApi.stats()
      .then(setClassStats)
      .catch(() => setClassStats(null))
      .finally(() => setClassLoading(false))

    lendersApi.list()
      .then(data => setLenders(Array.isArray(data) ? data : []))
      .catch(() => setLenders([]))
      .finally(() => setLenderLoading(false))
  }, [])

  const topLenders = classStats?.by_lender
    ? Object.entries(classStats.by_lender)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 6)
    : []

  const topWaivers = classStats?.by_waiver_type
    ? Object.entries(classStats.by_waiver_type)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 6)
    : []

  const totalClassified = classStats?.total_classified ?? 0
  const totalWaivers    = lenders.reduce((acc, l) => acc + (l.waivers?.length ?? 0), 0)
  const pendingReview   = classStats?.by_status?.pending ?? 0
  const avgConf         = classStats?.avg_confidence ? Math.round(classStats.avg_confidence * 100) : null

  const isLoading = emailLoading || classLoading

  return (
    <div className="p-6 space-y-6">
      {/* Page header */}
      <div>
        <h1 className="text-xl font-bold text-slate-900">Dashboard</h1>
        <p className="text-sm text-slate-500 mt-0.5">
          Vista general de la actividad del agente de clasificación.
        </p>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <KpiCard
          label="Emails en inbox"
          value={isLoading ? '…' : (emailStats?.total ?? 0)}
          sub={`${emailStats?.pending ?? 0} pendientes`}
          icon={EnvelopeIcon}
          color="blue"
          to="/inbox"
        />
        <KpiCard
          label="Clasificados"
          value={isLoading ? '…' : totalClassified}
          sub={`Tasa corrección: ${classStats?.correction_rate != null ? Math.round(classStats.correction_rate * 100) + '%' : '—'}`}
          icon={ClipboardDocumentCheckIcon}
          color="emerald"
          to="/classifications"
        />
        <KpiCard
          label="Pendientes revisión"
          value={isLoading ? '…' : pendingReview}
          sub="Baja confianza o sin aprobar"
          icon={ExclamationTriangleIcon}
          color={pendingReview > 0 ? 'amber' : 'emerald'}
          to="/classifications"
        />
        <KpiCard
          label="Lenders activos"
          value={lenderLoading ? '…' : lenders.filter(l => l.is_active).length}
          sub={`${totalWaivers} waivers configurados`}
          icon={BuildingLibraryIcon}
          color="navy"
          to="/lenders"
        />
      </div>

      {/* Secondary KPIs */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          { label: 'Alta confianza', value: classStats?.by_confidence_level?.high ?? 0, color: 'emerald', pct: totalClassified },
          { label: 'Media confianza', value: classStats?.by_confidence_level?.medium ?? 0, color: 'amber', pct: totalClassified },
          { label: 'Baja confianza', value: classStats?.by_confidence_level?.low ?? 0, color: 'red', pct: totalClassified },
          { label: 'Confianza promedio', value: avgConf != null ? `${avgConf}%` : '—', color: 'purple', pct: null },
        ].map(s => (
          <div key={s.label} className="bg-white rounded-xl border border-slate-200 px-5 py-3">
            <p className="text-xs text-slate-400 font-medium">{s.label}</p>
            <p className={`text-2xl font-bold mt-0.5 ${
              s.color === 'emerald' ? 'text-emerald-600' :
              s.color === 'amber'   ? 'text-amber-500'   :
              s.color === 'red'     ? 'text-red-500'     : 'text-purple-600'
            }`}>
              {isLoading ? '…' : s.value}
            </p>
            {s.pct != null && s.pct > 0 && (
              <p className="text-xs text-slate-400">
                {Math.round(((typeof s.value === 'number' ? s.value : 0) / s.pct) * 100)}% del total
              </p>
            )}
          </div>
        ))}
      </div>

      {/* Charts row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Top lenders */}
        <Section
          title="Top lenders clasificados"
          icon={ChartBarIcon}
          to="/classifications"
          loading={classLoading}
        >
          {topLenders.length === 0 ? (
            <p className="text-sm text-slate-400 text-center py-4">Sin datos de clasificación aún.</p>
          ) : (
            <div className="space-y-3">
              {topLenders.map(([name, count]) => (
                <HorizontalBar
                  key={name}
                  label={name}
                  count={count}
                  total={totalClassified}
                  color="bg-navy-900"
                />
              ))}
            </div>
          )}
        </Section>

        {/* Top waiver types */}
        <Section
          title="Top waiver types"
          icon={SparklesIcon}
          to="/classifications"
          loading={classLoading}
        >
          {topWaivers.length === 0 ? (
            <p className="text-sm text-slate-400 text-center py-4">Sin datos de clasificación aún.</p>
          ) : (
            <div className="space-y-3">
              {topWaivers.map(([name, count]) => (
                <HorizontalBar
                  key={name}
                  label={name}
                  count={count}
                  total={totalClassified}
                  color="bg-blue-500"
                />
              ))}
            </div>
          )}
        </Section>
      </div>

      {/* Email stats + Lender list */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Email breakdown */}
        <Section
          title="Estado del inbox"
          icon={EnvelopeIcon}
          to="/inbox"
          loading={emailLoading}
        >
          {!emailStats ? (
            <p className="text-sm text-slate-400 text-center py-4">Sin datos de inbox aún.</p>
          ) : (
            <div className="space-y-2.5">
              {[
                { label: 'Total', count: emailStats.total ?? 0, color: 'bg-slate-400' },
                { label: 'Pendientes', count: emailStats.pending ?? 0, color: 'bg-amber-400' },
                { label: 'Clasificados', count: emailStats.classified ?? 0, color: 'bg-blue-500' },
                { label: 'Procesados', count: emailStats.processed ?? 0, color: 'bg-emerald-500' },
              ].map(r => (
                <HorizontalBar
                  key={r.label}
                  label={r.label}
                  count={r.count}
                  total={emailStats.total || 1}
                  color={r.color}
                />
              ))}
            </div>
          )}
        </Section>

        {/* Lender knowledge base snapshot */}
        <Section
          title="Base de conocimiento"
          icon={BuildingLibraryIcon}
          to="/lenders"
          toLabel="Gestionar"
          loading={lenderLoading}
        >
          {lenders.length === 0 ? (
            <p className="text-sm text-slate-400 text-center py-4">
              Sin lenders configurados. Ve a Lenders → Seed matrix.
            </p>
          ) : (
            <div className="space-y-2">
              {lenders.slice(0, 7).map(l => (
                <div key={l.id} className="flex items-center justify-between py-1.5 border-b border-slate-50 last:border-0">
                  <div className="flex items-center gap-2 min-w-0">
                    <div className={`w-1.5 h-1.5 rounded-full shrink-0 ${l.is_active ? 'bg-emerald-400' : 'bg-slate-300'}`} />
                    <span className="text-sm text-slate-700 font-medium truncate">{l.name}</span>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <span className="text-xs text-slate-400">{l.waivers?.length ?? 0} waivers</span>
                    <Badge variant={l.is_active ? 'active' : 'inactive'} className="text-xs">
                      {l.is_active ? 'activo' : 'inactivo'}
                    </Badge>
                  </div>
                </div>
              ))}
              {lenders.length > 7 && (
                <p className="text-xs text-slate-400 text-center pt-1">
                  +{lenders.length - 7} más — <Link to="/lenders" className="text-blue-600 hover:underline">ver todos</Link>
                </p>
              )}
            </div>
          )}
        </Section>
      </div>
    </div>
  )
}
