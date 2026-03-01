import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { getAdminStats, deleteScheduleItem } from '../../services/api'

export default function Dashboard() {
    const navigate = useNavigate()
    const [stats, setStats] = useState(null)
    const [loading, setLoading] = useState(true)
    const [semester, setSemester] = useState(1)
    const [departmentId, setDepartmentId] = useState("")
    const [departments, setDepartments] = useState([])

    // modal state
    const [showConflictModal, setShowConflictModal] = useState(false)
    const [resolving, setResolving] = useState(false)

    // Load departments once
    useEffect(() => {
        const loadDepartments = async () => {
            try {
                // apiCall to list "college" doesn't have a direct helper like list() in Dashboard
                // we import list from api.js further up, let's just make sure we do that
                const api = await import('../../services/api')
                const depts = await api.list('college')
                setDepartments(depts || [])
            } catch (err) {
                console.error("Failed to load departments", err)
            }
        }
        loadDepartments()
    }, [])

    const fetchStats = async () => {
        setLoading(true)
        try {
            const data = await getAdminStats(semester, departmentId)
            if (data) {
                setStats(data)
            }
        } catch (err) {
            console.error("Failed to load admin stats", err)
        } finally {
            setLoading(false)
        }
    }

    useEffect(() => {
        fetchStats()
    }, [semester, departmentId])

    const handleResolveConflict = async (scheduleId) => {
        if (!confirm("Are you sure you want to delete this schedule item?")) return
        setResolving(true)
        try {
            await deleteScheduleItem(scheduleId)
            // Refresh stats
            await fetchStats()
        } catch (err) {
            alert("Failed to delete item: " + err.message)
        } finally {
            setResolving(false)
        }
    }

    const StatCard = ({ title, value, subtext, color, icon, onClick, actionLabel }) => (
        <div
            className={`bg-white/80 backdrop-blur-xl p-6 rounded-2xl shadow-sm border border-slate-200 flex items-start justify-between transition-all hover:shadow-lg ${onClick ? 'cursor-pointer hover:border-indigo-300' : ''}`}
            onClick={onClick}
        >
            <div>
                <p className="text-sm font-semibold text-slate-500 uppercase tracking-wide mb-1">{title}</p>
                <h3 className="text-3xl font-bold text-slate-800 mb-2">{value}</h3>
                <p className={`text-xs font-medium ${color}`}>{subtext}</p>
                {actionLabel && <div className="mt-2 text-xs text-indigo-600 font-bold uppercase">{actionLabel} &rarr;</div>}
            </div>
            <div className={`p-3 rounded-xl bg-opacity-10 ${color.replace('text-', 'bg-')}`}>
                <span className="text-2xl">{icon}</span>
            </div>
        </div>
    )

    const ProgressBar = ({ label, value, color }) => (
        <div className="mb-4">
            <div className="flex justify-between mb-1">
                <span className="text-sm font-medium text-slate-700">{label}</span>
                <span className="text-sm font-bold text-slate-700">{Math.round(value)}%</span>
            </div>
            <div className="w-full bg-slate-100 rounded-full h-2.5">
                <div
                    className={`h-2.5 rounded-full ${color}`}
                    style={{ width: `${Math.min(value, 100)}%` }}
                ></div>
            </div>
        </div>
    )

    if (loading && !stats) {
        return (
            <div className="flex flex-col items-center justify-center min-h-[500px]">
                <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-indigo-600 mb-4"></div>
                <p className="text-slate-500 font-medium">Loading dashboard statistics...</p>
            </div>
        )
    }

    if (!stats) return <div className="p-8 text-center text-red-500">Failed to load statistics.</div>

    return (
        <div className="space-y-8 animate-fade-in relative">
            {/* Header */}
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div>
                    <h1 className="text-3xl font-bold text-slate-800">
                        Dashboard
                    </h1>
                    <p className="text-slate-500 mt-1"> Overview for Semester {semester}</p>
                </div>

                <div className="flex flex-col sm:flex-row items-end sm:items-center gap-4">
                    <div className="flex items-center gap-3 bg-white p-2 rounded-xl shadow-sm border border-slate-200">
                        <span className="text-xs font-bold text-slate-500 uppercase px-2">Department:</span>
                        <select
                            value={departmentId}
                            onChange={(e) => setDepartmentId(e.target.value)}
                            className="bg-transparent border-none text-sm font-bold text-slate-700 outline-none cursor-pointer pr-8"
                            style={{ WebkitAppearance: 'none', MozAppearance: 'none', appearance: 'none', backgroundImage: 'url("data:image/svg+xml;charset=US-ASCII,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20width%3D%22292.4%22%20height%3D%22292.4%22%3E%3Cpath%20fill%3D%22%23475569%22%20d%3D%22M287%2069.4a17.6%2017.6%200%200%200-13-5.4H18.4c-5%200-9.3%201.8-12.9%205.4A17.6%2017.6%200%200%200%200%2082.2c0%205%201.8%209.3%205.4%2012.9l128%20127.9c3.6%203.6%207.8%205.4%2012.8%205.4s9.2-1.8%2012.8-5.4L287%2095c3.5-3.5%205.4-7.8%205.4-12.8%200-5-1.9-9.2-5.5-12.8z%22%2F%3E%3C%2Fsvg%3E")', backgroundRepeat: 'no-repeat', backgroundPosition: 'right 0.5rem center', backgroundSize: '0.65em auto' }}
                        >
                            <option value="">All Departments</option>
                            {departments.map((dept) => (
                                <option key={dept.id} value={dept.id}>{dept.code}</option>
                            ))}
                        </select>
                    </div>

                    <div className="flex items-center gap-3 bg-white p-2 rounded-xl shadow-sm border border-slate-200">
                        <span className="text-xs font-bold text-slate-500 uppercase px-2">Semester Filter:</span>
                        <button
                            onClick={() => setSemester(1)}
                            className={`px-4 py-2 rounded-lg text-sm font-bold transition-all ${semester === 1 ? 'bg-indigo-600 text-white shadow-md' : 'text-slate-600 hover:bg-slate-100'}`}
                        >
                            1st Sem
                        </button>
                        <button
                            onClick={() => setSemester(2)}
                            className={`px-4 py-2 rounded-lg text-sm font-bold transition-all ${semester === 2 ? 'bg-indigo-600 text-white shadow-md' : 'text-slate-600 hover:bg-slate-100'}`}
                        >
                            2nd Sem
                        </button>
                    </div>
                </div>
            </div>

            {/* Top Stats Row */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <StatCard
                    title="Room Utilization"
                    value={`${stats.rooms.utilization_pct}%`}
                    subtext={`${stats.rooms.active} of ${stats.rooms.total} rooms active`}
                    color="text-emerald-600"
                    icon="🏢"
                />
                <StatCard
                    title="Active Instructors"
                    value={`${stats.instructors.active}`}
                    subtext={`${stats.instructors.total} total instructors registered`}
                    color="text-blue-600"
                    icon="👨‍🏫"
                />
                <StatCard
                    title="Schedule Conflicts"
                    value={stats.conflicts.count}
                    subtext={stats.conflicts.count > 0 ? "Click to resolve conflicts" : "All clean!"}
                    color={stats.conflicts.count > 0 ? "text-rose-600" : "text-slate-500"}
                    icon="⚠️"
                    onClick={stats.conflicts.count > 0 ? () => setShowConflictModal(true) : undefined}
                    actionLabel={stats.conflicts.count > 0 ? "View & Resolve" : null}
                />
            </div>

            {/* Main Content Grid */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">

                {/* Left Column: Details */}
                <div className="space-y-8">
                    {/* Activity Panel */}
                    <div className="bg-white/80 backdrop-blur-xl p-6 rounded-2xl shadow-sm border border-slate-200">
                        <h2 className="text-lg font-bold text-slate-800 mb-6 flex items-center gap-2">
                            <span className="w-1.5 h-6 bg-indigo-500 rounded-full"></span>
                            Utilization Metrics
                        </h2>

                        <ProgressBar
                            label="Room Capacity Used"
                            value={stats.rooms.utilization_pct}
                            color={stats.rooms.utilization_pct > 80 ? "bg-amber-500" : "bg-emerald-500"}
                        />
                        <ProgressBar
                            label="Instructor Deployment"
                            value={stats.instructors.utilization_pct}
                            color="bg-blue-500"
                        />
                        <ProgressBar
                            label="Scheduling Coverage"
                            value={stats.subjects.total > 0 ? (stats.subjects.scheduled / stats.subjects.total) * 100 : 0}
                            color={stats.subjects.scheduled === stats.subjects.total ? "bg-emerald-500" : "bg-indigo-500"}
                        />
                    </div>

                    {/* Recommendations */}
                    <div className="bg-gradient-to-br from-slate-800 to-slate-900 text-white p-6 rounded-2xl shadow-lg relative overflow-hidden">
                        <div className="absolute top-0 right-0 p-4 opacity-10 text-9xl">💡</div>
                        <h2 className="text-lg font-bold mb-4 relative z-10 flex items-center gap-2">
                            AI Recommendations
                        </h2>
                        <ul className="space-y-3 relative z-10">
                            {stats.recommendations.map((rec, idx) => (
                                <li key={idx} className="flex items-start gap-3 text-sm text-slate-200 bg-white/10 p-3 rounded-lg">
                                    <span className="text-amber-400 mt-0.5">★</span>
                                    {rec}
                                </li>
                            ))}
                        </ul>
                    </div>
                </div>

                {/* Right Column: Unscheduled / Status */}
                <div className="bg-white/80 backdrop-blur-xl p-6 rounded-2xl shadow-sm border border-slate-200">
                    <div className="flex items-center justify-between mb-6">
                        <h2 className="text-lg font-bold text-slate-800 flex items-center gap-2">
                            Unscheduled Subjects
                        </h2>
                        <span className={`px-3 py-1 rounded-full text-xs font-bold ${stats.subjects.unscheduled > 0 ? 'bg-amber-100 text-amber-700' : 'bg-emerald-100 text-emerald-700'}`}>
                            {stats.subjects.unscheduled} Pending
                        </span>
                    </div>

                    {stats.subjects.sample_unscheduled.length > 0 ? (
                        <div className="space-y-4">
                            {stats.subjects.sample_unscheduled.map((subj, idx) => (
                                <div key={idx} className="flex items-center justify-between p-4 bg-slate-50 border border-slate-100 rounded-xl hover:bg-white hover:shadow-sm transition-all group">
                                    <div>
                                        <div className="font-bold text-slate-700 group-hover:text-indigo-600 transition-colors">{subj.code}</div>
                                        <div className="text-xs text-slate-500">{subj.description}</div>
                                    </div>
                                    <button
                                        onClick={() => navigate('/a/generate')}
                                        className="text-xs font-bold text-indigo-600 bg-indigo-50 px-3 py-1.5 rounded-lg opacity-0 group-hover:opacity-100 transition-opacity hover:bg-indigo-100"
                                    >
                                        Schedule
                                    </button>
                                </div>
                            ))}
                            {stats.subjects.unscheduled > 5 && (
                                <div className="text-center py-2 text-xs font-medium text-slate-400">
                                    + {stats.subjects.unscheduled - 5} more subjects hidden...
                                </div>
                            )}
                            <button
                                onClick={() => navigate('/a/generate')}
                                className="w-full py-3 mt-4 bg-indigo-600 hover:bg-indigo-700 text-white font-bold rounded-xl transition-all shadow-md shadow-indigo-200 flex items-center justify-center gap-2"
                            >
                                <span>⚡</span> Open Schedule Generator
                            </button>
                        </div>
                    ) : (
                        <div className="flex flex-col items-center justify-center py-12 text-slate-400">
                            <span className="text-4xl mb-3">🎉</span>
                            <p className="font-medium">All subjects are scheduled!</p>
                        </div>
                    )}
                </div>
            </div>

            {/* Conflict Resolution Modal */}
            {showConflictModal && (
                <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-sm animate-fade-in">
                    <div className="bg-white w-full max-w-4xl rounded-2xl shadow-2xl max-h-[90vh] flex flex-col overflow-hidden">
                        <div className="p-6 border-b border-slate-100 flex items-center justify-between bg-rose-50">
                            <div>
                                <h3 className="text-lg font-bold text-rose-800 flex items-center gap-2">
                                    ⚠️ Conflict Resolver
                                </h3>
                                <p className="text-sm text-rose-600">
                                    {stats.conflicts.count} conflicts detected involving {stats.conflicts.affected_items} items.
                                </p>
                            </div>
                            <button
                                onClick={() => setShowConflictModal(false)}
                                className="p-2 hover:bg-white/50 rounded-lg text-rose-800 transition-colors"
                            >
                                ✕
                            </button>
                        </div>

                        <div className="p-6 overflow-y-auto space-y-6 bg-slate-50">
                            {stats.conflicts.details && stats.conflicts.details.map((group, idx) => (
                                <div key={idx} className="bg-white rounded-xl shadow-sm border border-slate-200 p-5">
                                    <div className="flex items-center gap-3 mb-4 pb-3 border-b border-slate-100">
                                        <span className="px-2.5 py-1 bg-slate-100 rounded-lg text-xs font-bold text-slate-600">{group.time}</span>
                                        <span className="px-2.5 py-1 bg-slate-100 rounded-lg text-xs font-bold text-slate-600">{group.day}</span>
                                        <span className="flex-1 font-mono text-sm font-semibold text-slate-500 text-right">{group.room}</span>
                                    </div>

                                    <div className="space-y-3">
                                        {group.items.map(item => (
                                            <div key={item.id} className="flex items-center justify-between p-3 rounded-lg border border-red-100 bg-red-50/50 hover:bg-red-50 transition-colors">
                                                <div>
                                                    <div className="font-bold text-slate-800">{item.subject_code}</div>
                                                    <div className="text-xs text-slate-500">{item.description} • {item.instructor}</div>
                                                </div>
                                                <button
                                                    onClick={() => handleResolveConflict(item.id)}
                                                    disabled={resolving}
                                                    className="px-3 py-1.5 bg-white text-rose-600 border border-rose-200 font-bold text-xs rounded-lg hover:bg-rose-600 hover:text-white hover:border-rose-600 transition-all shadow-sm"
                                                >
                                                    Delete
                                                </button>
                                            </div>
                                        ))}
                                    </div>
                                    <div className="mt-3 text-center">
                                        <p className="text-[10px] text-slate-400 font-medium uppercase tracking-wide">Select one to delete (keeping others)</p>
                                    </div>
                                </div>
                            ))}
                            {(!stats.conflicts.details || stats.conflicts.details.length === 0) && (
                                <div className="text-center py-12 text-slate-400">
                                    <p>No conflict details available.</p>
                                </div>
                            )}
                        </div>

                        <div className="p-4 border-t border-slate-100 bg-white flex justify-end">
                            <button
                                onClick={() => setShowConflictModal(false)}
                                className="px-5 py-2.5 bg-slate-100 hover:bg-slate-200 text-slate-700 font-bold rounded-xl transition-colors"
                            >
                                Close
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    )
}
