import { useEffect, useMemo, useState } from 'react'
import { useOutletContext } from 'react-router-dom'
import { list } from '../../store/db'
import { loadInstructorSchedules, searchSwappableSchedules, createSwapRequest, validateSwapRequest } from '../../services/api'

export default function Schedule() {
    const [courses, setCourses] = useState([])
    const [subjects, setSubjects] = useState([])
    const [instructors, setInstructors] = useState([])
    const [rooms, setRooms] = useState([])
    const [days, setDays] = useState([])
    const [courseId, setCourseId] = useState('')
    const [year, setYear] = useState('')  // Empty = All Years
    const [sem, setSem] = useState('1')
    const [rows, setRows] = useState([])
    const [rawScheduleCount, setRawScheduleCount] = useState(0)  // Raw count before merging
    const [allInstructorSchedules, setAllInstructorSchedules] = useState([])
    const [coursesWithScheduleIds, setCoursesWithScheduleIds] = useState([])
    const [hasCheckedSchedule, setHasCheckedSchedule] = useState(false)
    const [loading, setLoading] = useState(true)

    // Get isDark from layout context
    const { isDark } = useOutletContext() || { isDark: false }

    // Swap modal state
    const [showSwapModal, setShowSwapModal] = useState(false)
    const [selectedSchedule, setSelectedSchedule] = useState(null)
    const [swapSearchResults, setSwapSearchResults] = useState([])
    const [swapSearchLoading, setSwapSearchLoading] = useState(false)
    const [swapReason, setSwapReason] = useState('')
    const [selectedSwapTarget, setSelectedSwapTarget] = useState(null)
    const [swapMessage, setSwapMessage] = useState('')
    const [swapError, setSwapError] = useState('')
    const [swapConflicts, setSwapConflicts] = useState([]) // New state for conflicts

    // Swap filter state
    const [swapFilterDay, setSwapFilterDay] = useState('')
    const [swapFilterRoom, setSwapFilterRoom] = useState('')
    const [swapFilterStartTime, setSwapFilterStartTime] = useState('07:00')
    const [swapFilterEndTime, setSwapFilterEndTime] = useState('21:00')

    const session = (() => {
        try { return JSON.parse(localStorage.getItem('jrmsu.session') || 'null') } catch { return null }
    })()

    const currentInstructorId = session?.instructorId || null

    useEffect(() => {
        async function loadData() {
            const [coursesData, subjectsData, instructorsData, roomsData, daysData] = await Promise.all([
                list('course'),
                list('subject'),
                list('instructor'),
                list('room'),
                list('day')
            ])
            setCourses(coursesData)
            setSubjects(subjectsData)
            setInstructors(instructorsData)
            setRooms(roomsData)
            setDays(daysData)
        }
        loadData()
    }, [])

    // Load all instructor schedules with a single optimized API call
    useEffect(() => {
        let cancelled = false
        async function fetchInstructorSchedules() {
            if (!currentInstructorId) {
                setCoursesWithScheduleIds([])
                setAllInstructorSchedules([])
                setHasCheckedSchedule(true)
                setLoading(false)
                return
            }
            setLoading(true)
            try {
                // Single API call instead of N×2 calls
                const resp = await loadInstructorSchedules(currentInstructorId)
                if (cancelled) return

                if (resp && resp.status === 'success') {
                    const courseIds = resp.course_ids || []
                    const items = resp.items || []

                    // Debug: log the response
                    console.log('[Schedule] Loaded instructor schedules:', {
                        count: items.length,
                        courseIds,
                        itemSample: items.slice(0, 3)
                    })

                    setAllInstructorSchedules(items)
                    setCoursesWithScheduleIds(courseIds)
                    setHasCheckedSchedule(true)

                    if (!courseIds.length) {
                        setCourseId('')
                        setRows([])
                    } else {
                        setCourseId(prev => {
                            const prevNum = parseInt(prev, 10)
                            return prevNum && courseIds.includes(prevNum) ? prev : String(courseIds[0])
                        })
                    }
                } else {
                    console.warn('[Schedule] API returned non-success:', resp)
                    setCoursesWithScheduleIds([])
                    setAllInstructorSchedules([])
                    setHasCheckedSchedule(true)
                }
            } catch (error) {
                console.error('Error loading instructor schedules:', error)
                setCoursesWithScheduleIds([])
                setAllInstructorSchedules([])
                setHasCheckedSchedule(true)
            } finally {
                if (!cancelled) setLoading(false)
            }
        }
        fetchInstructorSchedules()
        return () => { cancelled = true }
    }, [currentInstructorId])

    // Filter schedules for the selected course and semester from cached data
    useEffect(() => {
        if (!courseId || !allInstructorSchedules.length) {
            setRows([])
            return
        }

        // Filter by course and semester from cached schedules
        const courseIdNum = parseInt(courseId, 10)
        const semNum = parseInt(sem, 10)
        const yearNum = year ? parseInt(year, 10) : null  // null means all years

        const filtered = allInstructorSchedules.filter(s => {
            if (s.course_id !== courseIdNum) return false
            if (s.semester !== semNum) return false
            if (yearNum !== null && s.year !== yearNum) return false
            return true
        })

        if (!filtered.length) {
            setRows([])
            setRawScheduleCount(0)
            return
        }

        // Store raw count before grouping
        setRawScheduleCount(filtered.length)

        const dayLabelById = {}
        for (const d of (days || [])) {
            if (d && d.id != null) dayLabelById[d.id] = d.label
        }
        const dayOrder = { M: 0, T: 1, W: 2, TH: 3, F: 4, SAT: 5, SUN: 6 }

        const grouped = {}
        for (const item of filtered) {
            const subjectKey = item.subject_id || item.subjectId || ''
            const instructorKey = item.instructor_id || item.instructorId || ''
            const roomKey = item.room_id || item.roomId || ''
            const rawTimeKey = item.time || ''
            const timeKey = typeof rawTimeKey === 'string' ? rawTimeKey.replace(/^(M|T|W|TH|F|SAT|SUN)\s+/, '') : rawTimeKey
            const blockKey = item.block || ''
            const groupKey = `${subjectKey}|${instructorKey}|${roomKey}|${timeKey}|${blockKey}`
            if (!grouped[groupKey]) {
                grouped[groupKey] = { ...item, _dayIds: [] }
            }
            const dayId = item.day_id || item.dayId
            if (dayId != null && !grouped[groupKey]._dayIds.includes(dayId)) {
                grouped[groupKey]._dayIds.push(dayId)
            }
        }

        const merged = Object.values(grouped).map(g => {
            const dayIds = g._dayIds || []
            const labels = dayIds.map(id => dayLabelById[id]).filter(Boolean).sort((a, b) => (dayOrder[a] ?? 99) - (dayOrder[b] ?? 99))
            let combinedDays = ''
            if (labels.length === 2) {
                const [d1, d2] = labels
                if ((d1 === 'M' && d2 === 'W') || (d1 === 'W' && d2 === 'M')) combinedDays = 'M-W'
                else if ((d1 === 'T' && d2 === 'TH') || (d1 === 'TH' && d2 === 'T')) combinedDays = 'T-TH'
                else combinedDays = labels.join('-')
            } else {
                combinedDays = labels.join('-')
            }
            const { _dayIds, ...rest } = g
            return { ...rest, day_id: dayIds[0] ?? g.day_id ?? g.dayId ?? null, _combinedDaysLabel: combinedDays || (labels[0] || '') }
        })

        setRows(merged)
    }, [courseId, sem, year, allInstructorSchedules, days])

    const getSubject = (id) => subjects.find(s => s.id === id)
    const getDay = (r) => {
        const combined = r?._combinedDaysLabel
        if (combined) return combined
        const id = r?.dayId || r?.day_id
        return days.find(d => d.id === id)?.label || ''
    }
    const getRoom = (id) => rooms.find(r => r.id === id)?.name || ''

    const currentInstructor = instructors.find(i => i.id === currentInstructorId)
    const instructorName = currentInstructor
        ? `${currentInstructor.first_name || currentInstructor.firstName || ''} ${currentInstructor.last_name || currentInstructor.lastName || ''}`.trim()
        : 'Unknown'

    const hasAnySchedule = hasCheckedSchedule && coursesWithScheduleIds.length > 0
    const noScheduleForInstructor = hasCheckedSchedule && currentInstructorId && !hasAnySchedule
    // Ensure type-safe comparison (API returns integers, but course.id might be number or string)
    const visibleCourses = hasAnySchedule
        ? courses.filter(c => coursesWithScheduleIds.includes(typeof c.id === 'number' ? c.id : parseInt(c.id, 10)))
        : []

    const theme = {
        bg: isDark ? 'bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900' : 'bg-gradient-to-br from-slate-50 via-white to-slate-100',
        text: isDark ? 'text-white' : 'text-slate-800',
        textMuted: isDark ? 'text-slate-400' : 'text-slate-500',
        card: isDark ? 'bg-slate-800/50 border-slate-700/50' : 'bg-white/80 border-slate-200 shadow-lg',
        input: isDark ? 'bg-slate-700/50 border-slate-600 text-white' : 'bg-white border-slate-300 text-slate-800',
        table: isDark ? 'bg-slate-800/50 border-slate-700/50' : 'bg-white border-slate-200 shadow-lg',
        tableHeader: isDark ? 'bg-slate-900/50' : 'bg-slate-100',
        tableRow: isDark ? 'hover:bg-slate-700/30' : 'hover:bg-slate-50',
        tableDivide: isDark ? 'divide-slate-700/50' : 'divide-slate-200',
    }

    const getTypeBadge = (type) => {
        if (type === 'LEC') return isDark ? 'bg-blue-500/20 text-blue-400 border-blue-500/30' : 'bg-blue-100 text-blue-600 border-blue-200'
        if (type === 'LAB') return isDark ? 'bg-purple-500/20 text-purple-400 border-purple-500/30' : 'bg-purple-100 text-purple-600 border-purple-200'
        return isDark ? 'bg-slate-500/20 text-slate-400 border-slate-500/30' : 'bg-slate-100 text-slate-600 border-slate-200'
    }

    const getDayBadge = (day) => {
        if (day?.includes('SUN')) return isDark ? 'bg-orange-500/20 text-orange-400' : 'bg-orange-100 text-orange-600'
        if (day?.includes('SAT')) return isDark ? 'bg-amber-500/20 text-amber-400' : 'bg-amber-100 text-amber-600'
        return isDark ? 'bg-emerald-500/20 text-emerald-400' : 'bg-emerald-100 text-emerald-600'
    }

    // Convert 24-hour time to 12-hour format
    const formatTime12Hour = (timeStr) => {
        if (!timeStr) return '—'

        // Handle time ranges like "16:00:00–19:00:00" or "15:00–17:00"
        const parts = timeStr.split(/[–-]/).map(t => t.trim())

        const convertSingle = (t) => {
            // Extract hours and minutes from formats like "16:00:00", "16:00", "M 15:00"
            const cleaned = t.replace(/^[MTWTHFSAT]+\s*/i, '') // Remove day prefix
            const match = cleaned.match(/(\d{1,2}):(\d{2})/)
            if (!match) return t

            let hours = parseInt(match[1], 10)
            const minutes = match[2]
            const period = hours >= 12 ? 'PM' : 'AM'

            if (hours === 0) hours = 12
            else if (hours > 12) hours -= 12

            return `${hours}:${minutes} ${period}`
        }

        if (parts.length === 2) {
            return `${convertSingle(parts[0])} - ${convertSingle(parts[1])}`
        }
        return convertSingle(timeStr)
    }

    // Get instructor name by ID
    const getInstructorName = (id) => {
        const instructor = instructors.find(i => i.id === id)
        if (!instructor) return '—'
        return `${instructor.first_name || instructor.firstName || ''} ${instructor.last_name || instructor.lastName || ''}`.trim() || '—'
    }

    // Open swap modal - just opens modal without auto-searching
    const openSwapModal = (schedule) => {
        setSelectedSchedule(schedule)
        setShowSwapModal(true)
        setSwapSearchResults([])
        setSelectedSwapTarget(null)
        setSwapReason('')
        setSwapMessage('')
        setSwapError('')
        setSwapConflicts([])
        setSwapFilterDay('')
        setSwapFilterRoom('')
        setSwapFilterStartTime('07:00')
        setSwapFilterEndTime('21:00')
        setSwapSearchLoading(false)
    }

    // Search with filters
    const searchWithFilters = async () => {
        if (!selectedSchedule) return

        setSwapSearchLoading(true)
        setSwapError('')
        setSelectedSwapTarget(null)

        try {
            // Convert time to minutes for comparison
            const startMin = swapFilterStartTime ?
                parseInt(swapFilterStartTime.split(':')[0]) * 60 + parseInt(swapFilterStartTime.split(':')[1]) : null
            const endMin = swapFilterEndTime ?
                parseInt(swapFilterEndTime.split(':')[0]) * 60 + parseInt(swapFilterEndTime.split(':')[1]) : null

            const params = {
                instructor_id: currentInstructorId,
                schedule_id: selectedSchedule.id,
                requester_schedule_id: selectedSchedule.id // Redundant but clear for backend
            }

            // Add day filter if selected
            if (swapFilterDay) {
                const selectedDay = days.find(d => d.label === swapFilterDay)
                if (selectedDay) {
                    params.day_ids = [selectedDay.id]
                }
            }

            // Add time range filter
            if (startMin !== null) params.time_range_start = startMin
            if (endMin !== null) params.time_range_end = endMin

            const result = await searchSwappableSchedules(params)
            let filtered = result.schedules || []

            // Client-side room filter
            if (swapFilterRoom) {
                filtered = filtered.filter(s => s.room_id === parseInt(swapFilterRoom))
            }

            // Client-side time range filter (more precise)
            if (startMin !== null && endMin !== null) {
                filtered = filtered.filter(s => {
                    // Parse the time string to get start time
                    const timeStr = s.time || ''
                    const match = timeStr.match(/(\d{1,2}):(\d{2})/)
                    if (!match) return true
                    const scheduleStartMin = parseInt(match[1]) * 60 + parseInt(match[2])
                    return scheduleStartMin >= startMin && scheduleStartMin <= endMin
                })
            }

            setSwapSearchResults(filtered)
        } catch (err) {
            setSwapError(err.message || 'Failed to search schedules')
        } finally {
            setSwapSearchLoading(false)
        }
    }

    // Submit swap request
    const handleSubmitSwapRequest = async () => {
        if (!selectedSchedule || !selectedSwapTarget) return

        try {
            await createSwapRequest({
                requester_schedule_id: selectedSchedule.id,
                target_schedule_id: selectedSwapTarget.id,
                requester_id: currentInstructorId,
                reason: swapReason
            })
            setSwapMessage('Swap request sent successfully!')
            setTimeout(() => {
                setShowSwapModal(false)
            }, 2000)
        } catch (err) {
            // Handle conflicts if available
            if (err.data && err.data.conflicts) {
                setSwapConflicts(err.data.conflicts)
                setSwapError('Swap cannot be processed due to scheduling conflicts.')
            } else {
                setSwapError(err.message || 'Failed to create swap request')
                setSwapConflicts([])
            }
        }

    }

    // Handle selection with real-time validation
    const handleSelectSwapTarget = async (schedule) => {
        // Toggle selection
        if (selectedSwapTarget?.id === schedule.id) {
            setSelectedSwapTarget(null)
            setSwapConflicts([])
            setSwapError('')
            return
        }

        setSelectedSwapTarget(schedule)
        setSwapConflicts([])
        setSwapError('')

        // Validate immediately
        try {
            const res = await validateSwapRequest({
                requester_schedule_id: selectedSchedule.id,
                target_schedule_id: schedule.id
            })

            if (res && res.conflicts && res.conflicts.length > 0) {
                setSwapConflicts(res.conflicts)
                // Optional: set a warning message, but keeping error clear for now
            }
        } catch (err) {
            console.error("Validation failed", err)
        }
    }

    const SwapConflictsDisplay = ({ conflicts }) => {
        if (!conflicts || conflicts.length === 0) return null

        return (
            <div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-xl space-y-3">
                <div className="flex items-center gap-2 text-red-700 font-semibold">
                    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                    </svg>
                    <span>Swap Conflicts Detected</span>
                </div>
                <div className="space-y-2">
                    {conflicts.map((c, idx) => (
                        <div key={idx} className="flex items-start gap-3 text-sm p-2 bg-white/50 rounded-lg">
                            <div className={`mt-0.5 p-1 rounded shrink-0 ${c.type === 'instructor' ? 'bg-purple-100 text-purple-700' :
                                c.type === 'student' ? 'bg-orange-100 text-orange-700' :
                                    'bg-blue-100 text-blue-700'
                                }`}>
                                {c.type === 'instructor' && (
                                    <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" /></svg>
                                )}
                                {c.type === 'student' && (
                                    <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" /></svg>
                                )}
                                {c.type === 'room' && (
                                    <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" /></svg>
                                )}
                            </div>
                            <div>
                                <p className="font-medium text-red-800">{c.message}</p>
                                {c.details && <p className="text-red-600/80 text-xs mt-0.5">{c.details}</p>}
                            </div>
                        </div>
                    ))}
                </div>
            </div>
        )
    }

    return (
        <>
            <div className={`min-h-screen ${theme.bg} p-6`}>
                <div className="max-w-7xl mx-auto">
                    <div className="flex flex-col md:flex-row md:items-center md:justify-between mb-8">
                        <div>
                            <h1 className={`text-3xl font-bold ${theme.text} mb-2`}>
                                📅 My <span className="bg-gradient-to-r from-blue-500 to-cyan-500 bg-clip-text text-transparent">Schedule</span>
                            </h1>
                            <p className={theme.textMuted}>View your assigned classes and teaching schedule</p>
                        </div>
                    </div>

                    {currentInstructorId && (
                        <div className={`mb-6 p-4 backdrop-blur-xl rounded-2xl border ${isDark ? 'bg-gradient-to-r from-blue-600/20 to-cyan-600/20 border-blue-500/20' : 'bg-gradient-to-r from-blue-50 to-cyan-50 border-blue-200'}`}>
                            <div className="flex items-center gap-3">
                                <div className={`w-12 h-12 rounded-xl flex items-center justify-center ${isDark ? 'bg-blue-500/20' : 'bg-blue-100'}`}>
                                    <svg className="w-6 h-6 text-blue-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                                    </svg>
                                </div>
                                <div>
                                    <p className={theme.textMuted + ' text-sm'}>Viewing schedule for</p>
                                    <p className={`${theme.text} font-semibold text-lg`}>{instructorName}</p>
                                </div>
                            </div>
                        </div>
                    )}

                    {loading ? (
                        <div className="flex items-center justify-center py-24">
                            <div className={`flex items-center gap-3 ${theme.textMuted}`}>
                                <svg className="w-6 h-6 animate-spin" fill="none" viewBox="0 0 24 24">
                                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                                </svg>
                                <span>Loading your schedule...</span>
                            </div>
                        </div>
                    ) : noScheduleForInstructor ? (
                        <div className="flex items-center justify-center py-24">
                            <div className="text-center">
                                <div className={`w-20 h-20 mx-auto mb-4 rounded-full flex items-center justify-center ${isDark ? 'bg-slate-700/50' : 'bg-slate-100'}`}>
                                    <svg className={`w-10 h-10 ${theme.textMuted}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                                    </svg>
                                </div>
                                <p className={`text-xl ${theme.text} font-medium`}>No schedule assigned yet</p>
                                <p className={theme.textMuted + ' mt-2'}>Please contact the registrar for more information.</p>
                            </div>
                        </div>
                    ) : (
                        <>
                            <div className="flex flex-wrap items-center gap-4 mb-6">
                                <div className="flex-1 min-w-[200px]">
                                    <label className={theme.textMuted + ' block text-sm mb-2'}>Course</label>
                                    <select className={`w-full px-4 py-3 rounded-xl ${theme.input} border focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all`} value={courseId} onChange={e => setCourseId(e.target.value)}>
                                        <option value="">Select Course</option>
                                        {visibleCourses.map(c => <option key={c.id} value={c.id}>{c.code} — {c.description}</option>)}
                                    </select>
                                </div>
                                <div>
                                    <label className={theme.textMuted + ' block text-sm mb-2'}>Year Level</label>
                                    <select className={`px-4 py-3 rounded-xl ${theme.input} border focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all`} value={year} onChange={e => setYear(e.target.value)}>
                                        <option value="">All Years</option>
                                        <option value="1">1st Year</option>
                                        <option value="2">2nd Year</option>
                                        <option value="3">3rd Year</option>
                                        <option value="4">4th Year</option>
                                    </select>
                                </div>
                                <div>
                                    <label className={theme.textMuted + ' block text-sm mb-2'}>Semester</label>
                                    <select className={`px-4 py-3 rounded-xl ${theme.input} border focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all`} value={sem} onChange={e => setSem(e.target.value)}>
                                        <option value="1">1st Semester</option>
                                        <option value="2">2nd Semester</option>
                                    </select>
                                </div>
                            </div>

                            {rows.length > 0 && (
                                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
                                    <div className={`backdrop-blur-xl rounded-xl border p-4 ${theme.card}`}>
                                        <p className={theme.textMuted + ' text-sm'}>Total Classes</p>
                                        <p className={`text-2xl font-bold ${theme.text}`}>{rawScheduleCount}</p>
                                    </div>
                                    <div className={`backdrop-blur-xl rounded-xl border p-4 ${theme.card}`}>
                                        <p className={theme.textMuted + ' text-sm'}>Lectures</p>
                                        <p className="text-2xl font-bold text-blue-500">{rows.filter(r => getSubject(r.subjectId || r.subject_id)?.type === 'LEC').length}</p>
                                    </div>
                                    <div className={`backdrop-blur-xl rounded-xl border p-4 ${theme.card}`}>
                                        <p className={theme.textMuted + ' text-sm'}>Labs</p>
                                        <p className="text-2xl font-bold text-purple-500">{rows.filter(r => getSubject(r.subjectId || r.subject_id)?.type === 'LAB').length}</p>
                                    </div>
                                    <div className={`backdrop-blur-xl rounded-xl border p-4 ${theme.card}`}>
                                        <p className={theme.textMuted + ' text-sm'}>Total Units</p>
                                        <p className="text-2xl font-bold text-emerald-500">{rows.reduce((sum, r) => sum + (parseInt(getSubject(r.subjectId || r.subject_id)?.unit) || 0), 0)}</p>
                                    </div>
                                </div>
                            )}

                            {rows.length > 0 ? (
                                <div className={`backdrop-blur-xl rounded-2xl border overflow-hidden ${theme.table}`}>
                                    <div className="overflow-x-auto">
                                        <table className="w-full">
                                            <thead>
                                                <tr className={theme.tableHeader}>
                                                    <th className={`text-left px-4 py-4 ${theme.textMuted} font-medium text-sm`}>#</th>
                                                    <th className={`text-left px-4 py-4 ${theme.textMuted} font-medium text-sm`}>Subject Code</th>
                                                    <th className={`text-left px-4 py-4 ${theme.textMuted} font-medium text-sm`}>Description</th>
                                                    <th className={`text-left px-4 py-4 ${theme.textMuted} font-medium text-sm`}>Type</th>
                                                    <th className={`text-left px-4 py-4 ${theme.textMuted} font-medium text-sm`}>Units</th>
                                                    <th className={`text-left px-4 py-4 ${theme.textMuted} font-medium text-sm`}>Day</th>
                                                    <th className={`text-left px-4 py-4 ${theme.textMuted} font-medium text-sm`}>Time</th>
                                                    <th className={`text-left px-4 py-4 ${theme.textMuted} font-medium text-sm`}>Room</th>
                                                    <th className={`text-left px-4 py-4 ${theme.textMuted} font-medium text-sm`}>Block</th>
                                                    <th className={`text-left px-4 py-4 ${theme.textMuted} font-medium text-sm`}>Action</th>
                                                </tr>
                                            </thead>
                                            <tbody className={`divide-y ${theme.tableDivide}`}>
                                                {rows.map((r, idx) => {
                                                    const s = getSubject(r.subjectId || r.subject_id) || {}
                                                    const dayLabel = getDay(r)
                                                    return (
                                                        <tr key={idx} className={`${theme.tableRow} transition-colors`}>
                                                            <td className={`px-4 py-4 ${theme.textMuted} font-mono`}>{idx + 1}</td>
                                                            <td className="px-4 py-4"><span className={`${theme.text} font-medium`}>{s.code || '—'}</span></td>
                                                            <td className={`px-4 py-4 ${isDark ? 'text-slate-300' : 'text-slate-600'} max-w-xs truncate`}>{s.description || '—'}</td>
                                                            <td className="px-4 py-4"><span className={`px-2 py-1 rounded-lg text-xs font-medium border ${getTypeBadge(s.type)}`}>{s.type || '—'}</span></td>
                                                            <td className={`px-4 py-4 ${isDark ? 'text-slate-300' : 'text-slate-600'} text-center`}>{s.unit || '—'}</td>
                                                            <td className="px-4 py-4"><span className={`px-2 py-1 rounded-lg text-xs font-medium ${getDayBadge(dayLabel)}`}>{dayLabel || '—'}</span></td>
                                                            <td className={`px-4 py-4 ${isDark ? 'text-slate-300' : 'text-slate-600'} font-mono text-sm`}>{formatTime12Hour(r.time)}</td>
                                                            <td className="px-4 py-4"><span className="text-cyan-500">{getRoom(r.roomId || r.room_id) || '—'}</span></td>
                                                            <td className="px-4 py-4"><span className={`px-2 py-1 rounded-lg text-xs font-medium ${isDark ? 'bg-slate-600/50 text-slate-300' : 'bg-slate-100 text-slate-600'}`}>{r.block || '—'}</span></td>
                                                            <td className="px-4 py-4">
                                                                <button
                                                                    onClick={() => openSwapModal(r)}
                                                                    className="px-3 py-1.5 text-xs font-medium rounded-lg bg-indigo-500 text-white hover:bg-indigo-600 transition-colors"
                                                                >
                                                                    Request Swap
                                                                </button>
                                                            </td>
                                                        </tr>
                                                    )
                                                })}
                                            </tbody>
                                        </table>
                                    </div>
                                </div>
                            ) : courseId ? (
                                <div className="flex items-center justify-center py-24">
                                    <div className="text-center">
                                        <div className={`w-20 h-20 mx-auto mb-4 rounded-full flex items-center justify-center ${isDark ? 'bg-slate-700/50' : 'bg-slate-100'}`}>
                                            <svg className={`w-10 h-10 ${theme.textMuted}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
                                            </svg>
                                        </div>
                                        <p className={`text-xl ${theme.text} font-medium`}>No schedule found</p>
                                        <p className={theme.textMuted + ' mt-2'}>No classes found for the selected course, year, and semester.</p>
                                    </div>
                                </div>
                            ) : (
                                <div className="flex items-center justify-center py-24">
                                    <div className="text-center">
                                        <div className={`w-20 h-20 mx-auto mb-4 rounded-full flex items-center justify-center ${isDark ? 'bg-slate-700/50' : 'bg-slate-100'}`}>
                                            <svg className={`w-10 h-10 ${theme.textMuted}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                                            </svg>
                                        </div>
                                        <p className={`text-xl ${theme.text} font-medium`}>Select a course</p>
                                        <p className={theme.textMuted + ' mt-2'}>Please select a course to view your schedule.</p>
                                    </div>
                                </div>
                            )}
                        </>
                    )}
                </div>
            </div>

            {/* Swap Request Modal */}
            {
                showSwapModal && (
                    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
                        <div className={`${isDark ? 'bg-slate-800' : 'bg-white'} rounded-2xl shadow-2xl w-full max-w-3xl max-h-[80vh] overflow-hidden flex flex-col`}>
                            <div className={`p-6 border-b ${isDark ? 'border-slate-700' : 'border-slate-200'}`}>
                                <h2 className={`text-xl font-bold ${theme.text}`}>Request Schedule Swap</h2>
                                {selectedSchedule && (
                                    <p className={`${theme.textMuted} text-sm mt-1`}>
                                        Swapping: {getSubject(selectedSchedule.subjectId || selectedSchedule.subject_id)?.code || 'Unknown'} • {getDay(selectedSchedule)} • {formatTime12Hour(selectedSchedule.time)}
                                    </p>
                                )}
                            </div>

                            <div className="flex-1 overflow-y-auto p-6">
                                {swapError && (
                                    <div className="mb-4 p-3 bg-red-50 border border-red-200 text-red-700 rounded-lg text-sm">
                                        {swapError}
                                    </div>
                                )}
                                {swapMessage && (
                                    <div className="mb-4 p-3 bg-green-50 border border-green-200 text-green-700 rounded-lg text-sm">
                                        {swapMessage}
                                    </div>
                                )}

                                {/* Filter Controls */}
                                <div className={`mb-6 p-4 rounded-xl border ${isDark ? 'bg-slate-700/50 border-slate-600' : 'bg-slate-50 border-slate-200'}`}>
                                    <h3 className={`font-medium ${theme.text} mb-3`}>Search Filters</h3>
                                    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                                        {/* Day Filter */}
                                        <div>
                                            <label className={`block text-xs ${theme.textMuted} mb-1`}>Day</label>
                                            <select
                                                value={swapFilterDay}
                                                onChange={(e) => setSwapFilterDay(e.target.value)}
                                                className={`w-full px-3 py-2 rounded-lg text-sm ${theme.input} border focus:ring-2 focus:ring-indigo-500`}
                                            >
                                                <option value="">All Days</option>
                                                {days.map(d => (
                                                    <option key={d.id} value={d.label}>{d.label}</option>
                                                ))}
                                            </select>
                                        </div>

                                        {/* Room Filter */}
                                        <div>
                                            <label className={`block text-xs ${theme.textMuted} mb-1`}>Room</label>
                                            <select
                                                value={swapFilterRoom}
                                                onChange={(e) => setSwapFilterRoom(e.target.value)}
                                                className={`w-full px-3 py-2 rounded-lg text-sm ${theme.input} border focus:ring-2 focus:ring-indigo-500`}
                                            >
                                                <option value="">All Rooms</option>
                                                {rooms.map(r => (
                                                    <option key={r.id} value={r.id}>{r.name}</option>
                                                ))}
                                            </select>
                                        </div>

                                        {/* Start Time */}
                                        <div>
                                            <label className={`block text-xs ${theme.textMuted} mb-1`}>From</label>
                                            <input
                                                type="time"
                                                value={swapFilterStartTime}
                                                onChange={(e) => setSwapFilterStartTime(e.target.value)}
                                                className={`w-full px-3 py-2 rounded-lg text-sm ${theme.input} border focus:ring-2 focus:ring-indigo-500`}
                                            />
                                        </div>

                                        {/* End Time */}
                                        <div>
                                            <label className={`block text-xs ${theme.textMuted} mb-1`}>To</label>
                                            <input
                                                type="time"
                                                value={swapFilterEndTime}
                                                onChange={(e) => setSwapFilterEndTime(e.target.value)}
                                                className={`w-full px-3 py-2 rounded-lg text-sm ${theme.input} border focus:ring-2 focus:ring-indigo-500`}
                                            />
                                        </div>
                                    </div>
                                    <button
                                        onClick={searchWithFilters}
                                        disabled={swapSearchLoading}
                                        className="mt-3 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors text-sm font-medium disabled:opacity-50"
                                    >
                                        {swapSearchLoading ? 'Searching...' : 'Search Schedules'}
                                    </button>
                                </div>

                                {/* Timetable Display */}
                                <div className="mb-4">
                                    <h3 className={`font-medium ${theme.text} mb-2`}>Available Schedules:</h3>
                                    {swapSearchLoading ? (
                                        <div className={`text-center py-8 ${theme.textMuted}`}>
                                            <svg className="w-6 h-6 animate-spin mx-auto mb-2" fill="none" viewBox="0 0 24 24">
                                                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                                            </svg>
                                            Searching...
                                        </div>
                                    ) : swapSearchResults.length === 0 ? (
                                        <div className={`text-center py-8 ${theme.textMuted} border rounded-lg ${isDark ? 'border-slate-600' : 'border-slate-200'}`}>
                                            {selectedSchedule ? 'Click "Search Schedules" to find available slots' : 'No results found'}
                                        </div>
                                    ) : (
                                        <div className={`border rounded-xl overflow-hidden ${isDark ? 'border-slate-600' : 'border-slate-200'}`}>
                                            {/* Timetable Header */}
                                            <div className={`grid grid-cols-[auto_1fr_1fr_1fr_1fr_auto] gap-2 ${isDark ? 'bg-slate-700' : 'bg-slate-100'}`}>
                                                <div className={`p-2 text-xs font-medium ${theme.textMuted} border-r ${isDark ? 'border-slate-600' : 'border-slate-200'} text-center`}>Status</div>
                                                <div className={`p-2 text-xs font-medium ${theme.textMuted} border-r ${isDark ? 'border-slate-600' : 'border-slate-200'}`}>Time</div>
                                                <div className={`p-2 text-xs font-medium ${theme.textMuted} border-r ${isDark ? 'border-slate-600' : 'border-slate-200'}`}>Subject</div>
                                                <div className={`p-2 text-xs font-medium ${theme.textMuted} border-r ${isDark ? 'border-slate-600' : 'border-slate-200'}`}>Instructor</div>
                                                <div className={`p-2 text-xs font-medium ${theme.textMuted} border-r ${isDark ? 'border-slate-600' : 'border-slate-200'}`}>Day / Room</div>
                                                <div className={`p-2 text-xs font-medium ${theme.textMuted}`}>Action</div>
                                            </div>
                                            {/* Timetable Body */}
                                            <div className={`divide-y ${isDark ? 'divide-slate-600' : 'divide-slate-200'} max-h-64 overflow-y-auto`}>
                                                {swapSearchResults.map((schedule) => (
                                                    <div key={schedule.id} className={`border-b ${isDark ? 'border-slate-700' : 'border-slate-100'} last:border-0`}>
                                                        <div
                                                            className={`grid grid-cols-[auto_1fr_1fr_1fr_1fr_auto] gap-2 items-center ${selectedSwapTarget?.id === schedule.id
                                                                ? 'bg-indigo-100 dark:bg-indigo-900/30'
                                                                : isDark ? 'hover:bg-slate-700/50' : 'hover:bg-slate-50'
                                                                }`}
                                                        >
                                                            {/* Status Icon with Hover Tooltip */}
                                                            <div className={`p-2 flex justify-center border-r ${isDark ? 'border-slate-600' : 'border-slate-200'}`}>
                                                                {schedule.has_conflict ? (
                                                                    <div className="relative group">
                                                                        <div className="w-8 h-8 rounded-full bg-red-100 text-red-600 flex items-center justify-center cursor-help">
                                                                            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                                                                            </svg>
                                                                        </div>
                                                                        {/* Tooltip */}
                                                                        <div className="absolute left-10 top-0 z-50 hidden group-hover:block w-80">
                                                                            <div className="bg-white dark:bg-slate-800 shadow-xl rounded-xl p-3 border border-slate-200 dark:border-slate-700">
                                                                                <div className="text-xs font-bold text-slate-500 mb-2 uppercase tracking-wide">Conflict Details</div>
                                                                                <SwapConflictsDisplay conflicts={schedule.conflicts} />
                                                                            </div>
                                                                        </div>
                                                                    </div>
                                                                ) : (
                                                                    <div className="w-8 h-8 rounded-full bg-emerald-100 text-emerald-600 flex items-center justify-center" title="No conflicts detected">
                                                                        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                                                                        </svg>
                                                                    </div>
                                                                )}
                                                            </div>

                                                            <div className={`p-2 text-sm ${theme.text} border-r ${isDark ? 'border-slate-600' : 'border-slate-200'} font-mono`}>
                                                                {formatTime12Hour(schedule.time) || '—'}
                                                            </div>
                                                            <div className={`p-2 text-sm border-r ${isDark ? 'border-slate-600' : 'border-slate-200'}`}>
                                                                <span className={`font-medium ${theme.text}`}>{schedule.subject_code}</span>
                                                                <span className={`block text-xs ${theme.textMuted} truncate`}>{schedule.subject_description}</span>
                                                            </div>
                                                            <div className={`p-2 text-sm ${theme.text} border-r ${isDark ? 'border-slate-600' : 'border-slate-200'}`}>
                                                                {schedule.instructor_name || '—'}
                                                            </div>
                                                            <div className={`p-2 text-sm ${theme.textMuted} border-r ${isDark ? 'border-slate-600' : 'border-slate-200'}`}>
                                                                <span className="text-emerald-500 font-medium">{schedule.day_label}</span>
                                                                <span className="mx-1">•</span>
                                                                <span className="text-cyan-500">{schedule.room_name}</span>
                                                            </div>
                                                            <div className="p-2">
                                                                <button
                                                                    onClick={() => handleSelectSwapTarget(schedule)}
                                                                    className={`px-2 py-1 text-xs rounded ${selectedSwapTarget?.id === schedule.id
                                                                        ? 'bg-indigo-600 text-white'
                                                                        : 'bg-indigo-100 text-indigo-700 hover:bg-indigo-200'
                                                                        }`}
                                                                >
                                                                    {selectedSwapTarget?.id === schedule.id ? '✓ Selected' : 'Select'}
                                                                </button>
                                                            </div>
                                                        </div>

                                                        {/* Inline Conflict Display */}
                                                        {selectedSwapTarget?.id === schedule.id && swapConflicts.length > 0 && (
                                                            <div className={`p-3 ${isDark ? 'bg-red-900/20' : 'bg-red-50/80'}`}>
                                                                <SwapConflictsDisplay conflicts={swapConflicts} />
                                                            </div>
                                                        )}
                                                    </div>
                                                ))}
                                            </div>
                                        </div>
                                    )}
                                </div>

                                {/* Reason Input */}
                                {selectedSwapTarget && (
                                    <div className="mb-4">
                                        <label className={`block font-medium ${theme.text} mb-2`}>
                                            Reason for swap request (optional):
                                        </label>
                                        <textarea
                                            value={swapReason}
                                            onChange={(e) => setSwapReason(e.target.value)}
                                            className={`w-full px-4 py-3 rounded-xl ${theme.input} border focus:ring-2 focus:ring-indigo-500 focus:border-transparent`}
                                            rows={3}
                                            placeholder="e.g., I prefer morning classes due to commute schedule..."
                                        />
                                    </div>
                                )}
                            </div>

                            <div className={`p-6 border-t ${isDark ? 'border-slate-700' : 'border-slate-200'} flex justify-end gap-3`}>
                                <button
                                    onClick={() => setShowSwapModal(false)}
                                    className={`px-4 py-2 rounded-xl ${isDark ? 'bg-slate-700 text-white hover:bg-slate-600' : 'bg-slate-100 text-slate-700 hover:bg-slate-200'} transition-colors`}
                                >
                                    Cancel
                                </button>
                                <button
                                    onClick={handleSubmitSwapRequest}
                                    disabled={!selectedSwapTarget}
                                    className={`px-4 py-2 rounded-xl font-medium transition-colors ${selectedSwapTarget
                                        ? 'bg-indigo-600 text-white hover:bg-indigo-700'
                                        : 'bg-slate-300 text-slate-500 cursor-not-allowed'
                                        }`}
                                >
                                    Send Swap Request
                                </button>
                            </div>
                        </div>
                    </div>
                )
            }
        </>
    )
}

