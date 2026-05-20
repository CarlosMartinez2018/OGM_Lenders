import { useState, useEffect, useCallback, Fragment } from 'react'
import {
  MagnifyingGlassIcon,
  FunnelIcon,
  CheckCircleIcon,
  PencilSquareIcon,
  EyeIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  ExclamationTriangleIcon,
  SparklesIcon,
  ArrowPathIcon,
  ClipboardDocumentCheckIcon,
  DocumentArrowDownIcon,
  PaperClipIcon,
} from '@heroicons/react/24/outline'
import { CheckCircleIcon as CheckCircleSolid } from '@heroicons/react/24/solid'
import { classificationsApi, lendersApi, configApi } from '../lib/api'
import Badge from '../components/ui/Badge'
import Button from '../components/ui/Button'
import Drawer from '../components/ui/Drawer'
import Modal from '../components/ui/Modal'
import Spinner from '../components/ui/Spinner'

const PAGE_SIZE = 50

// ── Confidence bar ─────────────────────────────────────────────────
function ConfidenceBar({ score, level }) {
  const pct = Math.round((score ?? 0) * 100)
  const color =
    level === 'high'   ? 'bg-emerald-500' :
    level === 'medium' ? 'bg-amber-400'   : 'bg-red-400'
  return (
    <div className="flex items-center gap-2 min-w-[90px]">
      <div className="flex-1 h-1.5 rounded-full bg-slate-100">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs font-mono text-slate-500 w-8 text-right">{pct}%</span>
    </div>
  )
}

// ── Stat card ──────────────────────────────────────────────────────
function StatCard({ label, value, sub, color = 'blue', icon: Icon }) {
  const ring = {
    blue:    'bg-blue-50 text-blue-600',
    emerald: 'bg-emerald-50 text-emerald-600',
    amber:   'bg-amber-50 text-amber-600',
    red:     'bg-red-50 text-red-600',
    purple:  'bg-purple-50 text-purple-600',
    slate:   'bg-slate-100 text-slate-500',
  }[color]
  return (
    <div className="bg-white rounded-xl border border-slate-200 px-5 py-4 flex items-center gap-4">
      <div className={`w-10 h-10 rounded-lg flex items-center justify-center shrink-0 ${ring}`}>
        <Icon className="w-5 h-5" />
      </div>
      <div>
        <p className="text-2xl font-bold text-slate-900 leading-tight">{value ?? '—'}</p>
        <p className="text-xs text-slate-500 mt-0.5">{label}</p>
        {sub && <p className="text-xs text-slate-400">{sub}</p>}
      </div>
    </div>
  )
}

