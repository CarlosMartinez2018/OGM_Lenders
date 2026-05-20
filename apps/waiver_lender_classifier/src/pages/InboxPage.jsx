import { useState, useEffect, useCallback, useRef } from 'react'
import {
  MagnifyingGlassIcon, ArrowPathIcon, CloudArrowUpIcon,
  EnvelopeIcon, ChevronDownIcon, ChevronUpIcon,
  EyeIcon, TrashIcon, PaperClipIcon, FunnelIcon,
} from '@heroicons/react/24/outline'
import { emailsApi } from '../lib/api'
import Badge from '../components/ui/Badge'
import Button from '../components/ui/Button'
import Drawer from '../components/ui/Drawer'
import Spinner from '../components/ui/Spinner'

const PAGE_SIZE = 50

function StatCard({ label, value, sub, color = 'text-slate-900' }) {
  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-card px-5 py-4">
      <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">{label}</p>
      <p className={`text-3xl font-bold mt-1 ${color}`}>{value ?? '—'}</p>
      {sub && <p className="text-xs text-slate-400 mt-0.5">{sub}</p>}
    </div>
  )
}

function IngestPanel() {
  const [open, setOpen] = useState(false)
  const [files, setFiles] = useState([])
  const [loading, setLoading] = useState(false)
  const [outlookLoading, setOutlookLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [month, setMonth] = useState('')
  const [year, setYear] = useState(new Date().getFullYear().toString())
  const [allDates, setAllDates] = useState(false)
  const fileRef = useRef()

  async function handleFileIngest() {
    if (!files.length) return
    setLoading(true); setResult(null)
    try {
      const d = await emailsApi.uploadEml(files)
      setResult({ ok: true, msg: `✓ ${d.inserted} insertados · ${d.duplicates} duplicados · ${d.errors} errores` })
      setFiles([])
    } catch (e) {
      setResult({ ok: false, msg: e.message })
    } finally { setLoading(false) }
  }

  async function handleOutlookIngest() {
    setOutlookLoading(true); setResult(null)
    try {
      const payload = { all_dates: allDates }
      if (month) payload.month = parseInt(month)
      if (year) payload.year = parseInt(year)
      const d = await emailsApi.ingestOutlook(payload)
      setResult({ ok: true, msg: `✓ Outlook: ${d.inserted} insertados · ${d.duplicates} duplicados · ${d.errors} errores` })
    } catch (e) {
      setResult({ ok: false, msg: e.message })
    } finally { setOutlookLoading(false) }
  }

  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-card overflow-hidden">
      <button
        onClick={() => setOpen(o => !o)}
        className="flex items-center justify-between w-full px-5 py-3.5 text-sm font-medium text-slate-700 hover:bg-slate-50 transition-colors"
      >
        <span className="flex items-center gap-2">
          <CloudArrowUpIcon className="w-4 h-4 text-slate-400" />
          Ingestar Emails
        </span>
        {open ? <ChevronUpIcon className="w-4 h-4 text-slate-400" /> : <ChevronDownIcon className="w-4 h-4 text-slate-400" />}
      </button>

      {open && (
        <div className="px-5 pb-5 border-t border-slate-100 pt-4 space-y-4">
          {result && (
            <div className={`px-4 py-3 rounded-lg text-sm font-medium ${result.ok ? 'bg-emerald-50 text-emerald-800 border border-emerald-200' : 'bg-red-50 text-red-800 border border-red-200'}`}>
              {result.msg}
            </div>
          )}

          <div className="flex flex-wrap gap-4 items-end">
            {/* File upload */}
            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-slate-500">Subir archivos .eml</label>
              <div className="flex gap-2">
                <label className="flex items-center gap-2 px-3 py-2 border border-dashed border-slate-300 rounded-lg text-sm text-slate-500 cursor-pointer hover:border-blue-400 hover:text-blue-600 hover:bg-blue-50 transition-all">
                  <PaperClipIcon className="w-4 h-4" />
                  {files.length ? `${files.length} archivo(s)` : 'Elegir .eml…'}
                  <input
                    ref={fileRef}
                    type="file"
                    accept=".eml"
                    multiple
                    className="hidden"
                    onChange={e => setFiles(Array.from(e.target.files))}
                  />
                </label>
                <Button size="sm" onClick={handleFileIngest} disabled={!files.length} loading={loading}>
                  Subir e Ingestar
                </Button>
              </div>
            </div>

            <div className="w-px h-10 bg-slate-200 self-center" />

            {/* Outlook */}
            <div className="flex gap-3 items-end flex-wrap">
              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-slate-500">Mes (opcional)</label>
                <select value={month} onChange={e => setMonth(e.target.value)}
                  className="px-2.5 py-2 border border-slate-200 rounded-lg text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent">
                  <option value="">— mes actual —</option>
                  {['Enero','Febrero','Marzo','Abril','Mayo','Junio','Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre'].map((m,i) => (
                    <option key={i} value={i+1}>{m}</option>
                  ))}
                </select>
              </div>
              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-slate-500">Año</label>
                <input value={year} onChange={e => setYear(e.target.value)}
                  className="w-20 px-2.5 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent" />
              </div>
              <label className="flex items-center gap-1.5 text-sm text-slate-600 pb-1 cursor-pointer">
                <input type="checkbox" checked={allDates} onChange={e => setAllDates(e.target.checked)} className="rounded" />
                Todas las fechas
              </label>
              <Button size="sm" variant="navy" onClick={handleOutlookIngest} loading={outlookLoading}>
                <EnvelopeIcon className="w-4 h-4" />
                Ingestar desde Outlook
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function EmailDetailDrawer({ emailId, open, onClose, onDelete }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [tab, setTab] = useState('clean')

  useEffect(() => {
    if (!open || !emailId) return
    setLoading(true)
    emailsApi.get(emailId)
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false))
  }, [open, emailId])

  const handleDelete = async () => {
    if (!confirm('¿Eliminar este email?')) return
    await emailsApi.delete(emailId)
    onDelete?.()
    onClose()
  }

  return (
    <Drawer open={open} onClose={onClose} title={data?.subject || 'Detalle del Email'} width="max-w-2xl">
      {loading && <div className="flex justify-center py-16"><Spinner size="lg" className="text-blue-600" /></div>}
      {!loading && data && (
        <div className="space-y-5">
          {/* Meta row */}
          <div className="flex flex-wrap gap-3">
            <Badge variant={data.source}>{data.source}</Badge>
            <Badge variant={data.status}>{data.status}</Badge>
            {data.has_attachments && (
              <span className="flex items-center gap-1 text-xs text-amber-700 bg-amber-50 border border-amber-200 px-2 py-0.5 rounded-md font-medium">
                <PaperClipIcon className="w-3.5 h-3.5" />
                {data.attachment_names?.length ?? 0} adjunto(s)
              </span>
            )}
          </div>

          {/* Info grid */}
          <div className="grid grid-cols-2 gap-4 text-sm">
            {[
              ['De', data.sender],
              ['Dominio', data.sender_domain],
              ['Recibido', data.received_date ? new Date(data.received_date).toLocaleDateString('es-MX', { day:'2-digit', month:'short', year:'numeric' }) : '—'],
              ['Ingestado', data.ingested_at ? new Date(data.ingested_at).toLocaleDateString('es-MX', { day:'2-digit', month:'short', year:'numeric' }) : '—'],
            ].map(([lbl, val]) => (
              <div key={lbl}>
                <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider">{lbl}</p>
                <p className="text-slate-800 mt-0.5 font-mono text-xs">{val || '—'}</p>
              </div>
            ))}
          </div>

          {/* To recipients */}
          {data.to_recipients?.length > 0 && (
            <div>
              <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider mb-1.5">Para</p>
              <div className="flex flex-wrap gap-1.5">
                {data.to_recipients.map(r => (
                  <span key={r} className="text-xs bg-slate-100 text-slate-600 px-2 py-0.5 rounded font-mono">{r}</span>
                ))}
              </div>
            </div>
          )}

          {/* Attachments */}
          {data.attachment_names?.length > 0 && (
            <div>
              <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider mb-1.5">Adjuntos</p>
              <div className="flex flex-wrap gap-1.5">
                {data.attachment_names.map(a => (
                  <span key={a} className="text-xs bg-amber-50 text-amber-700 border border-amber-200 px-2 py-0.5 rounded">{a}</span>
                ))}
              </div>
            </div>
          )}

          {/* Body */}
          {(data.body_text || data.body_clean) && (
            <div>
              <div className="flex gap-0 border border-slate-200 rounded-lg overflow-hidden mb-2">
                {['clean','raw'].map(t => (
                  <button key={t} onClick={() => setTab(t)}
                    className={`flex-1 py-1.5 text-xs font-semibold transition-colors ${tab === t ? 'bg-navy-900 text-white' : 'bg-white text-slate-500 hover:bg-slate-50'}`}>
                    {t === 'clean' ? 'Texto limpio' : 'Texto crudo'}
                  </button>
                ))}
              </div>
              <pre className={`text-xs leading-relaxed whitespace-pre-wrap p-3 rounded-lg max-h-72 overflow-y-auto ${
                tab === 'clean' ? 'bg-emerald-50 text-emerald-900 border border-emerald-100' : 'bg-slate-50 text-slate-700 border border-slate-200 font-mono'
              }`}>
                {(tab === 'clean' ? data.body_clean : data.body_text)?.slice(0, 3000) || 'Sin contenido disponible.'}
              </pre>
            </div>
          )}

          {/* IDs */}
          <div className="pt-2 border-t border-slate-100 space-y-2">
            <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider">Identificadores</p>
            <p className="text-xs font-mono text-slate-500 break-all">ID: {data.id}</p>
            {data.message_id && <p className="text-xs font-mono text-slate-400 break-all">{data.message_id}</p>}
          </div>

          {/* Delete */}
          <div className="pt-2">
            <Button variant="danger" size="sm" onClick={handleDelete}>
              <TrashIcon className="w-4 h-4" />
              Eliminar email
            </Button>
          </div>
        </div>
      )}
    </Drawer>
  )
}

export default function InboxPage() {
  const [emails, setEmails] = useState([])
  const [stats, setStats] = useState(null)
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [source, setSource] = useState('')
  const [status, setStatus] = useState('')
  const [offset, setOffset] = useState(0)
  const [selectedId, setSelectedId] = useState(null)
  const [drawerOpen, setDrawerOpen] = useState(false)

  const load = useCallback(async (params = {}) => {
    setLoading(true)
    try {
      const [emailData, statsData] = await Promise.all([
        emailsApi.list({ limit: PAGE_SIZE, offset, ...params }),
        emailsApi.stats(),
      ])
      setEmails(emailData.items ?? [])
      setTotal(emailData.total ?? 0)
      setStats(statsData)
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }, [offset])

  useEffect(() => { load({ search, source, status, offset }) }, [offset])

  const handleFilter = () => { setOffset(0); load({ search, source, status, offset: 0 }) }

  const openDrawer = (id) => { setSelectedId(id); setDrawerOpen(true) }

  const fmtDate = (iso) => iso
    ? new Date(iso).toLocaleDateString('es-MX', { day: '2-digit', month: 'short', year: 'numeric' })
    : '—'

  return (
    <div className="space-y-5 max-w-[1400px]">
      {/* Stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <StatCard label="Total Emails" value={stats?.total} sub="en parsed_emails" />
        <StatCard label="Pendientes" value={stats?.by_status?.pending ?? 0} sub="sin clasificar" color="text-amber-600" />
        <StatCard label="Clasificados" value={stats?.by_status?.classified ?? 0} sub="procesados por IA" color="text-emerald-600" />
        <StatCard label="Procesados" value={stats?.by_status?.processed ?? 0} sub="completados" color="text-blue-600" />
      </div>

      {/* Ingest panel (collapsed by default) */}
      <IngestPanel />

      {/* Table card */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-card overflow-hidden">
        {/* Toolbar */}
        <div className="flex items-center gap-3 px-4 py-3 border-b border-slate-100 flex-wrap">
          <h2 className="text-sm font-semibold text-slate-700 flex-1">
            Emails{total > 0 && <span className="ml-2 text-slate-400 font-normal">({total})</span>}
          </h2>

          {/* Search */}
          <div className="relative">
            <MagnifyingGlassIcon className="absolute left-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
            <input
              value={search}
              onChange={e => setSearch(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleFilter()}
              placeholder="Buscar asunto, remitente…"
              className="pl-8 pr-3 py-1.5 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 w-52"
            />
          </div>

          {/* Filters */}
          <div className="flex gap-2">
            <select value={source} onChange={e => { setSource(e.target.value); setOffset(0); load({ search, source: e.target.value, status, offset: 0 }) }}
              className="px-2.5 py-1.5 text-sm border border-slate-200 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-blue-500">
              <option value="">Todas las fuentes</option>
              <option value="outlook">Outlook</option>
              <option value="file">Archivo</option>
            </select>
            <select value={status} onChange={e => { setStatus(e.target.value); setOffset(0); load({ search, source, status: e.target.value, offset: 0 }) }}
              className="px-2.5 py-1.5 text-sm border border-slate-200 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-blue-500">
              <option value="">Todos los estados</option>
              <option value="pending">Pendiente</option>
              <option value="classified">Clasificado</option>
              <option value="processed">Procesado</option>
            </select>
          </div>

          <Button variant="secondary" size="sm" onClick={() => load({ search, source, status, offset })} disabled={loading}>
            <ArrowPathIcon className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            Actualizar
          </Button>
        </div>

        {/* Table */}
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-slate-50 border-b border-slate-200">
                {['Fuente','Asunto','Remitente','Recibido','Adj.','Estado','Ingestado','Acciones'].map(h => (
                  <th key={h} className="px-4 py-3 text-left text-[11px] font-semibold text-slate-400 uppercase tracking-wider whitespace-nowrap">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {loading && (
                <tr><td colSpan={8} className="py-16 text-center">
                  <Spinner size="lg" className="text-blue-600 mx-auto" />
                </td></tr>
              )}
              {!loading && emails.length === 0 && (
                <tr><td colSpan={8} className="py-16 text-center text-slate-400 text-sm">
                  No se encontraron emails.
                </td></tr>
              )}
              {!loading && emails.map(email => (
                <tr key={email.id} className="hover:bg-slate-50 transition-colors group cursor-pointer" onClick={() => openDrawer(email.id)}>
                  <td className="px-4 py-3 whitespace-nowrap">
                    <Badge variant={email.source}>{email.source}</Badge>
                  </td>
                  <td className="px-4 py-3 max-w-xs">
                    <p className="text-slate-800 font-medium truncate text-sm" title={email.subject}>
                      {email.subject || '(sin asunto)'}
                    </p>
                  </td>
                  <td className="px-4 py-3 max-w-[180px]">
                    <p className="text-slate-600 truncate text-xs font-mono" title={email.sender}>
                      {email.sender || '—'}
                    </p>
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap text-xs text-slate-500">
                    {fmtDate(email.received_date)}
                  </td>
                  <td className="px-4 py-3 text-center">
                    {email.has_attachments
                      ? <PaperClipIcon className="w-4 h-4 text-amber-500 mx-auto" />
                      : <span className="text-slate-300">—</span>}
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap">
                    <Badge variant={email.status ?? 'pending'}>{email.status ?? 'pending'}</Badge>
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap text-xs text-slate-400">
                    {fmtDate(email.ingested_at)}
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap text-right" onClick={e => e.stopPropagation()}>
                    <button onClick={() => openDrawer(email.id)}
                      className="p-1.5 rounded-lg text-slate-400 hover:text-blue-600 hover:bg-blue-50 transition-colors mr-1">
                      <EyeIcon className="w-4 h-4" />
                    </button>
                    <button onClick={async () => { if(confirm('¿Eliminar este email?')) { await emailsApi.delete(email.id); load({ search, source, status, offset }) } }}
                      className="p-1.5 rounded-lg text-slate-400 hover:text-red-600 hover:bg-red-50 transition-colors">
                      <TrashIcon className="w-4 h-4" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {total > PAGE_SIZE && (
          <div className="flex items-center justify-between px-4 py-3 border-t border-slate-100 text-sm text-slate-500">
            <span>Página {Math.floor(offset/PAGE_SIZE)+1} de {Math.ceil(total/PAGE_SIZE)} — {total} total</span>
            <div className="flex gap-2">
              <Button variant="secondary" size="sm" disabled={offset===0} onClick={() => setOffset(o => Math.max(0, o-PAGE_SIZE))}>← Anterior</Button>
              <Button variant="secondary" size="sm" disabled={offset+PAGE_SIZE>=total} onClick={() => setOffset(o => o+PAGE_SIZE)}>Siguiente →</Button>
            </div>
          </div>
        )}
      </div>

      {/* Detail drawer */}
      <EmailDetailDrawer
        emailId={selectedId}
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        onDelete={() => load({ search, source, status, offset })}
      />
    </div>
  )
}
