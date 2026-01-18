import { useEffect, useMemo, useState } from 'react'
import { getInstructorWorkload } from '../../services/api'

export default function Dashboard() {
    const session = useMemo(() => {
        try { return JSON.parse(localStorage.getItem('jrmsu.session') || 'null') } catch { return null }
    }, [])

    const instructorId = session?.instructorId || null
    const instructorName = session?.name || 'Instructor'
    const [semester, setSemester] = useState('1')
    const [workload, setWorkload] = useState(null)
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState('')
    const [refreshTick, setRefreshTick] = useState(0)
    const [isDark, setIsDark] = useState(() => {
        const saved = localStorage.getItem('jrmsu.theme')
        return saved ? saved === 'dark' : false
    })

    useEffect(() => {
        localStorage.setItem('jrmsu.theme', isDark ? 'dark' : 'light')
    }, [isDark])

    useEffect(() => {
        let cancelled = false
        async function load() {
            if (!instructorId) {
                setWorkload(null)
                return
            }
            try {
                setLoading(true)
                setError('')
                const data = await getInstructorWorkload(instructorId, Number(semester))
                if (cancelled) return
                setWorkload(data || null)
            } catch (e) {
                if (cancelled) return
                setWorkload(null)
                setError(e?.message || 'Failed to load workload')
            } finally {
                if (!cancelled) setLoading(false)
            }
        }
        load()
        return () => { cancelled = true }
    }, [instructorId, semester, refreshTick])

    useEffect(() => {
        function onVisible() {
            if (document.visibilityState === 'visible') {
                setRefreshTick(t => t + 1)
            }
        }
        document.addEventListener('visibilitychange', onVisible)
        const timer = setInterval(() => setRefreshTick(t => t + 1), 30000)
        return () => {
            document.removeEventListener('visibilitychange', onVisible)
            clearInterval(timer)
        }
    }, [])

    const weeklyHours = Number(workload?.weekly_hours || 0)
    const limitHours = Number(workload?.limit_hours || 0)
    const overloadHours = Number(workload?.overload_hours || 0)
    const unitsTotal = Number(workload?.units_total || 0)
    const scheduleCount = Number(workload?.schedule_count || 0)
    const isOverloaded = limitHours > 0 ? weeklyHours > limitHours : false
    const percent = limitHours > 0 ? Math.min(100, Math.round((weeklyHours / limitHours) * 100)) : 0

    const size = 180
    const stroke = 14
    const r = (size - stroke) / 2
    const c = 2 * Math.PI * r
    const dash = (percent / 100) * c

    const getStatusColor = () => {
        if (isOverloaded) return { primary: '#ef4444', secondary: '#fecaca', gradient: 'from-red-500 to-rose-600' }
        if (percent >= 80) return { primary: '#f59e0b', secondary: '#fef3c7', gradient: 'from-amber-500 to-orange-500' }
        return { primary: '#10b981', secondary: '#d1fae5', gradient: 'from-emerald-500 to-teal-500' }
    }
    const colors = getStatusColor()

    const currentDate = new Date().toLocaleDateString('en-US', {
        weekday: 'long', year: 'numeric', month: 'long', day: 'numeric'
    })

    const theme = {
        bg: isDark ? 'bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900' : 'bg-gradient-to-br from-slate-50 via-white to-slate-100',
        text: isDark ? 'text-white' : 'text-slate-800',
        textMuted: isDark ? 'text-slate-400' : 'text-slate-500',
        card: isDark ? 'bg-slate-800/50 border-slate-700/50' : 'bg-white/80 border-slate-200 shadow-lg',
        input: isDark ? 'bg-slate-700/50 border-slate-600 text-white' : 'bg-white border-slate-300 text-slate-800',
        ringBg: isDark ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.1)',
    }

    return (
        <div className={`min-h-screen ${theme.bg} p-6`}>
            <div className="max-w-6xl mx-auto">
                <div className="flex flex-col md:flex-row md:items-center md:justify-between mb-8">
                    <div>
                        <h1 className={`text-3xl font-bold ${theme.text} mb-1`}>
                            Welcome back, <span className="bg-gradient-to-r from-emerald-500 to-cyan-500 bg-clip-text text-transparent">{instructorName}</span>
                        </h1>
                        <p className={theme.textMuted}>{currentDate}</p>
                    </div>
                    <div className="flex items-center gap-3 mt-4 md:mt-0">
                        <button
                            onClick={() => setIsDark(!isDark)}
                            className={`p-2.5 rounded-xl ${theme.input} border transition-all hover:scale-105`}
                            title={isDark ? 'Switch to Light Mode' : 'Switch to Dark Mode'}
                        >
                            {isDark ? (
                                <svg className="w-5 h-5 text-yellow-400" fill="currentColor" viewBox="0 0 20 20">
                                    <path fillRule="evenodd" d="M10 2a1 1 0 011 1v1a1 1 0 11-2 0V3a1 1 0 011-1zm4 8a4 4 0 11-8 0 4 4 0 018 0zm-.464 4.95l.707.707a1 1 0 001.414-1.414l-.707-.707a1 1 0 00-1.414 1.414zm2.12-10.607a1 1 0 010 1.414l-.706.707a1 1 0 11-1.414-1.414l.707-.707a1 1 0 011.414 0zM17 11a1 1 0 100-2h-1a1 1 0 100 2h1zm-7 4a1 1 0 011 1v1a1 1 0 11-2 0v-1a1 1 0 011-1zM5.05 6.464A1 1 0 106.465 5.05l-.708-.707a1 1 0 00-1.414 1.414l.707.707zm1.414 8.486l-.707.707a1 1 0 01-1.414-1.414l.707-.707a1 1 0 011.414 1.414zM4 11a1 1 0 100-2H3a1 1 0 000 2h1z" clipRule="evenodd" />
                                </svg>
                            ) : (
                                <svg className="w-5 h-5 text-slate-600" fill="currentColor" viewBox="0 0 20 20">
                                    <path d="M17.293 13.293A8 8 0 016.707 2.707a8.001 8.001 0 1010.586 10.586z" />
                                </svg>
                            )}
                        </button>
                        <select
                            className={`px-4 py-2.5 rounded-xl ${theme.input} border focus:ring-2 focus:ring-emerald-500 focus:border-transparent transition-all`}
                            value={semester}
                            onChange={e => setSemester(e.target.value)}
                        >
                            <option value="1">Semester 1</option>
                            <option value="2">Semester 2</option>
                        </select>
                        <button
                            type="button"
                            className="px-4 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-medium transition-all flex items-center gap-2 disabled:opacity-50"
                            onClick={() => setRefreshTick(t => t + 1)}
                            disabled={loading}
                        >
                            <svg className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                            </svg>
                            Refresh
                        </button>
                    </div>
                </div>

                <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
                    <div className={`lg:col-span-1 backdrop-blur-xl rounded-2xl border p-6 flex flex-col items-center justify-center ${theme.card}`}>
                        <h2 className={`text-lg font-semibold ${theme.textMuted} mb-4`}>Weekly Workload</h2>
                        <div className="relative" style={{ width: size, height: size }}>
                            <div className="absolute inset-0 rounded-full blur-xl opacity-30" style={{ background: colors.primary }} />
                            <svg width={size} height={size} className="relative block">
                                <circle cx={size / 2} cy={size / 2} r={r} stroke={theme.ringBg} strokeWidth={stroke} fill="none" />
                                <circle cx={size / 2} cy={size / 2} r={r} stroke={colors.primary} strokeWidth={stroke} fill="none" strokeLinecap="round" strokeDasharray={`${dash} ${c - dash}`} transform={`rotate(-90 ${size / 2} ${size / 2})`} className="transition-all duration-700 ease-out" />
                            </svg>
                            <div className="absolute inset-0 flex flex-col items-center justify-center text-center">
                                <div className={`text-4xl font-bold ${theme.text}`}>{weeklyHours.toFixed(1)}</div>
                                <div className={`text-sm ${theme.textMuted}`}>hours / week</div>
                                <div className="mt-2 px-3 py-1 rounded-full text-xs font-medium" style={{ background: colors.secondary, color: colors.primary }}>{percent}% of limit</div>
                            </div>
                        </div>
                        <div className={`mt-4 text-center ${theme.textMuted}`}>
                            <span>Limit: </span>
                            <span className={`${theme.text} font-semibold`}>{limitHours} hours</span>
                        </div>
                    </div>

                    <div className="lg:col-span-2 grid grid-cols-2 gap-4">
                        <div className={`backdrop-blur-xl rounded-2xl border p-6 ${isDark ? 'bg-gradient-to-br from-blue-600/20 to-cyan-600/20 border-blue-500/20' : 'bg-gradient-to-br from-blue-50 to-cyan-50 border-blue-200'}`}>
                            <div className="flex items-center gap-4">
                                <div className={`w-14 h-14 rounded-xl flex items-center justify-center ${isDark ? 'bg-blue-500/20' : 'bg-blue-100'}`}>
                                    <svg className="w-7 h-7 text-blue-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                                    </svg>
                                </div>
                                <div>
                                    <p className={theme.textMuted + ' text-sm'}>Scheduled Classes</p>
                                    <p className={`text-3xl font-bold ${theme.text}`}>{scheduleCount}</p>
                                </div>
                            </div>
                        </div>

                        <div className={`backdrop-blur-xl rounded-2xl border p-6 ${isDark ? 'bg-gradient-to-br from-purple-600/20 to-pink-600/20 border-purple-500/20' : 'bg-gradient-to-br from-purple-50 to-pink-50 border-purple-200'}`}>
                            <div className="flex items-center gap-4">
                                <div className={`w-14 h-14 rounded-xl flex items-center justify-center ${isDark ? 'bg-purple-500/20' : 'bg-purple-100'}`}>
                                    <svg className="w-7 h-7 text-purple-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
                                    </svg>
                                </div>
                                <div>
                                    <p className={theme.textMuted + ' text-sm'}>Total Units</p>
                                    <p className={`text-3xl font-bold ${theme.text}`}>{unitsTotal}</p>
                                </div>
                            </div>
                        </div>

                        <div className={`backdrop-blur-xl rounded-2xl border p-6 ${overloadHours > 0 ? (isDark ? 'bg-gradient-to-br from-red-600/20 to-orange-600/20 border-red-500/20' : 'bg-gradient-to-br from-red-50 to-orange-50 border-red-200') : (isDark ? 'bg-gradient-to-br from-emerald-600/20 to-teal-600/20 border-emerald-500/20' : 'bg-gradient-to-br from-emerald-50 to-teal-50 border-emerald-200')}`}>
                            <div className="flex items-center gap-4">
                                <div className={`w-14 h-14 rounded-xl flex items-center justify-center ${overloadHours > 0 ? (isDark ? 'bg-red-500/20' : 'bg-red-100') : (isDark ? 'bg-emerald-500/20' : 'bg-emerald-100')}`}>
                                    <svg className={`w-7 h-7 ${overloadHours > 0 ? 'text-red-500' : 'text-emerald-500'}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                                    </svg>
                                </div>
                                <div>
                                    <p className={theme.textMuted + ' text-sm'}>Overload Hours</p>
                                    <p className={`text-3xl font-bold ${theme.text}`}>{overloadHours.toFixed(1)}</p>
                                </div>
                            </div>
                        </div>

                        <div className={`bg-gradient-to-br ${colors.gradient} rounded-2xl p-6 flex flex-col justify-center`}>
                            <p className="text-white/80 text-sm mb-1">Current Status</p>
                            <p className="text-2xl font-bold text-white">
                                {isOverloaded ? '⚠️ Overloaded' : percent >= 80 ? '📊 Near Limit' : '✅ Normal'}
                            </p>
                            <p className="text-white/70 text-sm mt-1">
                                {workload?.employment_type === 'visiting' ? 'Visiting Lecturer' : workload?.designation || 'Regular Faculty'}
                            </p>
                        </div>
                    </div>
                </div>

                {workload && Array.isArray(workload.warnings) && workload.warnings.length > 0 && (
                    <div className={`backdrop-blur-xl rounded-2xl border p-5 mb-8 ${isDark ? 'bg-red-500/10 border-red-500/30' : 'bg-red-50 border-red-200'}`}>
                        <div className="flex items-start gap-3">
                            <div className={`flex-shrink-0 w-10 h-10 rounded-xl flex items-center justify-center ${isDark ? 'bg-red-500/20' : 'bg-red-100'}`}>
                                <svg className="w-5 h-5 text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                                </svg>
                            </div>
                            <div className="flex-1">
                                <h3 className="text-red-500 font-semibold mb-2">Important Notices</h3>
                                <div className="space-y-2">
                                    {workload.warnings.map((w, idx) => (
                                        <p key={idx} className={isDark ? 'text-red-300 text-sm' : 'text-red-600 text-sm'}>{w}</p>
                                    ))}
                                </div>
                            </div>
                        </div>
                    </div>
                )}

                {error && (
                    <div className={`backdrop-blur-xl rounded-2xl border p-5 mb-8 text-center ${isDark ? 'bg-red-500/10 border-red-500/30' : 'bg-red-50 border-red-200'}`}>
                        <p className="text-red-500">{error}</p>
                    </div>
                )}

                {loading && (
                    <div className="flex items-center justify-center py-12">
                        <div className={`flex items-center gap-3 ${theme.textMuted}`}>
                            <svg className="w-6 h-6 animate-spin" fill="none" viewBox="0 0 24 24">
                                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                            </svg>
                            <span>Loading workload data...</span>
                        </div>
                    </div>
                )}

                <div className="mt-12 flex flex-col items-center">
                    <img src="/assets/jrmsu-logo.png" alt="JRMSU" className="w-24 h-24 object-contain opacity-80 hover:opacity-100 transition-opacity" onError={(e) => { e.currentTarget.style.display = 'none' }} />
                    <div className="mt-4 text-emerald-500 font-oswald uppercase tracking-wider text-lg">Jose Rizal Memorial State University</div>
                    <div className="mt-2 text-center">
                        <div className={theme.textMuted + ' text-sm'}>Classroom Scheduling System</div>
                    </div>
                </div>
            </div>
        </div>
    )
}
