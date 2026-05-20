import { useState, useEffect, useCallback, useRef } from 'react'
import {
  MagnifyingGlassIcon,
  PlusIcon,
  PencilSquareIcon,
  TrashIcon,
  ArrowPathIcon,
  CircleStackIcon,
  ChevronDownIcon,
  ChevronUpIcon,
  XMarkIcon,
  ExclamationTriangleIcon,
  BuildingLibraryIcon,
  CheckCircleIcon,
} from '@heroicons/react/24/outline'
import { lendersApi } from '../lib/api'
import Badge from '../components/ui/Badge'
import Button from '../components/ui/Button'
import Modal from '../components/ui/Modal'
import Spinner from '../components/ui/Spinner'

// ── Tag input ─────────────────────────────────────────────────────
function TagInput({ label, placeholder, values, onChange }) {
  const [draft, setDraft] = useState('')
  const inputRef = useRef(null)

  function add() {
    const v = draft.trim()
    if (v && !values.includes(v)) onChange([...values, v])
    setDraft('')
  }

  function remove(tag) {
    onChange(values.filter(t => t !== tag))
  }

  return (
    <div>
      <label className="block text-sm font-medium text-slate-700 mb-1.5">{label}</label>
      <div
        className="min-h-[40px] flex flex-wrap gap-1.5 px-3 py-2 rounded-lg border border-slate-200 bg-white cursor-text"
        onClick={() => inputRef.current?.focus()}
      >
        {values.map(tag => (
          <span key={tag} className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-blue-50 text-blue-700 text-xs font-medium">
            {tag}
            <button type="button" onClick={e => { e.stopPropagation(); remove(tag) }} className="text-blue-400 hover:text-blue-700">
              <XMarkIcon className="w-3 h-3" />
            </button>
          </span>
        ))}
        <input
          ref={inputRef}
          type="text"
          value={draft}
          onChange={e => setDraft(e.target.value)}
          onKeyDown={e => {
            if (e.key === 'Enter' || e.key === ',') { e.preventDefault(); add() }
            if (e.key === 'Backspace' && !draft && values.length) remove(values[values.length - 1])
          }}
          placeholder={values.length === 0 ? placeholder : ''}
          className="flex-1 min-w-[100px] bg-transparent text-sm text-slate-800 outline-none placeholder:text-slate-400"
        />
      </div>
      <p className="text-xs text-slate-400 mt-1">Presiona Enter o coma para agregar</p>
    </div>
  )
}

// ── Empty waiver template ─────────────────────────────────────────
function emptyWaiver() {
  return {
    _key: Date.now(),
    id: undefined,
    waiver_type: '',
    triggers: '',
    evidence_required_ops: '',
    evidence_required_insurance: '',
    documents_expected: '',
    actions_to_automate: '',
    waiver_pack: '',
    is_active: true,
  }
}

