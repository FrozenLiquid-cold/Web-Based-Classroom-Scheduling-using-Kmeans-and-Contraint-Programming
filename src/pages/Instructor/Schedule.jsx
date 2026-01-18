import { useEffect, useMemo, useState } from 'react'
import { list, getKey } from '../../store/db'
import { loadSchedule as apiLoadSchedule } from '../../services/api'

export default function Schedule() {
    const [courses, setCourses] = useState([])
    const [subjects, setSubjects] = useState([])
    const [instructors, setInstructors] = useState([])
    const [rooms, setRooms] = useState([])
    const [days, setDays] = useState([])
    const [courseId, setCourseId] = useState('')
    const [year, setYear] = useState('1')
    const [sem, setSem] = useState('1')
    const [rows, setRows] = useState([])
    const [coursesWithScheduleIds, setCoursesWithScheduleIds] = useState([])
    const [hasCheckedSchedule, setHasCheckedSchedule] = useState(false)
    const [loading, setLoading] = useState(true)
    const [isDark, setIsDark] = useState(() => {
        const saved = localStorage.getItem('jrmsu.theme')
        return saved ? saved === 'dark' : false
    })

    useEffect(() => {
        localStorage.setItem('jrmsu.theme', isDark ? 'dark' : 'light')
    }, [isDark])

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

    useEffect(() => {
        let cancelled = false
        async function findCoursesWithSchedule() {
            if (!currentInstructorId) {
                setCoursesWithScheduleIds([])
                setHasCheckedSchedule(true)
                setLoading(false)
                return
            }
            if (!courses || !courses.length) return
            setLoading(true)
            const ids = new Set()
            for (const course of courses) {
                for (const semester of [1, 2]) {
                    try {
                        const resp = await apiLoadSchedule(course.id, semester, null, currentInstructorId)
                        if (resp && resp.status === 'success' && Array.isArray(resp.items) && resp.items.length > 0) {
                            ids.add(course.id)
                            break
                        }
                    } catch (error) {
                        console.error('Error checking instructor schedule for course', course.id, error)
                    }
                }
            }
            if (cancelled) return
            const idsArray = Array.from(ids)
            setCoursesWithScheduleIds(idsArray)
            setHasCheckedSchedule(true)
            setLoading(false)
            if (!idsArray.length) {
                setCourseId('')
                setRows([])
            } else {
                setCourseId(prev => {
                    const prevNum = parseInt(prev, 10)
                    return prevNum && idsArray.includes(prevNum) ? prev : String(idsArray[0])
                })
            }
        }
        findCoursesWithSchedule()
        return () => { cancelled = true }
    }, [courses, currentInstructorId])

    const key = useMemo(() => `jrmsu.schedule.${courseId || 'none'}.${year}.${sem}`, [courseId, year, sem])

    useEffect(() => {
        async function loadSchedule() {
            if (!courseId) {
                setRows([])
                return
            }
            try {
                const saved = await getKey(key, [])
                if (saved && Array.isArray(saved)) {
                    const filtered = currentInstructorId
                        ? saved.filter(s => (s.instructorId === currentInstructorId || s.instructor_id === currentInstructorId))
                        : saved

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
                } else {
                    setRows([])
                }
            } catch (error) {
                console.error('Error loading schedule:', error)
                setRows([])
            }
        }
        loadSchedule()
    }, [key, courseId, currentInstructorId, days])

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
    const visibleCourses = hasAnySchedule ? courses.filter(c => coursesWithScheduleIds.includes(c.id)) : []

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

    return (
        <div className={`min-h-screen ${theme.bg} p-6`}>
            <div className="max-w-7xl mx-auto">
                <div className="flex flex-col md:flex-row md:items-center md:justify-between mb-8">
                    <div>
                        <h1 className={`text-3xl font-bold ${theme.text} mb-2`}>
                            📅 My <span className="bg-gradient-to-r from-blue-500 to-cyan-500 bg-clip-text text-transparent">Schedule</span>
                        </h1>
                        <p className={theme.textMuted}>View your assigned classes and teaching schedule</p>
                    </div>
                    <button
                        onClick={() => setIsDark(!isDark)}
                        className={`mt-4 md:mt-0 p-2.5 rounded-xl ${theme.input} border transition-all hover:scale-105`}
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
                                    <p className={`text-2xl font-bold ${theme.text}`}>{rows.length}</p>
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
                                                        <td className={`px-4 py-4 ${isDark ? 'text-slate-300' : 'text-slate-600'} font-mono text-sm`}>{r.time || '—'}</td>
                                                        <td className="px-4 py-4"><span className="text-cyan-500">{getRoom(r.roomId || r.room_id) || '—'}</span></td>
                                                        <td className="px-4 py-4"><span className={`px-2 py-1 rounded-lg text-xs font-medium ${isDark ? 'bg-slate-600/50 text-slate-300' : 'bg-slate-100 text-slate-600'}`}>{r.block || '—'}</span></td>
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
    )
}
