import { useState, useEffect, useMemo } from 'react'
import { getRoomSchedule, list } from '../../services/api'

// Master time slots from 7:00 AM to 7:00 PM (based on registrar time blocks)
const MASTER_TIME_SLOTS = [
    { label: "7:00 AM – 8:30 AM", start: 420, end: 510 },
    { label: "8:30 AM – 10:00 AM", start: 510, end: 600 },
    { label: "10:00 AM – 11:30 AM", start: 600, end: 690 },
    { label: "11:30 AM – 1:00 PM", start: 690, end: 780 },
    { label: "1:00 PM – 2:30 PM", start: 780, end: 870 },
    { label: "2:30 PM – 4:00 PM", start: 870, end: 960 },
    { label: "4:00 PM – 5:30 PM", start: 960, end: 1050 },
    { label: "5:30 PM – 7:00 PM", start: 1050, end: 1140 },
]

export default function RoomSchedule() {
    const [days, setDays] = useState([])
    const [rooms, setRooms] = useState([])
    const [loading, setLoading] = useState(true)

    // Filters
    const [semester, setSemester] = useState('1')
    const [selectedDay, setSelectedDay] = useState('')
    const [selectedRoom, setSelectedRoom] = useState('')

    const [scheduleData, setScheduleData] = useState([])
    const [fetchingSchedule, setFetchingSchedule] = useState(false)

    // Load initial data (days, rooms)
    useEffect(() => {
        const loadMetadata = async () => {
            try {
                const [d, r] = await Promise.all([
                    list('day'),
                    list('room')
                ])
                setDays(d)
                setRooms(r)
                if (d.length > 0) setSelectedDay(d[0].id)
                if (r.length > 0) setSelectedRoom(r[0].id)
            } catch (err) {
                console.error("Failed to load metadata", err)
            } finally {
                setLoading(false)
            }
        }
        loadMetadata()
    }, [])

    // Fetch schedule when filters change
    useEffect(() => {
        if (!selectedRoom || !semester) return

        const fetchSchedule = async () => {
            setFetchingSchedule(true)
            try {
                const data = await getRoomSchedule(selectedRoom, semester, selectedDay || null)
                if (!Array.isArray(data)) throw new Error("Invalid response format")
                setScheduleData(data)
            } catch (err) {
                console.error("Failed to fetch schedule", err)
                setScheduleData([])
            } finally {
                setFetchingSchedule(false)
            }
        }
        fetchSchedule()
    }, [selectedRoom, semester, selectedDay])

    // Extract start time in minutes from a time string
    const extractStartMinutes = (timeStr) => {
        if (!timeStr) return null
        const match = timeStr.match(/(\d{1,2}):(\d{2})/)
        if (match) {
            return parseInt(match[1]) * 60 + parseInt(match[2])
        }
        return null
    }

    // Build full day grid with occupied/vacant slots
    const fullDayGrid = useMemo(() => {
        // Track which schedules have been assigned to prevent duplicates
        const assignedScheduleIds = new Set()

        // Build the grid
        return MASTER_TIME_SLOTS.map((masterSlot, idx) => {
            // Find schedules that start within this master slot's time range
            const matchingSchedules = scheduleData.filter(slot => {
                // Skip if already assigned to another slot
                if (assignedScheduleIds.has(slot.id)) return false

                const startMin = extractStartMinutes(slot.time)
                if (startMin === null) return false

                // Check if schedule starts within this master slot
                return startMin >= masterSlot.start && startMin < masterSlot.end
            })

            // Mark these schedules as assigned
            matchingSchedules.forEach(s => assignedScheduleIds.add(s.id))

            if (matchingSchedules.length > 0) {
                // Return occupied slots
                return matchingSchedules.map((schedule, subIdx) => ({
                    ...schedule,
                    masterSlotLabel: masterSlot.label,
                    isVacant: false,
                    key: `${idx}-${subIdx}-${schedule.id}`
                }))
            } else {
                // Return vacant slot
                return [{
                    masterSlotLabel: masterSlot.label,
                    isVacant: true,
                    key: `${idx}-vacant`
                }]
            }
        }).flat()
    }, [scheduleData])

    // Helper to format time robustly
    const formatTime = (timeStr) => {
        if (!timeStr) return '—'
        const timePattern = /(\d{1,2}):(\d{2})/g
        const matches = [...timeStr.matchAll(timePattern)]
        if (matches.length === 0) return timeStr

        const to12Hour = (hour, minute) => {
            const h = parseInt(hour)
            const ampm = h >= 12 ? 'PM' : 'AM'
            const h12 = h % 12 || 12
            return `${h12}:${minute} ${ampm}`
        }

        if (matches.length >= 2) {
            return `${to12Hour(matches[0][1], matches[0][2])} – ${to12Hour(matches[1][1], matches[1][2])}`
        }
        return to12Hour(matches[0][1], matches[0][2])
    }

    const getTypeBadge = (type) => {
        switch (type) {
            case 'LEC': return 'bg-blue-100 text-blue-700 border-blue-200'
            case 'LAB': return 'bg-purple-100 text-purple-700 border-purple-200'
            default: return 'bg-slate-100 text-slate-700 border-slate-200'
        }
    }

    const getDayBadge = (day) => {
        switch (day) {
            case 'M': return 'bg-amber-100 text-amber-700'
            case 'T': return 'bg-emerald-100 text-emerald-700'
            case 'W': return 'bg-cyan-100 text-cyan-700'
            case 'TH': return 'bg-indigo-100 text-indigo-700'
            case 'F': return 'bg-rose-100 text-rose-700'
            case 'S': return 'bg-violet-100 text-violet-700'
            default: return 'bg-slate-100 text-slate-700'
        }
    }

    if (loading) {
        return (
            <div className="flex items-center justify-center h-full min-h-[400px]">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600"></div>
            </div>
        )
    }

    return (
        <div className="space-y-6">
            <header>
                <h1 className="text-3xl font-bold text-slate-800 mb-2">
                    🏢 Room <span className="bg-gradient-to-r from-blue-500 to-cyan-500 bg-clip-text text-transparent">Schedule</span>
                </h1>
                <p className="text-slate-500">Full day view of room utilization and vacancies.</p>
            </header>

            {/* Filters */}
            <div className="bg-white/80 backdrop-blur-xl p-6 rounded-2xl shadow-sm border border-slate-200 grid grid-cols-1 md:grid-cols-3 gap-6">
                <div>
                    <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">Semester</label>
                    <select
                        value={semester}
                        onChange={e => setSemester(e.target.value)}
                        className="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-blue-500 focus:bg-white transition-all font-medium text-slate-700"
                    >
                        <option value="1">1st Semester</option>
                        <option value="2">2nd Semester</option>
                    </select>
                </div>

                <div>
                    <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">Filter by Day</label>
                    <select
                        value={selectedDay}
                        onChange={e => setSelectedDay(e.target.value)}
                        className="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-blue-500 focus:bg-white transition-all font-medium text-slate-700"
                    >
                        <option value="">All Days</option>
                        {days.map(d => (
                            <option key={d.id} value={d.id}>{d.label}</option>
                        ))}
                    </select>
                </div>

                <div>
                    <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">Select Room</label>
                    <select
                        value={selectedRoom}
                        onChange={e => setSelectedRoom(e.target.value)}
                        className="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-blue-500 focus:bg-white transition-all font-medium text-slate-700"
                    >
                        {rooms.map(r => (
                            <option key={r.id} value={r.id}>{r.name} ({r.type})</option>
                        ))}
                    </select>
                </div>
            </div>

            {/* Schedule Display */}
            <div className="bg-white/80 backdrop-blur-xl rounded-2xl shadow-sm border border-slate-200 overflow-hidden min-h-[400px]">
                <div className="p-6 border-b border-slate-100 flex justify-between items-center">
                    <div>
                        <h2 className="text-lg font-bold text-slate-800 flex items-center gap-2">
                            Full Day Schedule
                            {fetchingSchedule && <span className="text-xs font-normal text-blue-500 animate-pulse bg-blue-50 px-2 py-0.5 rounded-full">Updating...</span>}
                        </h2>
                        <p className="text-sm text-slate-500 mt-1">7:00 AM – 7:00 PM time slots</p>
                    </div>
                </div>

                {fetchingSchedule && fullDayGrid.length === 0 ? (
                    <div className="flex flex-col items-center justify-center py-24 text-slate-400">
                        <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-blue-500 mb-4"></div>
                        <p className="font-medium animate-pulse">Loading schedule...</p>
                    </div>
                ) : (
                    <div className="overflow-x-auto">
                        <table className="w-full">
                            <thead className="bg-slate-50/50">
                                <tr>
                                    <th className="text-left px-6 py-4 text-slate-500 font-semibold text-xs uppercase tracking-wider">#</th>
                                    <th className="text-left px-6 py-4 text-slate-500 font-semibold text-xs uppercase tracking-wider">Time Slot</th>
                                    {!selectedDay && <th className="text-left px-6 py-4 text-slate-500 font-semibold text-xs uppercase tracking-wider">Day</th>}
                                    <th className="text-left px-6 py-4 text-slate-500 font-semibold text-xs uppercase tracking-wider">Subject Code</th>
                                    <th className="text-left px-6 py-4 text-slate-500 font-semibold text-xs uppercase tracking-wider">Description</th>
                                    <th className="text-left px-6 py-4 text-slate-500 font-semibold text-xs uppercase tracking-wider">Type</th>
                                    <th className="text-left px-6 py-4 text-slate-500 font-semibold text-xs uppercase tracking-wider">Instructor</th>
                                    <th className="text-left px-6 py-4 text-slate-500 font-semibold text-xs uppercase tracking-wider">Block</th>
                                    <th className="text-left px-6 py-4 text-slate-500 font-semibold text-xs uppercase tracking-wider">Status</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-slate-100">
                                {fullDayGrid.map((slot, idx) => (
                                    <tr key={slot.key} className={`transition-colors ${slot.isVacant ? 'bg-green-50/30 hover:bg-green-50/50' : 'hover:bg-slate-50'}`}>
                                        <td className="px-6 py-4 text-slate-400 font-mono text-sm">{idx + 1}</td>
                                        <td className="px-6 py-4 text-slate-600 font-mono text-sm font-medium">
                                            {slot.isVacant ? slot.masterSlotLabel : formatTime(slot.time)}
                                        </td>
                                        {!selectedDay && (
                                            <td className="px-6 py-4">
                                                {slot.isVacant ? (
                                                    <span className="text-slate-400">—</span>
                                                ) : (
                                                    <span className={`px-2.5 py-1 rounded-lg text-xs font-bold ${getDayBadge(slot.day_label)}`}>
                                                        {slot.day_label}
                                                    </span>
                                                )}
                                            </td>
                                        )}
                                        <td className="px-6 py-4">
                                            <span className={`text-sm ${slot.isVacant ? 'text-slate-400 italic' : 'text-slate-800 font-semibold'}`}>
                                                {slot.isVacant ? '—' : (slot.subject_code || '—')}
                                            </span>
                                        </td>
                                        <td className="px-6 py-4 text-sm max-w-xs truncate" title={slot.subject_description}>
                                            <span className={slot.isVacant ? 'text-slate-400 italic' : 'text-slate-600'}>
                                                {slot.isVacant ? 'Available for schedule' : (slot.subject_description || '—')}
                                            </span>
                                        </td>
                                        <td className="px-6 py-4">
                                            {slot.isVacant ? (
                                                <span className="text-slate-400">—</span>
                                            ) : (
                                                <span className={`px-2 py-1 rounded-lg text-xs font-medium border ${getTypeBadge(slot.type)}`}>
                                                    {slot.type || '—'}
                                                </span>
                                            )}
                                        </td>
                                        <td className="px-6 py-4 text-sm font-medium">
                                            <span className={slot.isVacant ? 'text-slate-400' : 'text-slate-700'}>
                                                {slot.isVacant ? '—' : (slot.instructor_name || '—')}
                                            </span>
                                        </td>
                                        <td className="px-6 py-4">
                                            {slot.isVacant ? (
                                                <span className="text-slate-400">—</span>
                                            ) : (
                                                <span className="px-2.5 py-1 rounded-lg bg-slate-100 text-slate-600 font-medium text-xs border border-slate-200">
                                                    {slot.block || '—'}
                                                </span>
                                            )}
                                        </td>
                                        <td className="px-6 py-4">
                                            {slot.isVacant ? (
                                                <div className="flex items-center gap-1.5">
                                                    <span className="relative flex h-2.5 w-2.5">
                                                        <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-500"></span>
                                                    </span>
                                                    <span className="text-xs font-medium text-emerald-600">Vacant</span>
                                                </div>
                                            ) : (
                                                <div className="flex items-center gap-1.5">
                                                    <span className="relative flex h-2.5 w-2.5">
                                                        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75"></span>
                                                        <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-red-500"></span>
                                                    </span>
                                                    <span className="text-xs font-medium text-red-600">Occupied</span>
                                                </div>
                                            )}
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                )}
            </div>
        </div>
    )
}