// ── Correction modal ───────────────────────────────────────────────
function CorrectionModal({ open, onClose, item, onSaved }) {
  const [lenders, setLenders] = useState([])
  const [correctedLender, setCorrectedLender] = useState('')
  const [correctedWaiver, setCorrectedWaiver] = useState('')
  const [notes, setNotes] = useState('')
  const [reviewedBy, setReviewedBy] = useState('operator')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    lendersApi.lendersAndWaivers()
      .then(data => setLenders(Array.isArray(data) ? data : []))
      .catch(() => setLenders([]))
  }, [])

  useEffect(() => {
    if (item) {
      setCorrectedLender(item.classification?.lender ?? '')
      setCorrectedWaiver(item.classification?.waiver_type ?? '')
      setNotes('')
      setError(null)
    }
  }, [item])

  const selectedLenderObj = lenders.find(l => l.name === correctedLender)
  const waiverOptions = selectedLenderObj?.waivers?.map(w => w.name) ?? []

  async function handleSubmit(e) {
    e.preventDefault()
    if (!correctedLender || !correctedWaiver) {
      setError('Lender y Waiver son obligatorios.')
      return
    }
    setSaving(true)
    setError(null)
    try {
      await classificationsApi.correct(item.id, {
        corrected_lender: correctedLender,
        corrected_waiver_type: correctedWaiver,
        reviewed_by: reviewedBy,
        notes: notes || undefined,
      })
      onSaved()
      onClose()
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal open={open} onClose={onClose} title="Corregir clasificación" size="max-w-lg">
      {item && (
        <form onSubmit={handleSubmit} className="px-6 py-5 space-y-4">
          {/* Original */}
          <div className="rounded-lg bg-slate-50 border border-slate-200 px-4 py-3 text-sm space-y-1">
            <p className="text-xs font-medium text-slate-400 uppercase tracking-wide mb-2">Clasificación original</p>
            <div className="flex gap-6">
              <div>
                <p className="text-xs text-slate-500">Lender</p>
                <p className="font-medium text-slate-800">{item.classification?.lender ?? '—'}</p>
              </div>
              <div>
                <p className="text-xs text-slate-500">Waiver</p>
                <p className="font-medium text-slate-800">{item.classification?.waiver_type ?? '—'}</p>
              </div>
              <div>
                <p className="text-xs text-slate-500">Confianza</p>
                <p className="font-medium text-slate-800">
                  {Math.round((item.classification?.confidence_score ?? 0) * 100)}%
                </p>
              </div>
            </div>
          </div>

          {/* Lender select */}
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Lender correcto</label>
            <select
              value={correctedLender}
              onChange={e => { setCorrectedLender(e.target.value); setCorrectedWaiver('') }}
              className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="">Seleccionar lender…</option>
              {lenders.map(l => (
                <option key={l.id} value={l.name}>{l.name}</option>
              ))}
            </select>
          </div>

          {/* Waiver select */}
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Waiver type correcto</label>
            <select
              value={correctedWaiver}
              onChange={e => setCorrectedWaiver(e.target.value)}
              disabled={!correctedLender}
              className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
            >
              <option value="">Seleccionar waiver…</option>
              {waiverOptions.map(w => (
                <option key={w} value={w}>{w}</option>
              ))}
            </select>
          </div>

          {/* Reviewed by */}
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Revisado por</label>
            <input
              type="text"
              value={reviewedBy}
              onChange={e => setReviewedBy(e.target.value)}
              className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          {/* Notes */}
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Notas (opcional)</label>
            <textarea
              rows={3}
              value={notes}
              onChange={e => setNotes(e.target.value)}
              placeholder="Razón de la corrección…"
              className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
            />
          </div>

          {error && (
            <p className="text-sm text-red-600 flex items-center gap-1.5">
              <ExclamationTriangleIcon className="w-4 h-4 shrink-0" />
              {error}
            </p>
          )}

          <div className="flex justify-end gap-3 pt-1">
            <Button variant="secondary" type="button" onClick={onClose} disabled={saving}>
              Cancelar
            </Button>
            <Button variant="primary" type="submit" loading={saving}>
              Guardar corrección
            </Button>
          </div>
        </form>
      )}
    </Modal>
  )
}