// ── Single waiver accordion card ──────────────────────────────────
function WaiverCard({ waiver, index, onChange, onRemove }) {
  const [open, setOpen] = useState(!waiver.id)

  function field(key) {
    return (
      <div key={key}>
        <label className="block text-xs font-medium text-slate-500 mb-1 capitalize">
          {key.replace(/_/g, ' ')}
        </label>
        <textarea
          rows={2}
          value={waiver[key] ?? ''}
          onChange={e => onChange({ ...waiver, [key]: e.target.value })}
          className="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
        />
      </div>
    )
  }

  return (
    <div className="rounded-lg border border-slate-200 overflow-hidden">
      <div
        className="flex items-center justify-between px-4 py-2.5 bg-slate-50 cursor-pointer select-none"
        onClick={() => setOpen(o => !o)}
      >
        <div className="flex items-center gap-2">
          {open ? <ChevronUpIcon className="w-3.5 h-3.5 text-slate-400" /> : <ChevronDownIcon className="w-3.5 h-3.5 text-slate-400" />}
          <span className="text-sm font-medium text-slate-700">
            {waiver.waiver_type || `Waiver ${index + 1}`}
          </span>
          {!waiver.is_active && <Badge variant="inactive">inactivo</Badge>}
        </div>
        <button
          type="button"
          onClick={e => { e.stopPropagation(); onRemove() }}
          className="p-1 rounded text-slate-300 hover:text-red-500 hover:bg-red-50 transition-colors"
        >
          <XMarkIcon className="w-3.5 h-3.5" />
        </button>
      </div>

      {open && (
        <div className="px-4 py-4 space-y-3">
          <div>
            <label className="block text-xs font-medium text-slate-700 mb-1">Waiver type <span className="text-red-500">*</span></label>
            <input
              type="text"
              value={waiver.waiver_type}
              onChange={e => onChange({ ...waiver, waiver_type: e.target.value })}
              className="w-full rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="Ej. Credit Score Waiver"
            />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {['triggers', 'evidence_required_ops', 'evidence_required_insurance', 'documents_expected', 'actions_to_automate', 'waiver_pack'].map(k => field(k))}
          </div>

          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={waiver.is_active}
              onChange={e => onChange({ ...waiver, is_active: e.target.checked })}
              className="rounded text-blue-600"
            />
            <span className="text-sm text-slate-600">Activo</span>
          </label>
        </div>
      )}
    </div>
  )
}

// ── Lender modal (tabbed) ─────────────────────────────────────────
const TABS = ['Información', 'Aliases & Dominios', 'Waivers']

