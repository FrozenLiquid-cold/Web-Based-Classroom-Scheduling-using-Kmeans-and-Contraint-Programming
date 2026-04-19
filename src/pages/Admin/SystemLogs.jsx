import { useState, useEffect, useCallback } from 'react'

const API_URL = 'http://localhost:8000/api'

const LEVELS = ['', 'INFO', 'SUCCESS', 'WARNING', 'ERROR']
const CATEGORIES = ['', 'auth', 'schedule', 'entity', 'settings', 'system']

const levelConfig = {
    INFO: { bg: 'bg-blue-100', text: 'text-blue-700', dot: 'bg-blue-500', icon: 'ℹ️' },
    SUCCESS: { bg: 'bg-emerald-100', text: 'text-emerald-700', dot: 'bg-emerald-500', icon: '✅' },
    WARNING: { bg: 'bg-amber-100', text: 'text-amber-700', dot: 'bg-amber-500', icon: '⚠️' },
    ERROR: { bg: 'bg-rose-100', text: 'text-rose-700', dot: 'bg-rose-500', icon: '❌' },
}

const categoryIcons = {
    auth: '🔐', schedule: '📅', entity: '📦', settings: '⚙️', system: '🖥️',
}

function formatTime(isoString) {
    if (!isoString) return '—'
    const d = new Date(isoString)
    const pad = (n) => String(n).padStart(2, '0')
    const month = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][d.getMonth()]
    return `${month} ${pad(d.getDate())}, ${d.getFullYear()} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

export default function SystemLogs() {
    const [logs, setLogs] = useState([])
    const [loading, setLoading] = useState(true)
    const [total, setTotal] = useState(0)
    const [page, setPage] = useState(1)
    const [totalPages, setTotalPages] = useState(1)
    const [category, setCategory] = useState('')
    const [level, setLevel] = useState('')
    const [search, setSearch] = useState('')
    const [searchInput, setSearchInput] = useState('')
    const [autoRefresh, setAutoRefresh] = useState(false)

    const fetchLogs = useCallback(async () => {
        setLoading(true)
        try {
            const params = new URLSearchParams({ page, per_page: 50 })
            if (category) params.set('category', category)
            if (level) params.set('level', level)
            if (search) params.set('search', search)
            const res = await fetch(`${API_URL}/system-logs?${params}`)
            if (res.ok) {
                const data = await res.json()
                setLogs(data.logs || [])
                setTotal(data.total || 0)
                setTotalPages(data.total_pages || 1)
            }
        } catch (err) {
            console.error('Failed to load logs:', err)
        } finally {
            setLoading(false)
        }
    }, [page, category, level, search])

    useEffect(() => { fetchLogs() }, [fetchLogs])

    // Auto-refresh every 5s when enabled
    useEffect(() => {
        if (!autoRefresh) return
        const iv = setInterval(fetchLogs, 5000)
        return () => clearInterval(iv)
    }, [autoRefresh, fetchLogs])

    const handleSearch = (e) => {
        e.preventDefault()
        setPage(1)
        setSearch(searchInput)
    }

    const handleClearLogs = async () => {
        if (!confirm('Are you sure you want to clear ALL system logs? This action cannot be undone.')) return
        try {
            const res = await fetch(`${API_URL}/system-logs/clear`, { method: 'DELETE' })
            if (res.ok) {
                setPage(1)
                fetchLogs()
            }
        } catch (err) {
            console.error('Failed to clear logs:', err)
        }
    }

    // Stats
    const infoCount = logs.filter(l => l.level === 'INFO').length
    const successCount = logs.filter(l => l.level === 'SUCCESS').length
    const warnCount = logs.filter(l => l.level === 'WARNING').length
    const errorCount = logs.filter(l => l.level === 'ERROR').length

    return (
        <div className="space-y-6 animate-fade-in">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-3xl font-bold text-slate-800">🖥️ System Logs</h1>
                    <p className="text-slate-500 mt-1">Activity log from all system operations. {total} total entries.</p>
                </div>
                <div className="flex items-center gap-3">
                    <label className="flex items-center gap-2 text-sm font-medium text-slate-600 cursor-pointer select-none">
                        <div className={`relative w-10 h-5 rounded-full transition-colors ${autoRefresh ? 'bg-emerald-500' : 'bg-slate-300'}`} onClick={() => setAutoRefresh(!autoRefresh)}>
                            <div className={`absolute top-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform ${autoRefresh ? 'translate-x-5' : 'translate-x-0.5'}`} />
                        </div>
                        Auto-refresh
                    </label>
                    <button onClick={fetchLogs} className="px-4 py-2 bg-indigo-600 text-white font-bold text-sm rounded-xl hover:bg-indigo-700 transition-colors shadow-sm">
                        ↻ Refresh
                    </button>
                    <button onClick={handleClearLogs} className="px-4 py-2 bg-rose-100 text-rose-700 font-bold text-sm rounded-xl hover:bg-rose-200 transition-colors">
                        🗑 Clear All
                    </button>
                </div>
            </div>

            {/* Mini Stat Cards */}
            <div className="grid grid-cols-4 gap-4">
                <div className="bg-blue-50 border border-blue-200 rounded-xl p-4 flex items-center gap-3">
                    <span className="text-2xl">ℹ️</span>
                    <div>
                        <div className="text-2xl font-bold text-blue-700">{infoCount}</div>
                        <div className="text-xs font-semibold text-blue-500 uppercase">Info</div>
                    </div>
                </div>
                <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-4 flex items-center gap-3">
                    <span className="text-2xl">✅</span>
                    <div>
                        <div className="text-2xl font-bold text-emerald-700">{successCount}</div>
                        <div className="text-xs font-semibold text-emerald-500 uppercase">Success</div>
                    </div>
                </div>
                <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 flex items-center gap-3">
                    <span className="text-2xl">⚠️</span>
                    <div>
                        <div className="text-2xl font-bold text-amber-700">{warnCount}</div>
                        <div className="text-xs font-semibold text-amber-500 uppercase">Warning</div>
                    </div>
                </div>
                <div className="bg-rose-50 border border-rose-200 rounded-xl p-4 flex items-center gap-3">
                    <span className="text-2xl">❌</span>
                    <div>
                        <div className="text-2xl font-bold text-rose-700">{errorCount}</div>
                        <div className="text-xs font-semibold text-rose-500 uppercase">Error</div>
                    </div>
                </div>
            </div>

            {/* Filters */}
            <div className="bg-white/80 backdrop-blur rounded-2xl border border-slate-200 shadow-sm p-4 flex flex-wrap items-center gap-4">
                <form onSubmit={handleSearch} className="flex-1 min-w-[250px]">
                    <input
                        type="text"
                        value={searchInput}
                        onChange={(e) => setSearchInput(e.target.value)}
                        placeholder="Search logs by detail, action, or user..."
                        className="w-full px-4 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-300 transition-all"
                    />
                </form>
                <select
                    value={category}
                    onChange={(e) => { setCategory(e.target.value); setPage(1) }}
                    className="px-4 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm font-medium text-slate-700 outline-none focus:ring-2 focus:ring-indigo-500"
                >
                    <option value="">All Categories</option>
                    {CATEGORIES.filter(Boolean).map(c => <option key={c} value={c}>{categoryIcons[c] || ''} {c.charAt(0).toUpperCase() + c.slice(1)}</option>)}
                </select>
                <select
                    value={level}
                    onChange={(e) => { setLevel(e.target.value); setPage(1) }}
                    className="px-4 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm font-medium text-slate-700 outline-none focus:ring-2 focus:ring-indigo-500"
                >
                    <option value="">All Levels</option>
                    {LEVELS.filter(Boolean).map(l => <option key={l} value={l}>{levelConfig[l]?.icon || ''} {l}</option>)}
                </select>
                {(search || category || level) && (
                    <button onClick={() => { setSearch(''); setSearchInput(''); setCategory(''); setLevel(''); setPage(1) }} className="px-3 py-2 text-xs font-bold text-slate-500 hover:text-slate-700 bg-slate-100 rounded-lg">
                        ✕ Clear Filters
                    </button>
                )}
            </div>

            {/* Log Table */}
            <div className="bg-white/80 backdrop-blur rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
                {loading && logs.length === 0 ? (
                    <div className="flex flex-col items-center justify-center py-20">
                        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600 mb-3"></div>
                        <p className="text-slate-500 text-sm">Loading logs...</p>
                    </div>
                ) : logs.length === 0 ? (
                    <div className="flex flex-col items-center justify-center py-20 text-slate-400">
                        <span className="text-5xl mb-4">📋</span>
                        <p className="font-medium">No log entries found.</p>
                        <p className="text-sm">System activities will appear here.</p>
                    </div>
                ) : (
                    <>
                        {/* Column Headers */}
                        <div className="grid grid-cols-12 gap-3 px-6 py-3 text-xs font-bold text-slate-500 uppercase tracking-wide border-b border-slate-100 bg-slate-50/50">
                            <div className="col-span-2">Timestamp</div>
                            <div className="col-span-1 text-center">Level</div>
                            <div className="col-span-1 text-center">Category</div>
                            <div className="col-span-1">Action</div>
                            <div className="col-span-1">User</div>
                            <div className="col-span-6">Detail</div>
                        </div>

                        {/* Rows */}
                        <div className="divide-y divide-slate-100">
                            {logs.map((log) => {
                                const lc = levelConfig[log.level] || levelConfig.INFO
                                return (
                                    <div key={log.id} className={`grid grid-cols-12 gap-3 px-6 py-3 items-center hover:bg-slate-50/50 transition-colors ${log.level === 'ERROR' ? 'bg-rose-50/30' : log.level === 'WARNING' ? 'bg-amber-50/20' : ''}`}>
                                        <div className="col-span-2 text-xs text-slate-500 font-mono">{formatTime(log.timestamp)}</div>
                                        <div className="col-span-1 text-center">
                                            <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold ${lc.bg} ${lc.text}`}>
                                                <span className={`w-1.5 h-1.5 rounded-full ${lc.dot}`}></span>
                                                {log.level}
                                            </span>
                                        </div>
                                        <div className="col-span-1 text-center">
                                            <span className="text-sm">{categoryIcons[log.category] || '📋'}</span>
                                            <span className="text-[10px] font-medium text-slate-500 ml-1">{log.category}</span>
                                        </div>
                                        <div className="col-span-1">
                                            <span className="px-2 py-0.5 bg-slate-100 text-slate-600 rounded text-[11px] font-bold">{log.action}</span>
                                        </div>
                                        <div className="col-span-1 text-sm text-slate-600 font-medium truncate">{log.user || '—'}</div>
                                        <div className="col-span-6 text-sm text-slate-700 truncate" title={log.detail}>{log.detail || '—'}</div>
                                    </div>
                                )
                            })}
                        </div>
                    </>
                )}

                {/* Pagination */}
                {totalPages > 1 && (
                    <div className="px-6 py-4 border-t border-slate-100 bg-slate-50/50 flex items-center justify-between">
                        <div className="text-sm text-slate-500">
                            Page {page} of {totalPages} · {total} total entries
                        </div>
                        <div className="flex gap-2">
                            <button
                                disabled={page <= 1}
                                onClick={() => setPage(p => Math.max(1, p - 1))}
                                className="px-4 py-2 bg-white border border-slate-200 text-slate-600 font-bold text-sm rounded-lg hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                            >
                                ← Prev
                            </button>
                            <button
                                disabled={page >= totalPages}
                                onClick={() => setPage(p => p + 1)}
                                className="px-4 py-2 bg-white border border-slate-200 text-slate-600 font-bold text-sm rounded-lg hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                            >
                                Next →
                            </button>
                        </div>
                    </div>
                )}
            </div>
        </div>
    )
}
