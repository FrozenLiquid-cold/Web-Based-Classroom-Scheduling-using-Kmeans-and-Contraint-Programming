import { useState, useEffect, useMemo } from 'react'
import { getRoomSchedule, list } from '../../services/api'
import { computeDefaultSY } from '../../components/SchoolYearSelector'

// Master time slots from 7:30 AM to 7:00 PM (based on registrar time blocks)
const MASTER_TIME_SLOTS = [
    { label: "7:30 AM – 9:00 AM", start: 450, end: 540 },
    { label: "9:00 AM – 10:30 AM", start: 540, end: 630 },
    { label: "10:30 AM – 12:00 PM", start: 630, end: 720 },
    { label: "1:00 PM – 2:30 PM", start: 780, end: 870 },
    { label: "2:30 PM – 4:00 PM", start: 870, end: 960 },
    { label: "4:00 PM – 5:30 PM", start: 960, end: 1050 },
    { label: "5:30 PM – 7:00 PM", start: 1050, end: 1140 },
]

export default function RoomSchedulePanel() {
    const [days, setDays] = useState([])
    const [rooms, setRooms] = useState([])
    const [buildings, setBuildings] = useState([])
    const [departments, setDepartments] = useState([])
    const [loading, setLoading] = useState(true)

    // Filters
    const [semester, setSemester] = useState('1')
    const [schoolYear, setSchoolYear] = useState(() => localStorage.getItem('jrmsu.schoolYear') || computeDefaultSY())
    const [departmentId, setDepartmentId] = useState('')
    const [selectedDay, setSelectedDay] = useState('')
    const [dayPattern, setDayPattern] = useState('MW')
    const [selectedRoom, setSelectedRoom] = useState('')

    const [scheduleData, setScheduleData] = useState([])
    const [fetchingSchedule, setFetchingSchedule] = useState(false)

    // Load initial data (days, rooms)
    useEffect(() => {
        const loadMetadata = async () => {
            try {
                const [d, r, b, dept] = await Promise.all([
                    list('day'),
                    list('room'),
                    list('building'),
                    list('college'),
                ])
                setDays(d)
                setRooms(r)
                setBuildings(b || [])
                setDepartments(dept || [])
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

    // Filter rooms by department (college -> building -> room)
    const filteredRooms = useMemo(() => {
        if (!departmentId) return rooms
        const deptBuildingIds = new Set(
            buildings
                .filter(b => String(b.college_id) === String(departmentId) || b.is_shared)
                .map(b => Number(b.id))
        )
        return rooms.filter(r => {
            // Include rooms with no building (accessible to all)
            if (!r.building_id) return true
            return deptBuildingIds.has(Number(r.building_id))
        })
    }, [rooms, buildings, departmentId])

    // Reset selected room when department changes
    useEffect(() => {
        if (filteredRooms.length > 0 && !filteredRooms.find(r => String(r.id) === String(selectedRoom))) {
            setSelectedRoom(filteredRooms[0].id)
        }
    }, [filteredRooms])

    // Build day label -> id lookup
    const dayLabelToId = useMemo(() => {
        const map = {}
        days.forEach(d => { map[d.label.toUpperCase()] = d.id })
        return map
    }, [days])

    // Day pattern definitions
    const DAY_PATTERNS = [
        { key: 'ALL', label: 'All Days', dayLabels: [] },
        { key: 'MW', label: 'M-W', dayLabels: ['M', 'W'] },
        { key: 'TTH', label: 'T-TH', dayLabels: ['T', 'TH'] },
        { key: 'F', label: 'F', dayLabels: ['F'] },
        { key: 'SAT', label: 'SAT', dayLabels: ['SAT', 'S'] },
        { key: 'SUN', label: 'SUN', dayLabels: ['SUN'] },
    ]

    // Get day IDs for the selected pattern
    const patternDayIds = useMemo(() => {
        if (dayPattern === 'ALL') return null // null = all days
        const pattern = DAY_PATTERNS.find(p => p.key === dayPattern)
        if (!pattern) return null
        return new Set(pattern.dayLabels.map(l => dayLabelToId[l]).filter(Boolean))
    }, [dayPattern, dayLabelToId])

    // Fetch schedule when filters change (always fetch all days, filter client-side)
    useEffect(() => {
        if (!selectedRoom || !semester) return

        const fetchSchedule = async () => {
            setFetchingSchedule(true)
            try {
                const data = await getRoomSchedule(selectedRoom, semester, null, schoolYear || null)
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
    }, [selectedRoom, semester, schoolYear])

    // Robust time parser using Regex
    const parseTimeRange = (timeStr) => {
        if (!timeStr) return { start: 0, end: 0 };

        // Match two times separated by hyphen, en-dash, or em-dash
        // Groups: 1=H1, 2=M1, 3=AM/PM1, 4=H2, 5=M2, 6=AM/PM2
        const regex = /(\d{1,2})[:.](\d{2})\s*(AM|PM)?\s*[-–—]\s*(\d{1,2})[:.](\d{2})\s*(AM|PM)?/i;
        const match = timeStr.match(regex);

        if (!match) {
            // Fallback for simple formats or log error
            console.warn("Invalid time format:", timeStr);
            return { start: 0, end: 0 };
        }

        const toMinutes = (hStr, mStr, pStr) => {
            let h = parseInt(hStr);
            const m = parseInt(mStr);
            const p = pStr ? pStr.toUpperCase() : null;

            // Heuristic for missing AM/PM: 
            // 7-11 is AM, 12 is PM, 1-6 is PM (unless specifically AM)
            // This is loose but prevents crashes

            if (p === 'PM' && h !== 12) h += 12;
            if (p === 'AM' && h === 12) h = 0;

            // If no period, assume business hours (7-6) logic? 
            // Better to assume AM if < 7, PM if < 7? No, strictly 12h leads to issues.
            // Let's rely on standard fallback if p is null: existing logic was h

            return h * 60 + m;
        };

        // Determine implicit AM/PM if missing
        // If first has no period, inherit from second? (e.g. 7:30 - 9:00 AM)
        let p1 = match[3];
        let p2 = match[6];

        // Convert
        const start = toMinutes(match[1], match[2], p1);
        let end = toMinutes(match[4], match[5], p2);

        // Fix for "1:00" interpreted as AM when it should be PM (if start is > end)
        // e.g. 11:30 - 1:00. 11:30=690, 1:00=60. 690 > 60. End must be PM.
        if (end < start) {
            end += 12 * 60;
        }

        return { start, end };
    };

    // Convert minutes back to "7:30 AM" format
    const minutesToTime = (mins) => {
        const h = Math.floor(mins / 60);
        const m = mins % 60;
        const period = h >= 12 ? 'PM' : 'AM';
        const h12 = h % 12 || 12;
        const mStr = m.toString().padStart(2, '0');
        return `${h12}:${mStr} ${period}`;
    }

    // Build smart timeline with Error Boundary
    const fullDayGrid = useMemo(() => {
        if (!scheduleData) return [];

        try {
            const START_OF_DAY = 7 * 60 + 30; // 7:30 AM
            const END_OF_DAY = 19 * 60;  // 7:00 PM

            const formatRange = (s, e) => `${minutesToTime(s)} – ${minutesToTime(e)}`;
            const schedulesByDay = {};
            days.forEach(d => { schedulesByDay[d.id] = [] });

            scheduleData.forEach(s => {
                if (!schedulesByDay[s.day_id]) schedulesByDay[s.day_id] = [];
                const range = parseTimeRange(s.time);
                // Filter invalid ranges to prevent layout breaking
                if (range.start > 0 || range.end > 0) {
                    schedulesByDay[s.day_id].push({ ...s, _start: range.start, _end: range.end });
                }
            });

            // Checkpoints for standard slots
            const SLOT_BOUNDARIES = [540, 630, 720, 780, 870, 960, 1050, 1140];

            const LUNCH_START = 720; // 12:00 PM
            const LUNCH_END = 780;   // 1:00 PM

            const pushVacantSlots = (timeline, start, end, day) => {
                if (start >= end) return;
                const breaks = SLOT_BOUNDARIES.filter(b => b > start && b < end);
                let current = start;
                const pushSlot = (from, to) => {
                    const isBreak = from >= LUNCH_START && to <= LUNCH_END;
                    timeline.push({
                        isVacant: true,
                        isBreak,
                        day_label: day.label,
                        time: formatRange(from, to),
                        key: `vacant-${day.id}-${from}`
                    });
                };
                breaks.forEach(b => {
                    pushSlot(current, b);
                    current = b;
                });
                if (current < end) {
                    pushSlot(current, end);
                }
            }

            let timeline = [];
            const daysToProcess = patternDayIds
                ? days.filter(d => patternDayIds.has(d.id))
                : days;

            // Check if selected room is in a shared building (GYM, FIELD, etc.)
            const selectedRoomObj = rooms.find(r => String(r.id) === String(selectedRoom));
            const selectedBuildingObj = selectedRoomObj?.building_id
                ? buildings.find(b => Number(b.id) === Number(selectedRoomObj.building_id))
                : null;
            const isSharedRoom = selectedBuildingObj?.is_shared || false;

            // Shared subjects that can legitimately overlap in shared venues
            const SHARED_SUBJECT_KEYWORDS = ['PE', 'NSTP', 'PATHFIT', 'CWTS', 'LTS', 'ROTC'];
            const isSharedSubject = (code) => {
                if (!code) return false;
                const upper = code.toUpperCase();
                return SHARED_SUBJECT_KEYWORDS.some(kw => upper.startsWith(kw) || upper.includes(kw));
            };

            // Check if this is a grouped multi-day pattern (MW, TTH)
            const currentPattern = DAY_PATTERNS.find(p => p.key === dayPattern);
            const isGroupedPattern = currentPattern && currentPattern.dayLabels.length > 1;

            if (isGroupedPattern) {
                // ── MERGED TIMELINE for MW / TTH ──
                // Collect all schedules with day info
                const allDayScheds = [];
                daysToProcess.forEach(day => {
                    (schedulesByDay[day.id] || []).forEach(s => {
                        allDayScheds.push({ ...s, _dayLabel: day.label, _dayId: day.id });
                    });
                });

                // Group identical schedules across days
                const mergeGroups = {};
                allDayScheds.forEach(s => {
                    const key = `${s._start}-${s._end}-${s.subject_code || ''}-${s.instructor_name || ''}-${s.block || ''}`;
                    if (!mergeGroups[key]) {
                        mergeGroups[key] = { sched: s, days: [s._dayLabel], ids: [s.id] };
                    } else {
                        if (!mergeGroups[key].days.includes(s._dayLabel)) {
                            mergeGroups[key].days.push(s._dayLabel);
                        }
                        mergeGroups[key].ids.push(s.id);
                    }
                });

                // Canonical day order for consistent labels (M/W not W/M)
                const DAY_ORDER = { 'M': 0, 'T': 1, 'W': 2, 'TH': 3, 'F': 4, 'SAT': 5, 'S': 5, 'SUN': 6 };
                const sortDays = (arr) => [...arr].sort((a, b) => (DAY_ORDER[a] ?? 99) - (DAY_ORDER[b] ?? 99));

                // Convert to flat list with merged day labels
                const patternLabel = sortDays(daysToProcess.map(d => d.label)).join('/');
                const mergedScheds = Object.values(mergeGroups).map(g => ({
                    ...g.sched,
                    day_label: g.days.length === daysToProcess.length ? patternLabel : sortDays(g.days).join('/'),
                    _mergedKey: g.ids.join('-'),
                }));

                // Sort by start time, then by subject
                mergedScheds.sort((a, b) => a._start - b._start || (a.subject_code || '').localeCompare(b.subject_code || ''));

                // Build single timeline
                const dummyDay = { label: '', id: 'merged' };
                let cursor = START_OF_DAY;
                mergedScheds.forEach(sched => {
                    if (sched._start > cursor) {
                        pushVacantSlots(timeline, cursor, sched._start, dummyDay);
                    }

                    let isConflict = sched._start < cursor;
                    if (isConflict && isSharedRoom && isSharedSubject(sched.subject_code)) {
                        isConflict = false;
                    }

                    timeline.push({
                        ...sched,
                        isVacant: false,
                        isConflict,
                        isSharedSlot: isSharedRoom && isSharedSubject(sched.subject_code),
                        key: `sched-${sched._mergedKey}`
                    });

                    cursor = Math.max(cursor, sched._end);
                });

                if (cursor < END_OF_DAY) {
                    pushVacantSlots(timeline, cursor, END_OF_DAY, dummyDay);
                }
            } else {
                // ── SINGLE DAY timeline (F, SAT, SUN, ALL) ──
                daysToProcess.forEach(day => {
                    const dayScheds = schedulesByDay[day.id] || [];
                    dayScheds.sort((a, b) => a._start - b._start);

                    let cursor = START_OF_DAY;

                    dayScheds.forEach((sched) => {
                        if (sched._start > cursor) {
                            pushVacantSlots(timeline, cursor, sched._start, day);
                        }

                        let isConflict = sched._start < cursor;
                        if (isConflict && isSharedRoom && isSharedSubject(sched.subject_code)) {
                            isConflict = false;
                        }

                        timeline.push({
                            ...sched,
                            isVacant: false,
                            isConflict: isConflict,
                            isSharedSlot: isSharedRoom && isSharedSubject(sched.subject_code),
                            key: `sched-${sched.id}`
                        });

                        cursor = Math.max(cursor, sched._end);
                    });

                    if (cursor < END_OF_DAY) {
                        pushVacantSlots(timeline, cursor, END_OF_DAY, day);
                    }
                });
            }

            return timeline;

        } catch (err) {
            console.error("Critical error building timeline:", err);
            return []; // Prevent page crash
        }
    }, [scheduleData, days, patternDayIds]);

    // Helper to format time robustly
    const formatTime = (timeStr) => {
        if (!timeStr) return '—'

        // Check if the string already contains AM/PM indicators
        const hasAmPm = /AM|PM/i.test(timeStr)

        const timePattern = /(\d{1,2}):(\d{2})\s*(AM|PM)?/gi
        const matches = [...timeStr.matchAll(timePattern)]
        if (matches.length === 0) return timeStr

        const to12Hour = (hour, minute, period) => {
            let h = parseInt(hour)
            let explicitPeriod = period ? period.toUpperCase() : null

            if (!explicitPeriod && !hasAmPm) {
                // School hours heuristic: 7-11 = AM, 12 = PM, 1-6 = PM
                if (h >= 7 && h <= 11) explicitPeriod = 'AM'
                else if (h === 12) explicitPeriod = 'PM'
                else if (h >= 1 && h <= 6) explicitPeriod = 'PM'
                else if (h >= 13) { explicitPeriod = h >= 12 ? 'PM' : 'AM' }
            }

            // Convert 24h to 12h if needed
            if (h >= 13) {
                explicitPeriod = 'PM'
                h -= 12
            } else if (h === 0) {
                h = 12
                explicitPeriod = 'AM'
            }

            const ampm = explicitPeriod || (h >= 7 && h <= 11 ? 'AM' : 'PM')
            const h12 = h || 12
            return `${h12}:${minute} ${ampm}`
        }

        if (matches.length >= 2) {
            return `${to12Hour(matches[0][1], matches[0][2], matches[0][3])} – ${to12Hour(matches[1][1], matches[1][2], matches[1][3])}`
        }
        return to12Hour(matches[0][1], matches[0][2], matches[0][3])
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
            {/* Filters */}
            <div className="bg-white/80 backdrop-blur-xl p-6 rounded-2xl shadow-sm border border-slate-200 grid grid-cols-1 md:grid-cols-5 gap-6">
                <div>
                    <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">School Year</label>
                    <select
                        value={schoolYear}
                        onChange={e => setSchoolYear(e.target.value)}
                        className="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-blue-500 focus:bg-white transition-all font-medium text-slate-700"
                    >
                        {(() => {
                            const now = new Date();
                            const currentYear = now.getFullYear();
                            const opts = [];
                            for (let start = currentYear + 1; start >= 2020; start--) {
                                const sy = `${start}-${start + 1}`;
                                opts.push(<option key={sy} value={sy}>SY {sy}</option>);
                            }
                            return opts;
                        })()}
                    </select>
                </div>

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
                    <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">Department</label>
                    <select
                        value={departmentId}
                        onChange={e => setDepartmentId(e.target.value)}
                        className="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-blue-500 focus:bg-white transition-all font-medium text-slate-700"
                    >
                        <option value="">All Departments</option>
                        {departments.map(d => (
                            <option key={d.id} value={d.id}>{d.code || d.name}</option>
                        ))}
                    </select>
                </div>

                <div>
                    <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">Day Pattern</label>
                    <select
                        value={dayPattern}
                        onChange={e => setDayPattern(e.target.value)}
                        className="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-blue-500 focus:bg-white transition-all font-medium text-slate-700"
                    >
                        {DAY_PATTERNS.map(p => (
                            <option key={p.key} value={p.key}>{p.label}</option>
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
                        {filteredRooms.map(r => (
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
                        <p className="text-sm text-slate-500 mt-1">7:30 AM – 7:00 PM time slots</p>
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
                                    {(dayPattern === 'ALL' || dayPattern === 'MW' || dayPattern === 'TTH') && <th className="text-left px-6 py-4 text-slate-500 font-semibold text-xs uppercase tracking-wider">Day</th>}
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
                                    <tr key={slot.key} className={`transition-colors ${slot.isBreak
                                        ? 'bg-amber-50/50'
                                        : slot.isVacant
                                            ? 'bg-green-50/30 hover:bg-green-50/50'
                                            : slot.isConflict
                                                ? 'bg-red-50 border-l-4 border-red-500'
                                                : slot.isSharedSlot
                                                    ? 'bg-blue-50/30 hover:bg-blue-50/50'
                                                    : 'hover:bg-slate-50'
                                        }`}>
                                        <td className="px-6 py-4 text-slate-400 font-mono text-sm">{idx + 1}</td>
                                        <td className="px-6 py-4 text-slate-600 font-mono text-sm font-medium">
                                            {slot.isVacant ? slot.time : formatTime(slot.time)}
                                        </td>
                                        {(dayPattern === 'ALL' || dayPattern === 'MW' || dayPattern === 'TTH') && (
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
                                            {slot.isConflict && <span className="ml-2 px-1.5 py-0.5 bg-red-100 text-red-700 text-[10px] font-bold rounded uppercase">Double Booked</span>}
                                        </td>
                                        <td className="px-6 py-4 text-sm max-w-xs truncate" title={slot.subject_description}>
                                            <span className={slot.isVacant ? 'text-slate-400 italic' : 'text-slate-600'}>
                                                {slot.isBreak ? '🍽️ Lunch Break' : slot.isVacant ? 'Available for schedule' : (slot.subject_description || '—')}
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
                                            {slot.isBreak ? (
                                                <div className="flex items-center gap-1.5">
                                                    <span className="relative flex h-2.5 w-2.5">
                                                        <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-amber-400"></span>
                                                    </span>
                                                    <span className="text-xs font-medium text-amber-600">Break</span>
                                                </div>
                                            ) : slot.isVacant ? (
                                                <div className="flex items-center gap-1.5">
                                                    <span className="relative flex h-2.5 w-2.5">
                                                        <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-500"></span>
                                                    </span>
                                                    <span className="text-xs font-medium text-emerald-600">Vacant</span>
                                                </div>
                                            ) : slot.isSharedSlot ? (
                                                <div className="flex items-center gap-1.5">
                                                    <span className="relative flex h-2.5 w-2.5">
                                                        <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-blue-500"></span>
                                                    </span>
                                                    <span className="text-xs font-medium text-blue-600">Shared</span>
                                                </div>
                                            ) : slot.isConflict ? (
                                                <div className="flex items-center gap-1.5">
                                                    <span className="relative flex h-2.5 w-2.5">
                                                        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75"></span>
                                                        <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-red-600"></span>
                                                    </span>
                                                    <span className="text-xs font-bold text-red-700">CONFLICT</span>
                                                </div>
                                            ) : (
                                                <div className="flex items-center gap-1.5">
                                                    <span className="relative flex h-2.5 w-2.5">
                                                        <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-orange-500"></span>
                                                    </span>
                                                    <span className="text-xs font-medium text-orange-600">Occupied</span>
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
