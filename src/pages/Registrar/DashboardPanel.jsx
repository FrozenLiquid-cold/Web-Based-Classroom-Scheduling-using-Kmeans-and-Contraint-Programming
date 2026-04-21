import { useState, useEffect } from 'react'
import { getAdminStats, deleteScheduleItem, getStaffingAnalysis } from '../../services/api'
import ConfirmDialog from '../../components/ConfirmDialog'
import SchoolYearSelector, { computeDefaultSY } from '../../components/SchoolYearSelector'

export default function DashboardPanel() {
    const [stats, setStats] = useState(null)
    const [loading, setLoading] = useState(true)
    const [semester, setSemester] = useState(1)
    const [departmentId, setDepartmentId] = useState("")
    const [schoolYear, setSchoolYear] = useState(computeDefaultSY)
    const [departments, setDepartments] = useState([])

    // modal state
    const [showConflictModal, setShowConflictModal] = useState(false)
    const [showRoomModal, setShowRoomModal] = useState(false)
    const [showInstructorModal, setShowInstructorModal] = useState(false)
    const [resolving, setResolving] = useState(false)
    const [confirmDialog, setConfirmDialog] = useState({ open: false })

    // Staffing modal state
    const [showStaffingModal, setShowStaffingModal] = useState(false)
    const [staffingData, setStaffingData] = useState(null)
    const [staffingBlocks, setStaffingBlocks] = useState(3)
    const [staffingLoading, setStaffingLoading] = useState(false)
    const [staffingTab, setStaffingTab] = useState("critical")
    const [staffingSearch, setStaffingSearch] = useState("")
    const [expandedSubj, setExpandedSubj] = useState(null)

    // Detail modal filters
    const [instrFilter, setInstrFilter] = useState("issues")
    const [roomSearch, setRoomSearch] = useState("")
    const [instrSearch, setInstrSearch] = useState("")

    // Load departments once
    useEffect(() => {
        const loadDepartments = async () => {
            try {
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
            const data = await getAdminStats(semester, departmentId, schoolYear)
            if (data) setStats(data)
        } catch (err) {
            console.error("Failed to load admin stats", err)
        } finally {
            setLoading(false)
        }
    }

    useEffect(() => { fetchStats() }, [semester, departmentId, schoolYear])

    // Fetch staffing analysis: on mount for stat card, and when modal is open / blocks change
    const fetchStaffing = async (blocksOverride) => {
        setStaffingLoading(true)
        try {
            const data = await getStaffingAnalysis(semester, blocksOverride || staffingBlocks, "", schoolYear)
            if (data) setStaffingData(data)
        } catch (err) {
            console.error("Failed to load staffing analysis", err)
        } finally {
            setStaffingLoading(false)
        }
    }
    // Initial load for stat card
    useEffect(() => { fetchStaffing() }, [semester, schoolYear])
    // Re-fetch when blocks change in modal
    useEffect(() => { if (showStaffingModal) fetchStaffing() }, [staffingBlocks])

    const handleResolveConflict = (scheduleId) => {
        setConfirmDialog({
            open: true,
            title: 'Delete Schedule Item',
            message: 'Are you sure you want to delete this schedule item? This will resolve the conflict.',
            confirmText: 'Delete',
            variant: 'danger',
            onConfirm: async () => {
                setConfirmDialog({ open: false })
                setResolving(true)
                try {
                    await deleteScheduleItem(scheduleId)
                    await fetchStats()
                } catch (err) {
                    alert("Failed to delete item: " + err.message)
                } finally {
                    setResolving(false)
                }
            },
        })
    }

    // --- Reusable Components ---

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
                <div className={`h-2.5 rounded-full ${color}`} style={{ width: `${Math.min(value, 100)}%` }}></div>
            </div>
        </div>
    )

    // --- Status helpers ---
    const statusConfig = {
        overloaded: { bg: 'bg-rose-100', text: 'text-rose-700', label: 'OVERLOADED', dot: 'bg-rose-500' },
        near_capacity: { bg: 'bg-amber-100', text: 'text-amber-700', label: 'NEAR CAP', dot: 'bg-amber-500' },
        active: { bg: 'bg-emerald-100', text: 'text-emerald-700', label: 'ACTIVE', dot: 'bg-emerald-500' },
        available: { bg: 'bg-slate-100', text: 'text-slate-500', label: 'AVAILABLE', dot: 'bg-slate-400' },
    }

    const getLoadBarColor = (pct) => {
        if (pct > 100) return 'bg-rose-500'
        if (pct >= 80) return 'bg-amber-500'
        if (pct > 0) return 'bg-emerald-500'
        return 'bg-slate-300'
    }

    // --- Loading / Error states ---
    if (loading && !stats) {
        return (
            <div className="flex flex-col items-center justify-center min-h-[500px]">
                <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-indigo-600 mb-4"></div>
                <p className="text-slate-500 font-medium">Loading dashboard statistics...</p>
            </div>
        )
    }
    if (!stats) return <div className="p-8 text-center text-red-500">Failed to load statistics.</div>

    // --- Filtered data for modals ---
    const filteredInstructors = (stats.instructors.details || []).filter(i => {
        const matchStatus = instrFilter === "all" || i.status === instrFilter
        const matchSearch = !instrSearch ||
            i.name.toLowerCase().includes(instrSearch.toLowerCase()) ||
            (i.college || '').toLowerCase().includes(instrSearch.toLowerCase()) ||
            (i.home_program || '').toLowerCase().includes(instrSearch.toLowerCase())
        return matchStatus && matchSearch
    })

    const filteredRooms = (stats.rooms.details || []).filter(r => {
        if (!roomSearch) return true
        const q = roomSearch.toLowerCase()
        return r.name.toLowerCase().includes(q) || (r.building || '').toLowerCase().includes(q) || r.type.toLowerCase().includes(q)
    })

    const closeRoomModal = () => { setShowRoomModal(false); setRoomSearch('') }
    const closeInstrModal = () => { setShowInstructorModal(false); setInstrFilter("all"); setInstrSearch('') }

    return (
        <div className="space-y-8 relative">
            {/* Filters Row */}
            <div className="flex flex-wrap items-center gap-4">
                <SchoolYearSelector onChange={setSchoolYear} />
                <div className="flex items-center gap-3 bg-white p-2 rounded-xl shadow-sm border border-slate-200">
                    <span className="text-xs font-bold text-slate-500 uppercase px-2">Department:</span>
                    <select
                        value={departmentId}
                        onChange={(e) => setDepartmentId(e.target.value)}
                        className="bg-transparent border-none text-sm font-bold text-slate-700 outline-none cursor-pointer pr-8"
                    >
                        <option value="">All Departments</option>
                        {departments.map((dept) => (
                            <option key={dept.id} value={dept.id}>{dept.code}</option>
                        ))}
                    </select>
                </div>
                <div className="flex items-center gap-3 bg-white p-2 rounded-xl shadow-sm border border-slate-200">
                    <span className="text-xs font-bold text-slate-500 uppercase px-2">Semester:</span>
                    <button onClick={() => setSemester(1)} className={`px-4 py-2 rounded-lg text-sm font-bold transition-all ${semester === 1 ? 'bg-indigo-600 text-white shadow-md' : 'text-slate-600 hover:bg-slate-100'}`}>1st Sem</button>
                    <button onClick={() => setSemester(2)} className={`px-4 py-2 rounded-lg text-sm font-bold transition-all ${semester === 2 ? 'bg-indigo-600 text-white shadow-md' : 'text-slate-600 hover:bg-slate-100'}`}>2nd Sem</button>
                </div>
            </div>

            {/* Top Stats Row */}
            <div className="grid grid-cols-1 md:grid-cols-5 gap-6">
                <StatCard
                    title="Room Utilization"
                    value={`${stats.rooms.utilization_pct}%`}
                    subtext={`${stats.rooms.active} of ${stats.rooms.total} rooms active`}
                    color="text-emerald-600"
                    icon="🏢"
                    onClick={() => setShowRoomModal(true)}
                    actionLabel="View Rooms"
                />
                <StatCard
                    title="Active Instructors"
                    value={`${stats.instructors.active} / ${stats.instructors.total}`}
                    subtext="Instructors assigned to classes"
                    color="text-blue-600"
                    icon="👨‍🏫"
                    onClick={() => { setInstrFilter("all"); setShowInstructorModal(true) }}
                    actionLabel="View Load"
                />
                <StatCard
                    title="Instructor Load"
                    value={stats.instructors.overloaded || 0}
                    subtext={`${stats.instructors.overloaded || 0} overloaded · ${stats.instructors.near_capacity || 0} near cap`}
                    color={stats.instructors.overloaded > 0 ? "text-rose-600" : "text-amber-600"}
                    icon="⚖️"
                    onClick={() => { setInstrFilter(stats.instructors.overloaded > 0 ? "overloaded" : "all"); setShowInstructorModal(true) }}
                    actionLabel={stats.instructors.overloaded > 0 ? "Review Now" : "View All"}
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
                <StatCard
                    title="Staffing Gaps"
                    value={staffingData ? `${staffingData.summary.critical + staffingData.summary.warning}` : '—'}
                    subtext={staffingData ? `${staffingData.summary.critical} critical · ${staffingData.summary.warning} warning` : 'Click to analyze'}
                    color={staffingData && staffingData.summary.critical > 0 ? "text-rose-600" : staffingData && staffingData.summary.warning > 0 ? "text-amber-600" : "text-emerald-600"}
                    icon="📊"
                    onClick={() => setShowStaffingModal(true)}
                    actionLabel="Analyze Staffing"
                />
            </div>

            {/* Main Content Grid */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                {/* Left Column */}
                <div className="space-y-8">
                    {/* Utilization Metrics */}
                    <div className="bg-white/80 backdrop-blur-xl p-6 rounded-2xl shadow-sm border border-slate-200">
                        <h2 className="text-lg font-bold text-slate-800 mb-6 flex items-center gap-2">
                            <span className="w-1.5 h-6 bg-indigo-500 rounded-full"></span>
                            Utilization Metrics
                        </h2>
                        <ProgressBar label="Room Capacity Used" value={stats.rooms.utilization_pct} color={stats.rooms.utilization_pct > 80 ? "bg-amber-500" : "bg-emerald-500"} />
                        <ProgressBar label="Instructor Deployment" value={stats.instructors.utilization_pct} color="bg-blue-500" />
                        <ProgressBar label="Scheduling Coverage" value={stats.subjects.total > 0 ? (stats.subjects.scheduled / stats.subjects.total) * 100 : 0} color={stats.subjects.scheduled === stats.subjects.total ? "bg-emerald-500" : "bg-indigo-500"} />
                    </div>

                    {/* Recommendations */}
                    <div className="bg-gradient-to-br from-slate-800 to-slate-900 text-white p-6 rounded-2xl shadow-lg relative overflow-hidden">
                        <div className="absolute top-0 right-0 p-4 opacity-10 text-9xl">💡</div>
                        <h2 className="text-lg font-bold mb-4 relative z-10 flex items-center gap-2">AI Recommendations</h2>
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

                {/* Right Column: Unscheduled */}
                <div className="bg-white/80 backdrop-blur-xl p-6 rounded-2xl shadow-sm border border-slate-200">
                    <div className="flex items-center justify-between mb-6">
                        <h2 className="text-lg font-bold text-slate-800 flex items-center gap-2">Unscheduled Subjects</h2>
                        <span className={`px-3 py-1 rounded-full text-xs font-bold ${stats.subjects.unscheduled > 0 ? 'bg-amber-100 text-amber-700' : 'bg-emerald-100 text-emerald-700'}`}>
                            {stats.subjects.unscheduled} Pending
                        </span>
                    </div>
                    {stats.subjects.sample_unscheduled.length > 0 ? (
                        <div className="space-y-4">
                            {stats.subjects.sample_unscheduled.map((subj, idx) => (
                                <div key={idx} className="flex items-center justify-between p-4 bg-slate-50 border border-slate-100 rounded-xl hover:bg-white hover:shadow-sm transition-all group">
                                    <div className="flex-1 min-w-0">
                                        <div className="font-bold text-slate-700 group-hover:text-indigo-600 transition-colors">{subj.code}</div>
                                        <div className="text-xs text-slate-500 truncate">{subj.description}</div>
                                    </div>
                                    <div className="flex items-center gap-1.5 ml-3 shrink-0">
                                        <span className="px-2 py-0.5 bg-blue-50 text-blue-700 border border-blue-200 rounded text-[10px] font-bold">{subj.course}</span>
                                        <span className="px-2 py-0.5 bg-violet-50 text-violet-700 border border-violet-200 rounded text-[10px] font-bold">Y{subj.year_level}</span>
                                        <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${subj.type === 'LAB' ? 'bg-purple-50 text-purple-700 border border-purple-200' : 'bg-slate-100 text-slate-600 border border-slate-200'}`}>{subj.type}</span>
                                    </div>
                                </div>
                            ))}
                            {stats.subjects.unscheduled > 5 && (
                                <div className="text-center py-2 text-xs font-medium text-slate-400">+ {stats.subjects.unscheduled - 5} more subjects hidden...</div>
                            )}
                        </div>
                    ) : (
                        <div className="flex flex-col items-center justify-center py-12 text-slate-400">
                            <span className="text-4xl mb-3">🎉</span>
                            <p className="font-medium">All subjects are scheduled!</p>
                        </div>
                    )}
                </div>
            </div>

            {/* =================== ROOM DETAIL MODAL =================== */}
            {showRoomModal && (
                <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-sm animate-fade-in">
                    <div className="bg-white w-full max-w-5xl rounded-2xl shadow-2xl max-h-[90vh] flex flex-col overflow-hidden">
                        <div className="p-6 border-b border-slate-100 flex items-center justify-between bg-emerald-50">
                            <div>
                                <h3 className="text-lg font-bold text-emerald-800 flex items-center gap-2">🏢 Room Utilization Details</h3>
                                <p className="text-sm text-emerald-600">{stats.rooms.active} active of {stats.rooms.total} total rooms · {stats.rooms.utilization_pct}% avg utilization</p>
                            </div>
                            <button onClick={closeRoomModal} className="p-2 hover:bg-white/50 rounded-lg text-emerald-800 transition-colors text-lg">✕</button>
                        </div>
                        <div className="px-6 py-3 bg-white border-b border-slate-100">
                            <input type="text" value={roomSearch} onChange={(e) => setRoomSearch(e.target.value)} placeholder="Search rooms by name, building, or type..." className="w-full px-4 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm outline-none focus:ring-2 focus:ring-emerald-500 focus:border-emerald-300 transition-all" />
                        </div>
                        <div className="p-6 overflow-y-auto bg-slate-50">
                            <div className="grid grid-cols-1 gap-3">
                                <div className="grid grid-cols-12 gap-3 px-4 py-2 text-xs font-bold text-slate-500 uppercase tracking-wide">
                                    <div className="col-span-3">Room</div>
                                    <div className="col-span-2">Building</div>
                                    <div className="col-span-1 text-center">Type</div>
                                    <div className="col-span-1 text-center">Slots</div>
                                    <div className="col-span-5">Utilization</div>
                                </div>
                                {filteredRooms.map((room) => (
                                    <div key={room.id} className="grid grid-cols-12 gap-3 items-center bg-white p-4 rounded-xl border border-slate-100 hover:shadow-sm transition-all">
                                        <div className="col-span-3">
                                            <div className="font-bold text-slate-800">{room.name}</div>
                                            <div className="text-xs text-slate-400">Cap: {room.capacity || '—'}</div>
                                        </div>
                                        <div className="col-span-2 text-sm text-slate-600">{room.building || '—'}</div>
                                        <div className="col-span-1 text-center">
                                            <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${room.type === 'LAB' ? 'bg-purple-100 text-purple-700' : 'bg-blue-100 text-blue-700'}`}>{room.type}</span>
                                        </div>
                                        <div className="col-span-1 text-center text-sm font-bold text-slate-700">
                                            {room.weekday_slots || room.scheduled_slots}<span className="text-[10px] text-slate-400 font-normal">/{room.max_slots || '?'}</span>
                                            {room.weekend_slots > 0 && <span className="block text-[9px] text-orange-500 font-medium">+{room.weekend_slots} wknd</span>}
                                        </div>
                                        <div className="col-span-5 flex items-center gap-3">
                                            <div className="flex-1 bg-slate-100 rounded-full h-2.5">
                                                <div className={`h-2.5 rounded-full transition-all ${room.utilization_pct >= 90 ? 'bg-red-500' : room.utilization_pct >= 70 ? 'bg-amber-500' : room.utilization_pct > 0 ? 'bg-emerald-500' : 'bg-slate-200'}`} style={{ width: `${Math.min(room.utilization_pct, 100)}%` }}></div>
                                            </div>
                                            <span className={`text-sm font-bold w-12 text-right ${room.utilization_pct >= 90 ? 'text-red-600' : room.utilization_pct >= 70 ? 'text-amber-600' : 'text-slate-600'}`}>{room.utilization_pct}%</span>
                                        </div>
                                    </div>
                                ))}
                                {filteredRooms.length === 0 && (
                                    <div className="text-center py-12 text-slate-400"><p>{roomSearch ? 'No rooms match your search.' : 'No room data available.'}</p></div>
                                )}
                            </div>
                        </div>
                        <div className="p-4 border-t border-slate-100 bg-white flex justify-end">
                            <button onClick={closeRoomModal} className="px-5 py-2.5 bg-slate-100 hover:bg-slate-200 text-slate-700 font-bold rounded-xl transition-colors">Close</button>
                        </div>
                    </div>
                </div>
            )}

            {/* =================== INSTRUCTOR DETAIL MODAL =================== */}
            {showInstructorModal && (
                <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-sm animate-fade-in">
                    <div className="bg-white w-full max-w-5xl rounded-2xl shadow-2xl max-h-[90vh] flex flex-col overflow-hidden">
                        <div className="p-6 border-b border-slate-100 flex items-center justify-between bg-blue-50">
                            <div>
                                <h3 className="text-lg font-bold text-blue-800 flex items-center gap-2">👨‍🏫 Instructor Load & Availability</h3>
                                <p className="text-sm text-blue-600">{stats.instructors.active} active · {stats.instructors.overloaded || 0} overloaded · {stats.instructors.near_capacity || 0} near capacity</p>
                            </div>
                            <button onClick={closeInstrModal} className="p-2 hover:bg-white/50 rounded-lg text-blue-800 transition-colors text-lg">✕</button>
                        </div>
                        {/* Filter tabs */}
                        <div className="px-6 py-3 bg-white border-b border-slate-100 flex gap-2 flex-wrap">
                            {[
                                { key: "all", label: "All", count: stats.instructors.details?.length || 0 },
                                { key: "overloaded", label: "Overloaded", count: stats.instructors.overloaded || 0 },
                                { key: "near_capacity", label: "Near Capacity", count: stats.instructors.near_capacity || 0 },
                                { key: "active", label: "Active", count: (stats.instructors.details || []).filter(i => i.status === "active").length },
                                { key: "available", label: "Available", count: (stats.instructors.details || []).filter(i => i.status === "available").length },
                            ].map(tab => (
                                <button key={tab.key} onClick={() => setInstrFilter(tab.key)} className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${instrFilter === tab.key ? 'bg-indigo-600 text-white shadow-sm' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'}`}>
                                    {tab.label} ({tab.count})
                                </button>
                            ))}
                        </div>
                        {/* Search */}
                        <div className="px-6 py-3 bg-white border-b border-slate-100">
                            <input type="text" value={instrSearch} onChange={(e) => setInstrSearch(e.target.value)} placeholder="Search by name or department..." className="w-full px-4 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-300 transition-all" />
                        </div>
                        <div className="p-6 overflow-y-auto bg-slate-50">
                            <div className="grid grid-cols-1 gap-3">
                                <div className="grid grid-cols-12 gap-3 px-4 py-2 text-xs font-bold text-slate-500 uppercase tracking-wide">
                                    <div className="col-span-3">Instructor</div>
                                    <div className="col-span-1 text-center">Dept</div>
                                    <div className="col-span-1 text-center">Type</div>
                                    <div className="col-span-1 text-center">Subj</div>
                                    <div className="col-span-1 text-center">Slots</div>
                                    <div className="col-span-3">Load</div>
                                    <div className="col-span-2 text-center">Status</div>
                                </div>
                                {filteredInstructors.map((instr) => {
                                    const sc = statusConfig[instr.status] || statusConfig.available
                                    return (
                                        <div key={instr.id} className={`grid grid-cols-12 gap-3 items-center p-4 rounded-xl border transition-all hover:shadow-sm ${instr.status === 'overloaded' ? 'bg-rose-50 border-rose-200' : instr.status === 'near_capacity' ? 'bg-amber-50 border-amber-200' : 'bg-white border-slate-100'}`}>
                                            <div className="col-span-3"><div className="font-bold text-slate-800">{instr.name}</div>{instr.home_program && <div className="text-[10px] text-blue-600 font-medium mt-0.5">{instr.home_program}</div>}</div>
                                            <div className="col-span-1 text-center text-xs font-medium text-slate-500">{instr.college || '—'}</div>
                                            <div className="col-span-1 text-center"><span className="text-[10px] font-bold text-slate-500 bg-slate-100 px-1.5 py-0.5 rounded">{instr.employment_type}</span></div>
                                            <div className="col-span-1 text-center text-sm font-bold text-slate-700">{instr.subject_count}</div>
                                            <div className="col-span-1 text-center text-sm font-bold text-slate-700">{instr.scheduled_slots}</div>
                                            <div className="col-span-3 flex items-center gap-2">
                                                <div className="flex-1 bg-slate-100 rounded-full h-2.5 overflow-hidden">
                                                    <div className={`h-2.5 rounded-full transition-all ${getLoadBarColor(instr.load_pct)}`} style={{ width: `${Math.min(instr.load_pct, 100)}%` }}></div>
                                                </div>
                                                <span className="text-xs font-bold text-slate-600 w-20 text-right whitespace-nowrap">{instr.loaded_units} / {instr.max_units} units</span>
                                            </div>
                                            <div className="col-span-2 text-center">
                                                <span className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-[11px] font-bold ${sc.bg} ${sc.text}`}>
                                                    <span className={`w-1.5 h-1.5 rounded-full ${sc.dot}`}></span>
                                                    {sc.label}
                                                </span>
                                            </div>
                                        </div>
                                    )
                                })}
                                {filteredInstructors.length === 0 && (
                                    <div className="text-center py-12 text-slate-400"><p>{instrSearch ? 'No instructors match your search.' : 'No instructors match the selected filter.'}</p></div>
                                )}
                            </div>
                        </div>
                        <div className="p-4 border-t border-slate-100 bg-white flex justify-end">
                            <button onClick={closeInstrModal} className="px-5 py-2.5 bg-slate-100 hover:bg-slate-200 text-slate-700 font-bold rounded-xl transition-colors">Close</button>
                        </div>
                    </div>
                </div>
            )}

            {/* =================== CONFLICT MODAL =================== */}
            {showConflictModal && (
                <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-sm animate-fade-in">
                    <div className="bg-white w-full max-w-4xl rounded-2xl shadow-2xl max-h-[90vh] flex flex-col overflow-hidden">
                        <div className="p-6 border-b border-slate-100 flex items-center justify-between bg-rose-50">
                            <div>
                                <h3 className="text-lg font-bold text-rose-800 flex items-center gap-2">⚠️ Conflict Resolver</h3>
                                <p className="text-sm text-rose-600">{stats.conflicts.count} conflicts detected involving {stats.conflicts.affected_items} items.</p>
                            </div>
                            <button onClick={() => setShowConflictModal(false)} className="p-2 hover:bg-white/50 rounded-lg text-rose-800 transition-colors">✕</button>
                        </div>
                        <div className="p-6 overflow-y-auto space-y-6 bg-slate-50">
                            {stats.conflicts.details && stats.conflicts.details.map((group, idx) => (
                                <div key={idx} className="bg-white rounded-xl shadow-sm border border-slate-200 p-5">
                                    <div className="flex items-center gap-3 mb-4 pb-3 border-b border-slate-100">
                                        <span className="px-2.5 py-1 bg-slate-100 rounded-lg text-xs font-bold text-slate-600">{group.time}</span>
                                        <span className="px-2.5 py-1 bg-slate-100 rounded-lg text-xs font-bold text-slate-600">{group.day}</span>
                                        <span className="flex-1 font-mono text-sm font-semibold text-slate-500 text-right">{group.room}</span>
                                    </div>
                                    {group.is_shared_room && (
                                        <div className="mb-3 flex items-start gap-2 p-3 bg-amber-50 border border-amber-200 rounded-lg">
                                            <span className="text-amber-500 text-sm mt-0.5">ℹ️</span>
                                            <p className="text-xs text-amber-700">
                                                <strong>{group.room}</strong> is a shared venue (GYM/FIELD). PE, NSTP, and PATHFIT can share this room — but a non-PE/NSTP subject cannot use the same slot.
                                            </p>
                                        </div>
                                    )}
                                    <div className="space-y-3">
                                        {group.items.map(item => (
                                            <div key={item.id} className={`flex items-center justify-between p-3 rounded-lg border transition-colors ${
                                                group.is_shared_room && item.is_shared_subject
                                                    ? 'border-emerald-200 bg-emerald-50/50 hover:bg-emerald-50'
                                                    : 'border-red-100 bg-red-50/50 hover:bg-red-50'
                                            }`}>
                                                <div className="flex items-center gap-3">
                                                    <div>
                                                        <div className="font-bold text-slate-800 flex items-center gap-2">
                                                            {item.subject_code}
                                                            {item.course && <span className="px-1.5 py-0.5 bg-blue-50 text-blue-600 text-[9px] font-bold rounded border border-blue-200">{item.course}</span>}
                                                            {group.is_shared_room && item.is_shared_subject && (
                                                                <span className="px-1.5 py-0.5 bg-emerald-100 text-emerald-700 text-[9px] font-bold rounded">SHARED OK</span>
                                                            )}
                                                            {group.is_shared_room && !item.is_shared_subject && (
                                                                <span className="px-1.5 py-0.5 bg-rose-100 text-rose-700 text-[9px] font-bold rounded">⚠ WRONG VENUE</span>
                                                            )}
                                                        </div>
                                                        <div className="text-xs text-slate-500">{item.description} • {item.instructor} {item.time && <span className="text-slate-400">({item.time})</span>}</div>
                                                    </div>
                                                </div>
                                                <button onClick={() => handleResolveConflict(item.id)} disabled={resolving} className="px-3 py-1.5 bg-white text-rose-600 border border-rose-200 font-bold text-xs rounded-lg hover:bg-rose-600 hover:text-white hover:border-rose-600 transition-all shadow-sm">Delete</button>
                                            </div>
                                        ))}
                                    </div>
                                    <div className="mt-3 text-center"><p className="text-[10px] text-slate-400 font-medium uppercase tracking-wide">Select one to delete (keeping others)</p></div>
                                </div>
                            ))}
                            {(!stats.conflicts.details || stats.conflicts.details.length === 0) && (
                                <div className="text-center py-12 text-slate-400"><p>No conflict details available.</p></div>
                            )}
                        </div>
                        <div className="p-4 border-t border-slate-100 bg-white flex justify-end">
                            <button onClick={() => setShowConflictModal(false)} className="px-5 py-2.5 bg-slate-100 hover:bg-slate-200 text-slate-700 font-bold rounded-xl transition-colors">Close</button>
                        </div>
                    </div>
                </div>
            )}

            {/* =================== STAFFING ANALYSIS MODAL =================== */}
            {showStaffingModal && (
                <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-sm animate-fade-in">
                    <div className="bg-white w-full max-w-6xl rounded-2xl shadow-2xl max-h-[90vh] flex flex-col overflow-hidden">
                        {/* Header */}
                        <div className="p-6 border-b border-slate-100 flex items-center justify-between bg-gradient-to-r from-violet-50 to-indigo-50">
                            <div>
                                <h3 className="text-lg font-bold text-indigo-800 flex items-center gap-2">📊 Staffing Analysis</h3>
                                <p className="text-sm text-indigo-600">
                                    {staffingData ? `${staffingData.summary.total_subjects} subjects · SY ${staffingData.school_year} · Semester ${semester}` : 'Loading...'}
                                </p>
                            </div>
                            <button onClick={() => { setShowStaffingModal(false); setStaffingSearch(''); setStaffingTab('critical'); setExpandedSubj(null) }} className="p-2 hover:bg-white/50 rounded-lg text-indigo-800 transition-colors text-lg">✕</button>
                        </div>

                        {/* Block Selector */}
                        <div className="px-6 py-3 bg-white border-b border-slate-100 flex flex-wrap items-center gap-4">
                            <div className="flex items-center gap-2">
                                <span className="text-xs font-bold text-slate-500 uppercase">Blocks:</span>
                                {[1,2,3,4].map(b => (
                                    <button key={b} onClick={() => setStaffingBlocks(b)} className={`w-9 h-9 rounded-lg text-sm font-bold transition-all ${staffingBlocks === b ? 'bg-indigo-600 text-white shadow-md' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'}`}>{b}</button>
                                ))}
                            </div>
                            <div className="flex-1" />
                            <input type="text" value={staffingSearch} onChange={(e) => setStaffingSearch(e.target.value)} placeholder="Search subject code..." className="px-4 py-2 bg-slate-50 border border-slate-200 rounded-xl text-sm outline-none focus:ring-2 focus:ring-indigo-500 w-64" />
                        </div>

                        {/* Tabs */}
                        {staffingData && (
                            <div className="px-6 py-2 bg-white border-b border-slate-100 flex gap-2 flex-wrap">
                                {[
                                    { key: "critical", label: "🔴 Critical", count: staffingData.summary.critical },
                                    { key: "warning", label: "⚠️ Warning", count: staffingData.summary.warning },
                                    { key: "all", label: "All", count: staffingData.summary.total_subjects },
                                    { key: "ok", label: "✅ OK", count: staffingData.summary.ok },
                                    { key: "instructors", label: "👤 Instructor Alerts", count: staffingData.instructor_warnings?.filter(w => w.issue !== 'balanced').length || 0 },
                                ].map(tab => (
                                    <button key={tab.key} onClick={() => setStaffingTab(tab.key)} className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${staffingTab === tab.key ? 'bg-indigo-600 text-white shadow-sm' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'}`}>
                                        {tab.label} ({tab.count})
                                    </button>
                                ))}
                            </div>
                        )}

                        {/* Content */}
                        <div className="p-6 overflow-y-auto bg-slate-50 flex-1">
                            {staffingLoading ? (
                                <div className="flex flex-col items-center justify-center py-16">
                                    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600 mb-3"></div>
                                    <p className="text-slate-500 text-sm">Analyzing staffing for {staffingBlocks} blocks...</p>
                                </div>
                            ) : !staffingData ? (
                                <div className="text-center py-16 text-slate-400">Failed to load data.</div>
                            ) : staffingTab === "instructors" ? (
                                /* Instructor Semester Balance Tab */
                                (() => {
                                    const allW = staffingData.instructor_warnings || []
                                    const issueFilter = staffingSearch.toLowerCase()
                                    const issueTypes = [
                                        { key: 'issues', label: '⚠ Issues Only', filter: w => w.issue !== 'balanced' },
                                        { key: 'lopsided', label: '🔀 Semester Lopsided', filter: w => ['semester_lopsided','no_subjects_this_sem','semester_heavy'].includes(w.issue) },
                                        { key: 'load', label: '📊 Load Issues', filter: w => ['overspecialized','underspecialized','overloaded'].includes(w.issue) },
                                        { key: 'showAll', label: 'All Instructors', filter: () => true },
                                    ]
                                    // Use instrFilter to select the sub-tab
                                    const activeFilter = issueTypes.find(t => t.key === instrFilter) || issueTypes[0]
                                    const filtered = allW.filter(w => {
                                        const matchFilter = activeFilter.filter(w)
                                        const matchSearch = !issueFilter || w.name.toLowerCase().includes(issueFilter)
                                        return matchFilter && matchSearch
                                    })
                                    // Deduplicate by instructor id (show each instructor once, with worst issue)
                                    const seen = new Set()
                                    const deduped = []
                                    for (const w of filtered) {
                                        const key = instrFilter === 'showAll' ? `${w.id}_${w.issue}` : `${w.id}`
                                        if (!seen.has(key)) { seen.add(key); deduped.push(w) }
                                    }
                                    const issueColors = {
                                        overloaded: { bg: 'bg-rose-100', text: 'text-rose-700', border: 'border-rose-200' },
                                        underspecialized: { bg: 'bg-amber-100', text: 'text-amber-700', border: 'border-amber-200' },
                                        overspecialized: { bg: 'bg-orange-100', text: 'text-orange-700', border: 'border-orange-200' },
                                        semester_lopsided: { bg: 'bg-violet-100', text: 'text-violet-700', border: 'border-violet-200' },
                                        no_subjects_this_sem: { bg: 'bg-slate-200', text: 'text-slate-700', border: 'border-slate-300' },
                                        semester_heavy: { bg: 'bg-blue-100', text: 'text-blue-700', border: 'border-blue-200' },
                                        balanced: { bg: 'bg-emerald-100', text: 'text-emerald-700', border: 'border-emerald-200' },
                                    }
                                    return (
                                        <div className="space-y-3">
                                            {/* Sub-tabs */}
                                            <div className="flex gap-2 flex-wrap mb-3">
                                                {issueTypes.map(t => (
                                                    <button key={t.key} onClick={() => setInstrFilter(t.key)} className={`px-3 py-1 rounded-lg text-xs font-bold transition-all ${instrFilter === t.key ? 'bg-indigo-600 text-white shadow-sm' : 'bg-white text-slate-600 hover:bg-slate-100 border border-slate-200'}`}>
                                                        {t.label} ({allW.filter(t.filter).length})
                                                    </button>
                                                ))}
                                            </div>
                                            {deduped.length === 0 ? (
                                                <div className="text-center py-12 text-slate-400"><span className="text-4xl block mb-3">✅</span>No issues in this category.</div>
                                            ) : deduped.map((w, idx) => {
                                                const colors = issueColors[w.issue] || issueColors.balanced
                                                const s1 = w.s1_count || 0
                                                const s2 = w.s2_count || 0
                                                const maxSem = Math.max(s1, s2, 1)
                                                return (
                                                    <div key={idx} className={`p-4 rounded-xl border ${w.issue === 'balanced' ? 'bg-white border-slate-100' : colors.bg + ' ' + colors.border}`}>
                                                        <div className="flex items-center gap-3 flex-wrap">
                                                            <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase ${colors.bg} ${colors.text}`}>{w.issue.replace(/_/g, ' ')}</span>
                                                            <span className="font-bold text-slate-800">{w.name}</span>
                                                            {w.designation && <span className="text-[10px] text-amber-600 font-semibold bg-amber-50 px-1.5 py-0.5 rounded">• {w.designation}</span>}
                                                            <span className="text-xs text-slate-500">{w.employment_type} · {w.unit_cap}u cap</span>
                                                            <span className="text-xs text-slate-400 ml-auto">{w.total_specialties} total specialties</span>
                                                        </div>
                                                        <p className="text-sm text-slate-600 mt-2">{w.detail}</p>
                                                        {/* Semester Balance Bar */}
                                                        <div className="mt-3 grid grid-cols-2 gap-4">
                                                            <div>
                                                                <div className="flex items-center gap-2 mb-1">
                                                                    <span className="text-[10px] font-bold text-indigo-600">S1</span>
                                                                    <div className="flex-1 bg-slate-100 rounded-full h-2.5 overflow-hidden">
                                                                        <div className="h-2.5 rounded-full bg-indigo-500 transition-all" style={{width: `${(s1 / maxSem) * 100}%`}}></div>
                                                                    </div>
                                                                    <span className="text-xs font-bold text-slate-700 w-5 text-right">{s1}</span>
                                                                </div>
                                                                <div className="flex flex-wrap gap-1 mt-1">
                                                                    {(w.s1_subjects || []).map(s => (
                                                                        <span key={s} className="px-1.5 py-0.5 bg-indigo-50 text-indigo-700 border border-indigo-200 rounded text-[9px] font-medium">{s}</span>
                                                                    ))}
                                                                    {(w.both_subjects || []).map(s => (
                                                                        <span key={s} className="px-1.5 py-0.5 bg-emerald-50 text-emerald-700 border border-emerald-200 rounded text-[9px] font-medium">{s} ↔</span>
                                                                    ))}
                                                                </div>
                                                            </div>
                                                            <div>
                                                                <div className="flex items-center gap-2 mb-1">
                                                                    <span className="text-[10px] font-bold text-teal-600">S2</span>
                                                                    <div className="flex-1 bg-slate-100 rounded-full h-2.5 overflow-hidden">
                                                                        <div className="h-2.5 rounded-full bg-teal-500 transition-all" style={{width: `${(s2 / maxSem) * 100}%`}}></div>
                                                                    </div>
                                                                    <span className="text-xs font-bold text-slate-700 w-5 text-right">{s2}</span>
                                                                </div>
                                                                <div className="flex flex-wrap gap-1 mt-1">
                                                                    {(w.s2_subjects || []).map(s => (
                                                                        <span key={s} className="px-1.5 py-0.5 bg-teal-50 text-teal-700 border border-teal-200 rounded text-[9px] font-medium">{s}</span>
                                                                    ))}
                                                                    {(w.both_subjects || []).map(s => (
                                                                        <span key={s} className="px-1.5 py-0.5 bg-emerald-50 text-emerald-700 border border-emerald-200 rounded text-[9px] font-medium">{s} ↔</span>
                                                                    ))}
                                                                </div>
                                                            </div>
                                                        </div>
                                                        {(w.unmatched || []).length > 0 && (
                                                            <div className="mt-2 flex items-center gap-1">
                                                                <span className="text-[10px] text-rose-500 font-bold">⚠ Unmatched:</span>
                                                                {w.unmatched.map(u => (
                                                                    <span key={u} className="px-1.5 py-0.5 bg-rose-50 text-rose-600 border border-rose-200 rounded text-[9px] font-medium">{u}</span>
                                                                ))}
                                                            </div>
                                                        )}
                                                    </div>
                                                )
                                            })}
                                        </div>
                                    )
                                })()
                            ) : (() => {
                                /* Subject Table */
                                const filtered = (staffingData.subjects || []).filter(s => {
                                    const matchTab = staffingTab === 'all' || s.severity === staffingTab
                                    const matchSearch = !staffingSearch || s.code.toLowerCase().includes(staffingSearch.toLowerCase())
                                    return matchTab && matchSearch
                                })
                                // Group by subject code + description: combine LEC + LAB of same subject into one row
                                // Same code can have different subjects (e.g. IT 104 "Social..." vs IT 104 "Networking 1")
                                const grouped = []
                                const codeMap = {}
                                for (const s of filtered) {
                                    const groupKey = `${s.code}||${(s.description || '').toLowerCase()}`
                                    if (!codeMap[groupKey]) {
                                        codeMap[groupKey] = { code: s.code, description: s.description || '', groupKey, entries: [], courses: new Set(), year_levels: new Set() }
                                        grouped.push(codeMap[groupKey])
                                    }
                                    codeMap[groupKey].entries.push(s)
                                    s.courses.forEach(c => codeMap[groupKey].courses.add(c))
                                    s.year_levels?.forEach(y => codeMap[groupKey].year_levels.add(y))
                                }
                                return (
                                    <div className="space-y-2">
                                        {/* Column Headers */}
                                        <div className="grid grid-cols-12 gap-2 px-4 py-2 text-[10px] font-bold text-slate-500 uppercase tracking-wide">
                                            <div className="col-span-2">Subject</div>
                                            <div className="col-span-2">Courses</div>
                                            <div className="col-span-1 text-center">Units</div>
                                            <div className="col-span-1 text-center">Sections</div>
                                            <div className="col-span-1 text-center">Need</div>
                                            <div className="col-span-1 text-center">Listed</div>
                                            <div className="col-span-2 text-center">Effective</div>
                                            <div className="col-span-2 text-center">Status</div>
                                        </div>
                                        {grouped.length === 0 ? (
                                            <div className="text-center py-12 text-slate-400">{staffingSearch ? 'No subjects match your search.' : 'No subjects in this category.'}</div>
                                        ) : grouped.map((group, gIdx) => {
                                            const isExpanded = expandedSubj === group.groupKey
                                            // Use worst severity from all entries
                                            const sevOrder = { critical: 0, warning: 1, ok: 2 }
                                            const worstEntry = [...group.entries].sort((a, b) => (sevOrder[a.severity] ?? 3) - (sevOrder[b.severity] ?? 3))[0]
                                            const severity = worstEntry.severity
                                            // Combine stats: sum sections, use worst effective ratio
                                            const totalSections = group.entries.reduce((sum, e) => sum + e.sections_needed, 0)
                                            const maxProfsNeeded = Math.max(...group.entries.map(e => e.profs_needed))
                                            const minEffective = Math.min(...group.entries.map(e => e.effective_profs))
                                            const maxRawProfs = Math.max(...group.entries.map(e => e.raw_profs))
                                            const worstGap = Math.max(...group.entries.map(e => e.gap_effective))
                                            const unitStr = [...new Set(group.entries.map(e => `${e.type}:${e.units}`))].map(u => u.split(':')[1]).join('+')
                                            const typeStr = group.entries.map(e => e.type).join('+')

                                            const sevConfig = {
                                                critical: { bg: 'bg-rose-100', text: 'text-rose-700', border: 'border-rose-200', dot: 'bg-rose-500' },
                                                warning: { bg: 'bg-amber-100', text: 'text-amber-700', border: 'border-amber-200', dot: 'bg-amber-500' },
                                                ok: { bg: 'bg-emerald-100', text: 'text-emerald-700', border: 'border-emerald-200', dot: 'bg-emerald-500' },
                                            }[severity] || { bg: 'bg-slate-100', text: 'text-slate-600', border: 'border-slate-200', dot: 'bg-slate-400' }
                                            return (
                                                <div key={gIdx}>
                                                    <div
                                                        className={`grid grid-cols-12 gap-2 items-center p-3 rounded-xl border cursor-pointer transition-all hover:shadow-sm ${
                                                            severity === 'critical' ? 'bg-rose-50/50 border-rose-200' :
                                                            severity === 'warning' ? 'bg-amber-50/50 border-amber-200' :
                                                            'bg-white border-slate-100'
                                                        }`}
                                                        onClick={() => setExpandedSubj(isExpanded ? null : group.groupKey)}
                                                    >
                                                        <div className="col-span-2">
                                                            <div className="font-bold text-slate-800 text-sm">{group.code}</div>
                                                            <div className="text-[10px] text-slate-400">{typeStr} · Y{[...group.year_levels].sort().join(',')}</div>
                                                            {group.description && <div className="text-[9px] text-slate-400 truncate max-w-[180px]" title={group.description}>{group.description}</div>}
                                                        </div>
                                                        <div className="col-span-2 flex flex-wrap gap-1">
                                                            {[...group.courses].sort().map(c => (
                                                                <span key={c} className="px-1.5 py-0.5 bg-slate-100 text-slate-600 rounded text-[10px] font-medium">{c}</span>
                                                            ))}
                                                        </div>
                                                        <div className="col-span-1 text-center text-sm font-medium text-slate-700">{unitStr}</div>
                                                        <div className="col-span-1 text-center text-sm font-medium text-slate-700">{totalSections}</div>
                                                        <div className="col-span-1 text-center text-sm font-bold text-slate-800">{maxProfsNeeded}</div>
                                                        <div className="col-span-1 text-center text-sm font-medium text-slate-600">{maxRawProfs}</div>
                                                        <div className="col-span-2 text-center">
                                                            <div className="flex items-center justify-center gap-2">
                                                                <div className="w-16 bg-slate-100 rounded-full h-2 overflow-hidden">
                                                                    <div className={`h-2 rounded-full ${minEffective >= maxProfsNeeded ? 'bg-emerald-500' : minEffective >= maxProfsNeeded * 0.6 ? 'bg-amber-500' : 'bg-rose-500'}`} style={{width: `${Math.min(100, (minEffective / Math.max(maxProfsNeeded, 1)) * 100)}%`}}></div>
                                                                </div>
                                                                <span className="text-xs font-bold text-slate-700 w-8">{minEffective}</span>
                                                            </div>
                                                        </div>
                                                        <div className="col-span-2 text-center flex items-center justify-center gap-2">
                                                            <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold ${sevConfig.bg} ${sevConfig.text}`}>
                                                                <span className={`w-1.5 h-1.5 rounded-full ${sevConfig.dot}`}></span>
                                                                {severity !== 'ok' ? `GAP ${worstGap}` : 'COVERED'}
                                                            </span>
                                                            <span className="text-slate-400 text-xs">{isExpanded ? '▲' : '▼'}</span>
                                                        </div>
                                                    </div>

                                                    {/* Expanded Instructor Details — per type (LEC / LAB) */}
                                                    {isExpanded && (
                                                        <div className="ml-4 mr-4 mb-2 mt-1 p-4 bg-white rounded-xl border border-slate-200 space-y-4">
                                                            {group.entries.map((subj, eIdx) => {
                                                                const typeLabel = subj.type === 'LEC' ? '📖 Lecture' : subj.type === 'LAB' ? '🖥 Laboratory' : subj.type
                                                                const entrySev = {
                                                                    critical: 'text-rose-600', warning: 'text-amber-600', ok: 'text-emerald-600',
                                                                }[subj.severity] || 'text-slate-500'
                                                                return (
                                                                    <div key={eIdx}>
                                                                        <div className="flex items-center gap-3 mb-2">
                                                                            <span className="text-xs font-bold text-slate-600">{typeLabel}</span>
                                                                            <span className="text-[10px] text-slate-400">{subj.units} units/section</span>
                                                                            <span className="text-[10px] text-slate-400">Need {subj.profs_needed} prof(s)</span>
                                                                            <span className={`text-[10px] font-bold ${entrySev}`}>
                                                                                Effective: {subj.effective_profs}
                                                                            </span>
                                                                            {subj.gap_effective > 0 && <span className="text-[10px] font-bold text-rose-500">Gap: {subj.gap_effective}</span>}
                                                                        </div>
                                                                        <div className="space-y-1.5">
                                                                            {subj.instructors.length === 0 ? (
                                                                                <p className="text-sm text-rose-500 font-medium">⚠ No instructors have this subject in their specialization!</p>
                                                                            ) : subj.instructors.map((inst, iIdx) => {
                                                                                const statusColors = {
                                                                                    available: 'bg-emerald-100 text-emerald-700',
                                                                                    limited_by_designation: 'bg-amber-100 text-amber-700',
                                                                                    at_capacity: 'bg-rose-100 text-rose-700',
                                                                                    spread_thin: 'bg-blue-100 text-blue-700',
                                                                                }[inst.status] || 'bg-slate-100 text-slate-600'
                                                                                return (
                                                                                    <div key={iIdx} className="p-2.5 rounded-lg bg-slate-50 border border-slate-100 space-y-1.5">
                                                                                        <div className="flex items-center gap-3">
                                                                                            <div className="flex-1">
                                                                                                <div className="font-bold text-sm text-slate-800">{inst.name}</div>
                                                                                                <div className="text-[10px] text-slate-500 flex gap-2 mt-0.5">
                                                                                                    <span>{inst.type}</span>
                                                                                                    {inst.designation && <span className="text-amber-600 font-semibold">• {inst.designation}</span>}
                                                                                                </div>
                                                                                            </div>
                                                                                            <div className="text-center px-2">
                                                                                                <div className="text-[10px] text-slate-400">Load</div>
                                                                                                <div className="text-xs font-bold text-slate-700">{inst.current_load}/{inst.unit_cap}</div>
                                                                                            </div>
                                                                                            <div className="text-center px-2">
                                                                                                <div className="text-[10px] text-slate-400">Remaining</div>
                                                                                                <div className={`text-xs font-bold ${inst.remaining > 0 ? 'text-emerald-600' : 'text-rose-600'}`}>{inst.remaining}u</div>
                                                                                            </div>
                                                                                            <div className="text-center px-2">
                                                                                                <div className="text-[10px] text-slate-400">Competing</div>
                                                                                                <div className="text-xs font-bold text-slate-600">{inst.competing_subjects}</div>
                                                                                            </div>
                                                                                            <div className="text-center px-2">
                                                                                                <div className="text-[10px] text-slate-400">Sections</div>
                                                                                                <div className="text-xs font-bold text-slate-700">{inst.sections_can_handle}</div>
                                                                                            </div>
                                                                                            <div className="text-center px-2 min-w-[60px]">
                                                                                                <div className="text-[10px] text-slate-400">Effective</div>
                                                                                                <div className={`text-sm font-bold ${inst.effective_contribution >= 0.8 ? 'text-emerald-600' : inst.effective_contribution >= 0.4 ? 'text-amber-600' : 'text-rose-600'}`}>{inst.effective_contribution}</div>
                                                                                            </div>
                                                                                            <span className={`px-2 py-0.5 rounded text-[9px] font-bold uppercase whitespace-nowrap ${statusColors}`}>
                                                                                                {inst.status.replace(/_/g, ' ')}
                                                                                            </span>
                                                                                        </div>
                                                                                        {/* S1/S2 Balance Row */}
                                                                                        {(inst.s1_count != null || inst.s2_count != null) && (
                                                                                            <div className="flex items-center gap-2 pt-1 border-t border-slate-100">
                                                                                                <div className="flex items-center gap-1">
                                                                                                    <span className="text-[9px] font-bold text-indigo-600">S1</span>
                                                                                                    <span className="text-[10px] font-bold text-slate-700 bg-indigo-50 border border-indigo-200 px-1.5 py-px rounded">{inst.s1_count || 0}</span>
                                                                                                </div>
                                                                                                <div className="flex items-center gap-1">
                                                                                                    <span className="text-[9px] font-bold text-teal-600">S2</span>
                                                                                                    <span className="text-[10px] font-bold text-slate-700 bg-teal-50 border border-teal-200 px-1.5 py-px rounded">{inst.s2_count || 0}</span>
                                                                                                </div>
                                                                                                {(inst.s1_count > 0 && (inst.s2_count || 0) === 0) || ((inst.s1_count || 0) === 0 && inst.s2_count > 0) ? (
                                                                                                    <span className="text-[9px] text-amber-600 font-bold">⚠ Lopsided</span>
                                                                                                ) : null}
                                                                                                <div className="flex flex-wrap gap-1 ml-2">
                                                                                                    {(inst.s1_subjects || []).map(s => (
                                                                                                        <span key={`s1-${s}`} className="px-1 py-px bg-indigo-50 text-indigo-600 border border-indigo-200 rounded text-[8px] font-medium">{s}</span>
                                                                                                    ))}
                                                                                                    {(inst.both_subjects || []).map(s => (
                                                                                                        <span key={`b-${s}`} className="px-1 py-px bg-emerald-50 text-emerald-600 border border-emerald-200 rounded text-[8px] font-medium">{s}↔</span>
                                                                                                    ))}
                                                                                                    {(inst.s2_subjects || []).map(s => (
                                                                                                        <span key={`s2-${s}`} className="px-1 py-px bg-teal-50 text-teal-600 border border-teal-200 rounded text-[8px] font-medium">{s}</span>
                                                                                                    ))}
                                                                                                </div>
                                                                                            </div>
                                                                                        )}
                                                                                    </div>
                                                                                )
                                                                            })}
                                                                        </div>
                                                                        {eIdx < group.entries.length - 1 && <hr className="border-slate-200 mt-3" />}
                                                                    </div>
                                                                )
                                                            })}
                                                        </div>
                                                    )}
                                                </div>
                                            )
                                        })}
                                    </div>
                                )
                            })()}
                        </div>

                        {/* Recommendations Footer */}
                        {staffingData && staffingData.recommendations?.length > 0 && staffingTab !== "instructors" && (
                            <div className="px-6 py-4 bg-gradient-to-r from-slate-800 to-slate-900 border-t">
                                <div className="text-xs font-bold text-slate-400 uppercase mb-2">Recommendations</div>
                                <div className="space-y-1.5">
                                    {staffingData.recommendations.map((rec, idx) => (
                                        <p key={idx} className="text-sm text-slate-200">{rec}</p>
                                    ))}
                                </div>
                            </div>
                        )}

                        <div className="p-4 border-t border-slate-100 bg-white flex justify-end">
                            <button onClick={() => { setShowStaffingModal(false); setStaffingSearch(''); setStaffingTab('critical'); setExpandedSubj(null) }} className="px-5 py-2.5 bg-slate-100 hover:bg-slate-200 text-slate-700 font-bold rounded-xl transition-colors">Close</button>
                        </div>
                    </div>
                </div>
            )}

            <ConfirmDialog {...confirmDialog} onCancel={() => setConfirmDialog({ open: false })} />
        </div>
    )
}