function LenderModal({ open, onClose, lender, onSaved }) {
  const [tab, setTab] = useState(0)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)

  // Form state
  const [name, setName]           = useState('')
  const [firstName, setFirstName] = useState('')
  const [lastName, setLastName]   = useState('')
  const [email, setEmail]         = useState('')
  const [phone, setPhone]         = useState('')
  const [notes, setNotes]         = useState('')
  const [isActive, setIsActive]   = useState(true)
  const [aliases, setAliases]     = useState([])
  const [domains, setDomains]     = useState([])
  const [waivers, setWaivers]     = useState([])

  const isEdit = Boolean(lender)

  useEffect(() => {
    if (!open) return
    setTab(0)
    setError(null)
    if (lender) {
      setName(lender.name ?? '')
      setFirstName(lender.first_name ?? '')
      setLastName(lender.last_name ?? '')
      setEmail(lender.email ?? '')
      setPhone(lender.phone ?? '')
      setNotes(lender.notes ?? '')
      setIsActive(lender.is_active ?? true)
      setAliases(lender.aliases ?? [])
      setDomains(lender.domains ?? [])
      setWaivers((lender.waivers ?? []).map(w => ({ ...w, _key: w.id ?? Date.now() + Math.random() })))
    } else {
      setName(''); setFirstName(''); setLastName(''); setEmail('')
      setPhone(''); setNotes(''); setIsActive(true); setAliases([])
      setDomains([]); setWaivers([])
    }
  }, [open, lender])

  function updateWaiver(idx, updated) {
    setWaivers(ws => ws.map((w, i) => i === idx ? updated : w))
  }

  function removeWaiver(idx) {
    setWaivers(ws => ws.filter((_, i) => i !== idx))
  }

  async function handleSubmit(e) {
    e.preventDefault()
    if (!name.trim()) { setError('El nombre del lender es obligatorio.'); setTab(0); return }
    const invalidWaivers = waivers.filter(w => !w.waiver_type.trim())
    if (invalidWaivers.length) { setError('Todos los waivers deben tener un tipo.'); setTab(2); return }

    setSaving(true)
    setError(null)
    try {
      const payload = {
        name: name.trim(),
        first_name: firstName || null,
        last_name: lastName || null,
        email: email || null,
        phone: phone || null,
        notes: notes || null,
        is_active: isActive,
        aliases,
        domains,
        waivers: waivers.map(({ _key, ...rest }) => rest),
      }
      if (isEdit) {
        await lendersApi.update(lender.id, payload)
      } else {
        await lendersApi.create(payload)
      }
      onSaved()
      onClose()
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={isEdit ? `Editar: ${lender?.name}` : 'Nuevo Lender'}
      size="max-w-3xl"
    >
      <form onSubmit={handleSubmit} className="flex flex-col" style={{ maxHeight: '75vh' }}>
        {/* Tab bar */}
        <div className="flex border-b border-slate-200 px-6 gap-1 shrink-0">
          {TABS.map((t, i) => (
            <button
              key={t}
              type="button"
              onClick={() => setTab(i)}
              className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors -mb-px ${
                tab === i
                  ? 'border-blue-600 text-blue-600'
                  : 'border-transparent text-slate-500 hover:text-slate-700'
              }`}
            >
              {t}
              {i === 2 && waivers.length > 0 && (
                <span className="ml-1.5 px-1.5 py-0.5 rounded-full bg-slate-100 text-xs text-slate-600">
                  {waivers.length}
                </span>
              )}
            </button>
          ))}
        </div>

        {/* Tab content (single scroll) */}
        <div className="overflow-y-auto flex-1 px-6 py-5">

          {/* Tab 0 — Información */}
          {tab === 0 && (
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">
                  Nombre <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  value={name}
                  onChange={e => setName(e.target.value)}
                  className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="Ej. Chase Bank"
                  autoFocus
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                {[
                  { label: 'Nombre de contacto', value: firstName, set: setFirstName, placeholder: 'John' },
                  { label: 'Apellido de contacto', value: lastName, set: setLastName, placeholder: 'Doe' },
                ].map(f => (
                  <div key={f.label}>
                    <label className="block text-sm font-medium text-slate-700 mb-1">{f.label}</label>
                    <input
                      type="text"
                      value={f.value}
                      onChange={e => f.set(e.target.value)}
                      placeholder={f.placeholder}
                      className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                  </div>
                ))}
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">Email</label>
                  <input
                    type="email"
                    value={email}
                    onChange={e => setEmail(e.target.value)}
                    placeholder="contact@lender.com"
                    className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">Teléfono</label>
                  <input
                    type="text"
                    value={phone}
                    onChange={e => setPhone(e.target.value)}
                    placeholder="+1 (555) 000-0000"
                    className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Notas</label>
                <textarea
                  rows={3}
                  value={notes}
                  onChange={e => setNotes(e.target.value)}
                  placeholder="Información adicional…"
                  className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
                />
              </div>

              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={isActive}
                  onChange={e => setIsActive(e.target.checked)}
                  className="w-4 h-4 rounded text-blue-600"
                />
                <span className="text-sm text-slate-700 font-medium">Lender activo</span>
              </label>
            </div>
          )}

          {/* Tab 1 — Aliases & Dominios */}
          {tab === 1 && (
            <div className="space-y-6">
              <div className="rounded-lg bg-blue-50 border border-blue-100 px-4 py-3 text-sm text-blue-700">
                Los aliases y dominios permiten al agente IA reconocer variantes del nombre del lender en los emails.
              </div>
              <TagInput
                label="Aliases del lender"
                placeholder="Escribe un alias y presiona Enter…"
                values={aliases}
                onChange={setAliases}
              />
              <TagInput
                label="Dominios de email"
                placeholder="Ej. chase.com, jpmorgan.com…"
                values={domains}
                onChange={setDomains}
              />
            </div>
          )}

          {/* Tab 2 — Waivers */}
          {tab === 2 && (
            <div className="space-y-3">
              {waivers.length === 0 && (
                <div className="rounded-lg border border-dashed border-slate-200 px-6 py-10 text-center">
                  <BuildingLibraryIcon className="w-8 h-8 text-slate-300 mx-auto mb-2" />
                  <p className="text-sm text-slate-500 font-medium">Sin waivers configurados</p>
                  <p className="text-xs text-slate-400 mt-1">Agrega los tipos de waiver que maneja este lender.</p>
                </div>
              )}

              {waivers.map((w, i) => (
                <WaiverCard
                  key={w._key}
                  waiver={w}
                  index={i}
                  onChange={updated => updateWaiver(i, updated)}
                  onRemove={() => removeWaiver(i)}
                />
              ))}

              <button
                type="button"
                onClick={() => setWaivers(ws => [...ws, emptyWaiver()])}
                className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg border border-dashed border-blue-300 text-blue-600 text-sm font-medium hover:bg-blue-50 transition-colors"
              >
                <PlusIcon className="w-4 h-4" />
                Agregar waiver
              </button>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between px-6 py-4 border-t border-slate-200 shrink-0">
          <div className="flex-1">
            {error && (
              <p className="text-sm text-red-600 flex items-center gap-1.5">
                <ExclamationTriangleIcon className="w-4 h-4 shrink-0" />
                {error}
              </p>
            )}
          </div>
          <div className="flex gap-3">
            <Button variant="secondary" type="button" onClick={onClose} disabled={saving}>
              Cancelar
            </Button>
            <Button variant="primary" type="submit" loading={saving}>
              {isEdit ? 'Guardar cambios' : 'Crear lender'}
            </Button>
          </div>
        </div>
      </form>
    </Modal>
  )
}

// ── Delete confirm modal ──────────────────────────────────────────
function DeleteModal({ open, onClose, lender, onDeleted }) {
  const [deleting, setDeleting] = useState(false)
  const [error, setError] = useState(null)

  async function handleDelete() {
    setDeleting(true)
    setError(null)
    try {
      await lendersApi.delete(lender.id)
      onDeleted()
      onClose()
    } catch (err) {
      setError(err.message)
      setDeleting(false)
    }
  }

  return (
    <Modal open={open} onClose={onClose} title="Eliminar lender" size="max-w-md">
      <div className="px-6 py-5 space-y-4">
        <p className="text-sm text-slate-700">
          ¿Confirmas que deseas eliminar <strong>{lender?.name}</strong>? Esta acción eliminará también todos sus aliases, dominios y waivers.
        </p>
        {error && (
          <p className="text-sm text-red-600 flex items-center gap-1.5">
            <ExclamationTriangleIcon className="w-4 h-4 shrink-0" />
            {error}
          </p>
        )}
        <div className="flex justify-end gap-3">
          <Button variant="secondary" onClick={onClose} disabled={deleting}>Cancelar</Button>
          <Button variant="danger" onClick={handleDelete} loading={deleting}>Eliminar</Button>
        </div>
      </div>
    </Modal>
  )
}

// ── Main page ─────────────────────────────────────────────────────
export default function LendersPage() {
  const [lenders, setLenders] = useState([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [modalOpen, setModalOpen] = useState(false)
  const [editLender, setEditLender] = useState(null)
  const [deleteTarget, setDeleteTarget] = useState(null)
  const [deleteOpen, setDeleteOpen] = useState(false)
  const [seeding, setSeeding] = useState(false)
  const [seedMsg, setSeedMsg] = useState(null)
  const [actionError, setActionError] = useState(null)

  const loadLenders = useCallback(async () => {
    setLoading(true)
    try {
      const data = await lendersApi.list()
      setLenders(Array.isArray(data) ? data : [])
    } catch {
      setLenders([])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { loadLenders() }, [loadLenders])

  async function handleSeed() {
    setSeeding(true)
    setSeedMsg(null)
    setActionError(null)
    try {
      const res = await lendersApi.seed()
      setSeedMsg(res?.message ?? 'Seed completado.')
      loadLenders()
    } catch (err) {
      setActionError(err.message)
    } finally {
      setSeeding(false)
    }
  }

  function openCreate() {
    setEditLender(null)
    setModalOpen(true)
  }

  function openEdit(lender) {
    setEditLender(lender)
    setModalOpen(true)
  }

  function openDelete(lender) {
    setDeleteTarget(lender)
    setDeleteOpen(true)
  }

  const filtered = lenders.filter(l =>
    !search ||
    l.name.toLowerCase().includes(search.toLowerCase()) ||
    (l.aliases ?? []).some(a => a.toLowerCase().includes(search.toLowerCase())) ||
    (l.domains ?? []).some(d => d.toLowerCase().includes(search.toLowerCase()))
  )

  const activeCount   = lenders.filter(l => l.is_active).length
  const inactiveCount = lenders.length - activeCount
  const waiverTotal   = lenders.reduce((acc, l) => acc + (l.waivers?.length ?? 0), 0)

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-slate-900">Lenders</h1>
          <p className="text-sm text-slate-500 mt-0.5">
            Base de conocimiento del agente IA — {lenders.length} lenders, {waiverTotal} waivers configurados.
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            variant="secondary"
            size="sm"
            onClick={handleSeed}
            loading={seeding}
            title="Poblar desde la matriz de lenders y waivers"
          >
            <CircleStackIcon className="w-4 h-4" />
            Seed matrix
          </Button>
          <Button variant="navy" size="sm" onClick={openCreate}>
            <PlusIcon className="w-4 h-4" />
            Nuevo lender
          </Button>
        </div>
      </div>

      {/* Mini stats */}
      <div className="flex gap-4">
        {[
          { label: 'Total', value: lenders.length, color: 'text-slate-900' },
          { label: 'Activos', value: activeCount, color: 'text-emerald-600' },
          { label: 'Inactivos', value: inactiveCount, color: 'text-slate-400' },
          { label: 'Waivers', value: waiverTotal, color: 'text-blue-600' },
        ].map(s => (
          <div key={s.label} className="bg-white rounded-xl border border-slate-200 px-4 py-3 min-w-[100px]">
            <p className="text-xs text-slate-400 font-medium">{s.label}</p>
            <p className={`text-2xl font-bold ${s.color}`}>{s.value}</p>
          </div>
        ))}
      </div>

      {/* Search */}
      <div className="relative max-w-sm">
        <MagnifyingGlassIcon className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none" />
        <input
          type="text"
          placeholder="Buscar lender, alias o dominio…"
          value={search}
          onChange={e => setSearch(e.target.value)}
          className="w-full pl-9 pr-3 py-2 rounded-lg border border-slate-200 bg-white text-sm text-slate-800 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
      </div>

      {/* Feedback messages */}
      {seedMsg && (
        <div className="flex items-center gap-2 px-4 py-3 rounded-lg bg-emerald-50 border border-emerald-200 text-sm text-emerald-700">
          <CheckCircleIcon className="w-4 h-4 shrink-0" />
          {seedMsg}
        </div>
      )}
      {actionError && (
        <div className="flex items-center gap-2 px-4 py-3 rounded-lg bg-red-50 border border-red-200 text-sm text-red-700">
          <ExclamationTriangleIcon className="w-4 h-4 shrink-0" />
          {actionError}
        </div>
      )}

      {/* Table */}
      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
        {loading ? (
          <div className="flex items-center justify-center py-16 gap-3 text-slate-400">
            <Spinner size="md" />
            <span className="text-sm">Cargando lenders…</span>
          </div>
        ) : filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 text-slate-400">
            <BuildingLibraryIcon className="w-10 h-10 mb-3 opacity-30" />
            <p className="text-sm font-medium">
              {search ? 'Sin resultados para tu búsqueda.' : 'No hay lenders registrados.'}
            </p>
            {!search && (
              <p className="text-xs mt-1">Haz clic en "Seed matrix" para poblar desde la matriz predefinida.</p>
            )}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-100 bg-slate-50">
                  {['Lender', 'Contacto', 'Aliases', 'Dominios', 'Waivers', 'Estado', ''].map(h => (
                    <th key={h} className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wide whitespace-nowrap">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-50">
                {filtered.map(lender => (
                  <tr key={lender.id} className="hover:bg-slate-50/70 transition-colors group">
                    {/* Name */}
                    <td className="px-4 py-3">
                      <p className="font-semibold text-slate-900">{lender.name}</p>
                      {lender.notes && (
                        <p className="text-xs text-slate-400 truncate max-w-[200px]" title={lender.notes}>
                          {lender.notes}
                        </p>
                      )}
                    </td>

                    {/* Contact */}
                    <td className="px-4 py-3 text-xs text-slate-500">
                      {lender.email && <p className="font-mono">{lender.email}</p>}
                      {lender.phone && <p>{lender.phone}</p>}
                      {!lender.email && !lender.phone && <span className="text-slate-300">—</span>}
                    </td>

                    {/* Aliases */}
                    <td className="px-4 py-3">
                      <div className="flex flex-wrap gap-1 max-w-[180px]">
                        {(lender.aliases ?? []).slice(0, 3).map(a => (
                          <span key={a} className="px-1.5 py-0.5 rounded bg-slate-100 text-xs text-slate-600">{a}</span>
                        ))}
                        {(lender.aliases?.length ?? 0) > 3 && (
                          <span className="px-1.5 py-0.5 rounded bg-slate-100 text-xs text-slate-400">
                            +{lender.aliases.length - 3}
                          </span>
                        )}
                        {(lender.aliases?.length ?? 0) === 0 && <span className="text-slate-300 text-xs">—</span>}
                      </div>
                    </td>

                    {/* Domains */}
                    <td className="px-4 py-3">
                      <div className="flex flex-wrap gap-1 max-w-[160px]">
                        {(lender.domains ?? []).slice(0, 2).map(d => (
                          <span key={d} className="px-1.5 py-0.5 rounded bg-blue-50 text-xs text-blue-600 font-mono">{d}</span>
                        ))}
                        {(lender.domains?.length ?? 0) > 2 && (
                          <span className="px-1.5 py-0.5 rounded bg-blue-50 text-xs text-blue-400">
                            +{lender.domains.length - 2}
                          </span>
                        )}
                        {(lender.domains?.length ?? 0) === 0 && <span className="text-slate-300 text-xs">—</span>}
                      </div>
                    </td>

                    {/* Waivers count */}
                    <td className="px-4 py-3">
                      <span className="inline-flex items-center justify-center w-7 h-7 rounded-full bg-navy-50 text-navy-700 text-xs font-bold">
                        {lender.waivers?.length ?? 0}
                      </span>
                    </td>

                    {/* Status */}
                    <td className="px-4 py-3">
                      <Badge variant={lender.is_active ? 'active' : 'inactive'}>
                        {lender.is_active ? 'activo' : 'inactivo'}
                      </Badge>
                    </td>

                    {/* Actions */}
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                        <button
                          onClick={() => openEdit(lender)}
                          className="p-1.5 rounded-lg text-slate-400 hover:text-blue-600 hover:bg-blue-50 transition-colors"
                          title="Editar"
                        >
                          <PencilSquareIcon className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => openDelete(lender)}
                          className="p-1.5 rounded-lg text-slate-400 hover:text-red-600 hover:bg-red-50 transition-colors"
                          title="Eliminar"
                        >
                          <TrashIcon className="w-4 h-4" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Lender modal */}
      <LenderModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        lender={editLender}
        onSaved={loadLenders}
      />

      {/* Delete confirm */}
      <DeleteModal
        open={deleteOpen}
        onClose={() => setDeleteOpen(false)}
        lender={deleteTarget}
        onDeleted={loadLenders}
      />
    </div>
  )
}
