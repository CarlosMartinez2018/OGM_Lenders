const variants = {
  pending:    'bg-amber-100 text-amber-800',
  classified: 'bg-emerald-100 text-emerald-800',
  processed:  'bg-blue-100 text-blue-800',
  reviewed:   'bg-purple-100 text-purple-800',
  corrected:  'bg-indigo-100 text-indigo-800',
  error:      'bg-red-100 text-red-800',
  active:     'bg-emerald-100 text-emerald-800',
  inactive:   'bg-slate-100 text-slate-500',
  high:       'bg-emerald-100 text-emerald-800',
  medium:     'bg-amber-100 text-amber-800',
  low:        'bg-red-100 text-red-800',
  outlook:    'bg-blue-100 text-blue-700',
  file:       'bg-slate-100 text-slate-600',
  navy:       'bg-navy-100 text-navy-800',
}

export default function Badge({ variant = 'pending', children, className = '' }) {
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded-md text-xs font-semibold ${variants[variant] ?? 'bg-slate-100 text-slate-600'} ${className}`}
    >
      {children}
    </span>
  )
}