// ── Detail drawer ─────────────────────────────────────────────────
function ClassificationDrawer({ open, onClose, item, onApprove, onCorrect, approving }) {
  if (!item) return null
  const c = item.classification ?? {}
  const pct = Math.round((c.confidence_score ?? 0) * 100)

  const fields = [
    { label: 'Trigger description', value: c.trigger_description },
    { label: 'Required evidence (Ops)', value: c.required_evidence_ops },
    { label: 'Required evidence (Insurance)', value: c.required_evidence_insurance },
    { label: 'Documents expected', value: c.documents_expected },
    { label: 'Waiver Pack', value: c.waiver_pack },
    { label: 'Actions to automate', value: c.actions_to_automate },
  ].filter(f => f.value)

  return (
    <Drawer
      open={open}
      onClose={onClose}
      title={item.subject ?? '(sin asunto)'}
      width="max-w-2xl"
    >
      <div className="space-y-6">
        {/* Classification summary */}
        <div className="rounded-xl border border-slate-200 divide-y divide-slate-100">
          <div className="px-4 py-3 bg-slate-50 rounded-t-xl">
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide">Clasificación IA</p>
          </div>
          <div className="px-4 py-3 grid grid-cols-2 gap-4">
            <div>
              <p className="text-xs text-slate-400 mb-0.5">Lender</p>
              <p className="text-sm font-semibold text-slate-900">{c.lender ?? '—'}</p>
            </div>
            <div>
              <p className="text-xs text-slate-400 mb-0.5">Waiver type</p>
              <p className="text-sm font-semibold text-slate-900">{c.waiver_type ?? '—'}</p>
            </div>
            <div>
              <p className="text-xs text-slate-400 mb-1">Confianza</p>
              <ConfidenceBar score={c.confidence_score} level={c.confidence_level} />
            </div>
            <div>
              <p className="text-xs text-slate-400 mb-0.5">Estado</p>
              <Badge variant={item.status ?? 'pending'}>{item.status ?? 'pending'}</Badge>
            </div>
          </div>
          {c.secondary_issues?.length > 0 && (
            <div className="px-4 py-3">
              <p className="text-xs text-slate-400 mb-2">Secondary issues</p>
              <div className="flex flex-wrap gap-1.5">
                {c.secondary_issues.map((s, i) => (
                  <span key={i} className="inline-flex items-center px-2 py-0.5 rounded-full bg-slate-100 text-xs text-slate-600">{s}</span>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Detail fields */}
        {fields.length > 0 && (
          <div className="space-y-3">
            {fields.map(f => (
              <div key={f.label} className="rounded-lg border border-slate-200 px-4 py-3 bg-white">
                <p className="text-xs font-medium text-slate-400 uppercase tracking-wide mb-1">{f.label}</p>
                <p className="text-sm text-slate-700 whitespace-pre-wrap">{f.value}</p>
              </div>
            ))}
          </div>
        )}

        {/* Attachments & Draft Response */}
        {(c.suggested_attachments?.length > 0 || c.draft_response) && (
          <div className="rounded-xl border border-indigo-100 divide-y divide-indigo-50 bg-indigo-50/30">
            <div className="px-4 py-3 bg-indigo-50 rounded-t-xl flex items-center gap-2">
              <PaperClipIcon className="w-4 h-4 text-indigo-500" />
              <p className="text-xs font-semibold text-indigo-600 uppercase tracking-wide">Adjuntos y Respuesta Propuesta</p>
            </div>
            
            {c.suggested_attachments?.length > 0 && (
              <div className="px-4 py-3">
                <p className="text-xs text-slate-400 mb-2">Documentos adjuntos encontrados</p>
                <div className="space-y-2">
                  {c.suggested_attachments.map((path, idx) => (
                    <div key={idx} className="flex items-center gap-2 text-sm bg-white p-2 rounded border border-indigo-100 text-indigo-700">
                      <DocumentArrowDownIcon className="w-4 h-4 shrink-0 text-indigo-400" />
                      <span className="truncate" title={path}>{path}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
            
            {c.draft_response && (
              <div className="px-4 py-3">
                <p className="text-xs text-slate-400 mb-2">Borrador de respuesta generado</p>
                <div className="bg-white p-3 rounded border border-indigo-100">
                  <p className="text-sm text-slate-700 whitespace-pre-wrap font-mono leading-relaxed">{c.draft_response}</p>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Reasoning */}
        {c.reasoning && (
          <div className="rounded-lg border border-blue-100 bg-blue-50 px-4 py-3">
            <p className="text-xs font-medium text-blue-500 uppercase tracking-wide mb-1 flex items-center gap-1">
              <SparklesIcon className="w-3.5 h-3.5" /> Razonamiento del modelo
            </p>
            <p className="text-sm text-slate-700 whitespace-pre-wrap leading-relaxed">{c.reasoning}</p>
          </div>
        )}

        {/* Email metadata */}
        <div className="rounded-xl border border-slate-200 divide-y divide-slate-100">
          <div className="px-4 py-3 bg-slate-50 rounded-t-xl">
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide">Metadatos del email</p>
          </div>
          <div className="px-4 py-3 grid grid-cols-2 gap-x-6 gap-y-3 text-sm">
            {[
              { k: 'Sender',   v: item.sender },
              { k: 'Source',   v: item.source },
              { k: 'Filename', v: item.filename },
              { k: 'ID',       v: item.id },
              { k: 'Created',  v: item.created_at ? new Date(item.created_at).toLocaleString() : null },
            ].filter(r => r.v).map(r => (
              <div key={r.k}>
                <p className="text-xs text-slate-400">{r.k}</p>
                <p className="text-slate-700 font-mono text-xs break-all">{r.v}</p>
              </div>
            ))}
          </div>
        </div>

        {/* Actions */}
        {item.status === 'pending' || item.status === 'classified' ? (
          <div className="flex gap-3 pt-1">
            <Button
              variant="success"
              onClick={() => onApprove(item)}
              loading={approving}
              className="flex-1"
            >
              <CheckCircleIcon className="w-4 h-4" />
              Aprobar
            </Button>
            <Button
              variant="secondary"
              onClick={() => onCorrect(item)}
              className="flex-1"
            >
              <PencilSquareIcon className="w-4 h-4" />
              Corregir
            </Button>
          </div>
        ) : (
          <div className="flex items-center gap-2 text-sm text-slate-500 bg-slate-50 rounded-lg px-4 py-3">
            <CheckCircleSolid className="w-4 h-4 text-emerald-500 shrink-0" />
            Esta clasificación ya fue revisada.
          </div>
        )}
      </div>
    </Drawer>
  )
}

// ── Main page ─────────────────────────────────────────────────────
export default function ClassificationsPage() {
  const [tab, setTab] = useState('all') // 'all' | 'review'
  const [stats, setStats] = useState(null)
  const [items, setItems] = useState([])
  const [reviewItems, setReviewItems] = useState([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(false)
  const [statsLoading, setStatsLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [filterStatus, setFilterStatus] = useState('')
  const [filterConfidence, setFilterConfidence] = useState('')
  const [selectedItem, setSelectedItem] = useState(null)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [correctionItem, setCorrectionItem] = useState(null)
  const [correctionOpen, setCorrectionOpen] = useState(false)
  const [approving, setApproving] = useState(false)
  const [actionError, setActionError] = useState(null)
  
  // Config
  const [config, setConfig] = useState({ document_base_path: '' })
  const [configSaving, setConfigSaving] = useState(false)

  // Load config
  useEffect(() => {
    configApi.get().then(setConfig).catch(() => {})
  }, [])
  
  async function handleSaveConfig() {
    setConfigSaving(true)
    try {
      const res = await configApi.update({ document_base_path: config.document_base_path })
      setConfig(res)
    } catch (err) {
      console.error(err)
    } finally {
      setConfigSaving(false)
    }
  }

  // Load stats
  useEffect(() => {
    setStatsLoading(true)
    classificationsApi.stats()
      .then(setStats)
      .catch(() => setStats(null))
      .finally(() => setStatsLoading(false))
  }, [])

  // Load classifications list
  const loadItems = useCallback(async () => {
    if (tab !== 'all') return
    setLoading(true)
    try {
      const params = {
        skip: (page - 1) * PAGE_SIZE,
        limit: PAGE_SIZE,
      }
      if (search)           params.search = search
      if (filterStatus)     params.status = filterStatus
      if (filterConfidence) params.confidence_level = filterConfidence
      const data = await classificationsApi.list(params)
      const arr = Array.isArray(data) ? data : (data?.items ?? [])
      setItems(arr)
      setTotal(data?.total ?? arr.length)
    } catch {
      setItems([])
    } finally {
      setLoading(false)
    }
  }, [tab, page, search, filterStatus, filterConfidence])

  // Load review queue
  const loadReviewQueue = useCallback(async () => {
    if (tab !== 'review') return
    setLoading(true)
    try {
      const data = await classificationsApi.reviewQueue()
      setReviewItems(Array.isArray(data) ? data : (data?.items ?? []))
    } catch {
      setReviewItems([])
    } finally {
      setLoading(false)
    }
  }, [tab])

  useEffect(() => { loadItems() }, [loadItems])
  useEffect(() => { loadReviewQueue() }, [loadReviewQueue])

  // Reset page when filters change
  useEffect(() => { setPage(1) }, [search, filterStatus, filterConfidence])

  function refresh() {
    loadItems()
    loadReviewQueue()
    setStatsLoading(true)
    classificationsApi.stats()
      .then(setStats)
      .catch(() => {})
      .finally(() => setStatsLoading(false))
  }

  function openDetail(item) {
    setSelectedItem(item)
    setActionError(null)
    setDrawerOpen(true)
  }

  async function handleApprove(item) {
    setApproving(true)
    setActionError(null)
    try {
      await classificationsApi.approve(item.id)
      setDrawerOpen(false)
      refresh()
    } catch (err) {
      setActionError(err.message)
    } finally {
      setApproving(false)
    }
  }

  function handleCorrect(item) {
    setCorrectionItem(item)
    setDrawerOpen(false)
    setCorrectionOpen(true)
  }

  function handleCorrectionSaved() {
    refresh()
  }

  const displayItems = tab === 'all' ? items : reviewItems
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))

  const statCards = [
    {
      label: 'Total clasificados',
      value: statsLoading ? '…' : (stats?.total_classified ?? 0),
      color: 'blue',
      icon: ClipboardDocumentCheckIcon,
    },
    {
      label: 'Alta confianza',
      value: statsLoading ? '…' : (stats?.by_confidence_level?.high ?? 0),
      sub: '> 85%',
      color: 'emerald',
      icon: CheckCircleIcon,
    },
    {
      label: 'Media confianza',
      value: statsLoading ? '…' : (stats?.by_confidence_level?.medium ?? 0),
      sub: '60 – 85%',
      color: 'amber',
      icon: ExclamationTriangleIcon,
    },
    {
      label: 'Baja confianza',
      value: statsLoading ? '…' : (stats?.by_confidence_level?.low ?? 0),
      sub: '< 60% — requieren revisión',
      color: 'red',
      icon: ExclamationTriangleIcon,
    },
    {
      label: 'Tasa de corrección',
      value: statsLoading ? '…' : `${Math.round((stats?.correction_rate ?? 0) * 100)}%`,
      color: 'purple',
      icon: PencilSquareIcon,
    },
  ]

  return (
    <div className="p-6 space-y-6">
      {/* Page header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-slate-900">Clasificaciones IA</h1>
          <p className="text-sm text-slate-500 mt-0.5">
            Resultados del agente de clasificación de emails por Lender y Waiver type.
          </p>
        </div>
        <Button variant="ghost" size="sm" onClick={refresh}>
          <ArrowPathIcon className="w-4 h-4" />
          Actualizar
        </Button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
        {statCards.map(s => <StatCard key={s.label} {...s} />)}
      </div>

      {/* Config Bar */}
      <div className="flex items-center gap-3 bg-white border border-slate-200 p-3 rounded-xl">
        <label className="text-sm font-medium text-slate-700 shrink-0">Ruta de Documentos PDF:</label>
        <input 
          type="text" 
          value={config.document_base_path}
          onChange={e => setConfig({...config, document_base_path: e.target.value})}
          placeholder="Ej. C:\Users\Documentos\Waivers"
          className="flex-1 min-w-0 rounded-md border border-slate-200 px-3 py-1.5 text-sm"
        />
        <Button size="sm" variant="secondary" loading={configSaving} onClick={handleSaveConfig}>
          Guardar Ruta
        </Button>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 bg-slate-100 rounded-xl p-1 w-fit">
        {[
          { id: 'all',    label: 'Todas las clasificaciones' },
          { id: 'review', label: `Cola de revisión${stats?.by_status?.pending ? ` (${stats.by_status.pending})` : ''}` },
        ].map(t => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-all ${
              tab === t.id
                ? 'bg-white text-slate-900 shadow-sm'
                : 'text-slate-500 hover:text-slate-700'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Filters (only on "all" tab) */}
      {tab === 'all' && (
        <div className="flex flex-wrap gap-3 items-center">
          <div className="relative flex-1 min-w-[200px] max-w-sm">
            <MagnifyingGlassIcon className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none" />
            <input
              type="text"
              placeholder="Buscar por asunto, lender, waiver…"
              value={search}
              onChange={e => setSearch(e.target.value)}
              className="w-full pl-9 pr-3 py-2 rounded-lg border border-slate-200 bg-white text-sm text-slate-800 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          <div className="flex items-center gap-2">
            <FunnelIcon className="w-4 h-4 text-slate-400" />
            <select
              value={filterStatus}
              onChange={e => setFilterStatus(e.target.value)}
              className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="">Todos los estados</option>
              <option value="pending">Pending</option>
              <option value="classified">Classified</option>
              <option value="reviewed">Reviewed</option>
              <option value="corrected">Corrected</option>
            </select>

            <select
              value={filterConfidence}
              onChange={e => setFilterConfidence(e.target.value)}
              className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="">Toda confianza</option>
              <option value="high">Alta (&gt;85%)</option>
              <option value="medium">Media (60-85%)</option>
              <option value="low">Baja (&lt;60%)</option>
            </select>
          </div>
        </div>
      )}

      {/* Table */}
      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
        {loading ? (
          <div className="flex items-center justify-center py-16 gap-3 text-slate-400">
            <Spinner size="md" />
            <span className="text-sm">Cargando clasificaciones…</span>
          </div>
        ) : displayItems.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 text-slate-400">
            <ClipboardDocumentCheckIcon className="w-10 h-10 mb-3 opacity-30" />
            <p className="text-sm font-medium">Sin clasificaciones</p>
            <p className="text-xs mt-1">
              {tab === 'review' ? 'No hay items pendientes de revisión.' : 'Ajusta los filtros o clasifica nuevos emails.'}
            </p>
          </div>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-100 bg-slate-50">
                    {['Asunto', 'Sender', 'Lender', 'Waiver type', 'Confianza', 'Estado', 'Creado', ''].map(h => (
                      <th key={h} className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wide whitespace-nowrap">
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-50">
                  {displayItems.map(item => {
                    const c = item.classification ?? {}
                    const isReviewed = item.status === 'reviewed' || item.status === 'corrected'
                    return (
                      <tr key={item.id} className="hover:bg-slate-50/60 transition-colors group">
                        {/* Subject */}
                        <td className="px-4 py-3 max-w-[200px]">
                          <p className="truncate text-slate-800 font-medium" title={item.subject}>
                            {item.subject ?? '(sin asunto)'}
                          </p>
                        </td>

                        {/* Sender */}
                        <td className="px-4 py-3 max-w-[160px]">
                          <p className="truncate text-xs font-mono text-slate-500" title={item.sender}>
                            {item.sender ?? '—'}
                          </p>
                        </td>

                        {/* Lender */}
                        <td className="px-4 py-3">
                          <span className="text-slate-800 font-medium">{c.lender ?? '—'}</span>
                        </td>

                        {/* Waiver */}
                        <td className="px-4 py-3 max-w-[180px]">
                          <span className="text-slate-600 truncate block" title={c.waiver_type}>
                            {c.waiver_type ?? '—'}
                          </span>
                        </td>

                        {/* Confidence */}
                        <td className="px-4 py-3">
                          <ConfidenceBar score={c.confidence_score} level={c.confidence_level} />
                        </td>

                        {/* Status */}
                        <td className="px-4 py-3">
                          <Badge variant={item.status ?? 'pending'}>{item.status ?? 'pending'}</Badge>
                        </td>

                        {/* Date */}
                        <td className="px-4 py-3 text-xs text-slate-400 whitespace-nowrap">
                          {item.created_at
                            ? new Date(item.created_at).toLocaleDateString('es-MX', { day:'2-digit', month:'short', year:'numeric' })
                            : '—'}
                        </td>

                        {/* Actions */}
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                            <button
                              onClick={() => openDetail(item)}
                              className="p-1.5 rounded-lg text-slate-400 hover:text-blue-600 hover:bg-blue-50 transition-colors"
                              title="Ver detalle"
                            >
                              <EyeIcon className="w-4 h-4" />
                            </button>
                            {!isReviewed && (
                              <>
                                <button
                                  onClick={() => handleApprove(item)}
                                  className="p-1.5 rounded-lg text-slate-400 hover:text-emerald-600 hover:bg-emerald-50 transition-colors"
                                  title="Aprobar"
                                >
                                  <CheckCircleIcon className="w-4 h-4" />
                                </button>
                                <button
                                  onClick={() => handleCorrect(item)}
                                  className="p-1.5 rounded-lg text-slate-400 hover:text-amber-600 hover:bg-amber-50 transition-colors"
                                  title="Corregir"
                                >
                                  <PencilSquareIcon className="w-4 h-4" />
                                </button>
                              </>
                            )}
                          </div>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>

            {/* Pagination (all tab only) */}
            {tab === 'all' && totalPages > 1 && (
              <div className="flex items-center justify-between px-4 py-3 border-t border-slate-100">
                <p className="text-xs text-slate-400">
                  {(page - 1) * PAGE_SIZE + 1}–{Math.min(page * PAGE_SIZE, total)} de {total}
                </p>
                <div className="flex gap-1">
                  <button
                    onClick={() => setPage(p => Math.max(1, p - 1))}
                    disabled={page === 1}
                    className="p-1.5 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-100 disabled:opacity-30 transition-colors"
                  >
                    <ChevronLeftIcon className="w-4 h-4" />
                  </button>
                  <span className="px-3 py-1.5 text-xs text-slate-600">
                    {page} / {totalPages}
                  </span>
                  <button
                    onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                    disabled={page === totalPages}
                    className="p-1.5 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-100 disabled:opacity-30 transition-colors"
                  >
                    <ChevronRightIcon className="w-4 h-4" />
                  </button>
                </div>
              </div>
            )}
          </>
        )}
      </div>

      {actionError && (
        <div className="flex items-center gap-2 px-4 py-3 rounded-lg bg-red-50 border border-red-200 text-sm text-red-700">
          <ExclamationTriangleIcon className="w-4 h-4 shrink-0" />
          {actionError}
        </div>
      )}

      {/* Detail drawer */}
      <ClassificationDrawer
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        item={selectedItem}
        onApprove={handleApprove}
        onCorrect={handleCorrect}
        approving={approving}
      />

      {/* Correction modal */}
      <CorrectionModal
        open={correctionOpen}
        onClose={() => setCorrectionOpen(false)}
        item={correctionItem}
        onSaved={handleCorrectionSaved}
      />
    </div>
  )
}
