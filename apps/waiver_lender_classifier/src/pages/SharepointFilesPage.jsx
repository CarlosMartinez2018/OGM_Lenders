import { useState, useEffect, useCallback } from 'react'
import {
  MagnifyingGlassIcon,
  ArrowPathIcon,
  ArrowTopRightOnSquareIcon,
  DocumentIcon,
  FolderIcon,
} from '@heroicons/react/24/outline'
import { sharepointApi } from '../lib/api'
import Button from '../components/ui/Button'
import Spinner from '../components/ui/Spinner'

function humanSize(bytes) {
  if (bytes == null) return '—'
  const units = ['B', 'KB', 'MB', 'GB']
  let i = 0
  let n = bytes
  while (n >= 1024 && i < units.length - 1) { n /= 1024; i++ }
  return `${n.toFixed(n >= 100 || i === 0 ? 0 : 1)} ${units[i]}`
}

function formatDate(iso) {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleString('es-CO', {
      year: 'numeric', month: '2-digit', day: '2-digit',
      hour: '2-digit', minute: '2-digit',
    })
  } catch {
    return iso
  }
}

export default function SharepointFilesPage() {
  const [drives, setDrives] = useState([])
  const [files, setFiles] = useState([])
  const [query, setQuery] = useState('')
  const [driveFilter, setDriveFilter] = useState('')
  const [loading, setLoading] = useState(false)
  const [syncing, setSyncing] = useState(false)
  const [error, setError] = useState(null)
  const [syncMsg, setSyncMsg] = useState(null)

  const loadDrives = useCallback(async () => {
    try {
      const d = await sharepointApi.drives()
      setDrives(d)
    } catch (e) {
      setError(e.message)
    }
  }, [])

  const loadFiles = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await sharepointApi.list({
        q: query || undefined,
        drive: driveFilter || undefined,
        only_files: true,
        limit: 200,
      })
      setFiles(data)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [query, driveFilter])

  useEffect(() => { loadDrives() }, [loadDrives])

  // Debounce the search input
  useEffect(() => {
    const t = setTimeout(loadFiles, 300)
    return () => clearTimeout(t)
  }, [loadFiles])

  async function handleSync() {
    setSyncing(true)
    setSyncMsg(null)
    setError(null)
    try {
      const r = await sharepointApi.sync()
      setSyncMsg(
        `Sincronizacion OK: ${r.items_seen} items (${r.files_added} nuevos, ` +
        `${r.files_updated} actualizados) en ${r.took_seconds}s.`
      )
      await loadDrives()
      await loadFiles()
    } catch (e) {
      setError(e.message)
    } finally {
      setSyncing(false)
    }
  }

  return (
    <div className="p-6 space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-slate-800">SharePoint</h1>
          <p className="text-sm text-slate-500">
            Inventario de archivos sincronizado desde Microsoft Graph.
          </p>
        </div>
        <Button onClick={handleSync} disabled={syncing}>
          <ArrowPathIcon className={`w-4 h-4 ${syncing ? 'animate-spin' : ''}`} />
          {syncing ? 'Sincronizando...' : 'Sincronizar ahora'}
        </Button>
      </div>

      {/* Drive summary */}
      {drives.length > 0 && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          {drives.map(d => (
            <div
              key={d.drive_name}
              className="bg-white border border-slate-200 rounded-lg p-3"
            >
              <p className="text-xs text-slate-500 truncate" title={d.drive_name}>
                {d.drive_name}
              </p>
              <p className="text-xl font-semibold text-slate-800">{d.files}</p>
              <p className="text-[10px] text-slate-400">
                archivos · {d.folders} carpetas
              </p>
            </div>
          ))}
        </div>
      )}

      {/* Filters */}
      <div className="bg-white border border-slate-200 rounded-lg p-3 flex flex-wrap gap-3 items-center">
        <div className="relative flex-1 min-w-[260px]">
          <MagnifyingGlassIcon className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={query}
            onChange={e => setQuery(e.target.value)}
            placeholder="Buscar por nombre o ruta..."
            className="w-full pl-9 pr-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <select
          value={driveFilter}
          onChange={e => setDriveFilter(e.target.value)}
          className="px-3 py-2 text-sm border border-slate-200 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="">Todas las bibliotecas</option>
          {drives.map(d => (
            <option key={d.drive_name} value={d.drive_name}>
              {d.drive_name}
            </option>
          ))}
        </select>
      </div>

      {/* Messages */}
      {syncMsg && (
        <div className="text-sm px-3 py-2 rounded-lg bg-green-50 text-green-800 border border-green-200">
          {syncMsg}
        </div>
      )}
      {error && (
        <div className="text-sm px-3 py-2 rounded-lg bg-red-50 text-red-800 border border-red-200">
          {error}
        </div>
      )}

      {/* Table */}
      <div className="bg-white border border-slate-200 rounded-lg overflow-hidden">
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead className="bg-slate-50 text-slate-600">
              <tr>
                <th className="text-left font-medium px-4 py-2.5">Nombre</th>
                <th className="text-left font-medium px-4 py-2.5">Ruta</th>
                <th className="text-left font-medium px-4 py-2.5">Biblioteca</th>
                <th className="text-left font-medium px-4 py-2.5">Tipo</th>
                <th className="text-right font-medium px-4 py-2.5">Tamano</th>
                <th className="text-left font-medium px-4 py-2.5">Modificado</th>
                <th className="px-4 py-2.5"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {loading && (
                <tr><td colSpan={7} className="text-center py-8"><Spinner /></td></tr>
              )}
              {!loading && files.length === 0 && (
                <tr><td colSpan={7} className="text-center py-8 text-slate-400">
                  Sin resultados. {drives.length === 0 && 'Haz click en Sincronizar para empezar.'}
                </td></tr>
              )}
              {!loading && files.map(f => (
                <tr key={f.id} className="hover:bg-slate-50">
                  <td className="px-4 py-2">
                    <div className="flex items-center gap-2">
                      {f.is_folder
                        ? <FolderIcon className="w-4 h-4 text-amber-500 shrink-0" />
                        : <DocumentIcon className="w-4 h-4 text-slate-400 shrink-0" />}
                      <span className="text-slate-800 truncate max-w-md" title={f.name}>
                        {f.name}
                      </span>
                    </div>
                  </td>
                  <td className="px-4 py-2 text-slate-500">
                    <span title={f.path} className="block truncate max-w-md">{f.path}</span>
                  </td>
                  <td className="px-4 py-2 text-slate-600">{f.drive_name}</td>
                  <td className="px-4 py-2 text-slate-500 uppercase text-xs">
                    {f.file_extension || (f.is_folder ? 'folder' : '—')}
                  </td>
                  <td className="px-4 py-2 text-right text-slate-500 tabular-nums">
                    {humanSize(f.size)}
                  </td>
                  <td className="px-4 py-2 text-slate-500 whitespace-nowrap">
                    {formatDate(f.sp_modified_at)}
                  </td>
                  <td className="px-4 py-2">
                    {f.web_url && (
                      <a
                        href={f.web_url}
                        target="_blank"
                        rel="noreferrer"
                        title="Abrir en SharePoint"
                        className="inline-flex items-center text-blue-600 hover:text-blue-800"
                      >
                        <ArrowTopRightOnSquareIcon className="w-4 h-4" />
                      </a>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {files.length > 0 && (
          <div className="px-4 py-2 text-xs text-slate-400 border-t border-slate-100">
            Mostrando {files.length} resultado(s). Limite por consulta: 200.
          </div>
        )}
      </div>
    </div>
  )
}
