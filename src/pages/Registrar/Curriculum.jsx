import { useEffect, useMemo, useState } from 'react'
import { list } from '../../store/db'
import { loadSchedule as loadScheduleApi } from '../../services/api'

export default function Curriculum() {
  const [courses, setCourses] = useState([])
  const [courseId, setCourseId] = useState('')
  const [year, setYear] = useState('1')
  const [sem, setSem] = useState('1')
  const [schedule, setSchedule] = useState([])
  const [days, setDays] = useState([])
  const [subjects, setSubjects] = useState([])
  const [rooms, setRooms] = useState([])
  const [instructors, setInstructors] = useState([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    async function loadData() {
      try {
        const [courseList, dayList, subjectList, roomList, instructorList] = await Promise.all([
          list('course'),
          list('day'),
          list('subject'),
          list('room'),
          list('instructor'),
        ])
        setCourses(courseList || [])
        setDays(dayList || [])
        setSubjects(subjectList || [])
        setRooms(roomList || [])
        setInstructors(instructorList || [])
      } catch (err) {
        console.error('Failed to load reference data for curriculum view', err)
      }
    }
    loadData()
  }, [])

  const handleLoadSchedule = async () => {
    if (!courseId) {
      setSchedule([])
      setError('Please select a course.')
      return
    }

    setIsLoading(true)
    setError('')
    try {
      const courseIdNum = Number(courseId)
      const yearNum = Number(year)
      const semNum = Number(sem)
      const result = await loadScheduleApi(courseIdNum, semNum, yearNum)
      const items = (result && Array.isArray(result.items)) ? result.items : []
      setSchedule(items)
      if (!items.length) {
        setError('No saved schedule found for this course/year/semester.')
      }
    } catch (err) {
      console.error('Failed to load schedule for curriculum view', err)
      setSchedule([])
      setError(err.message || 'Failed to load schedule from database.')
    } finally {
      setIsLoading(false)
    }
  }

  const getSubject = (id) => subjects.find((s) => s.id === id)
  const getSubjectCode = (id) => {
    const subject = getSubject(id)
    return subject?.code || `ID: ${id}`
  }
  const getSubjectDescription = (id) => {
    const subject = getSubject(id)
    return subject?.description || '—'
  }
  const getSubjectType = (id) => {
    const subject = getSubject(id)
    return subject?.type || '—'
  }
  const getSubjectUnit = (id) => {
    const subject = getSubject(id)
    return subject?.unit ?? '—'
  }
  const getRoomName = (id) => {
    if (!id) return '—'
    const room = rooms.find((r) => r.id === id)
    return room?.name || `ID: ${id}`
  }
  const getInstructorName = (id) => {
    if (!id) return '—'
    const instructor = instructors.find((i) => i.id === id)
    if (!instructor) return `ID: ${id}`
    const firstName = instructor.first_name || instructor.firstName || ''
    const lastName = instructor.last_name || instructor.lastName || ''
    const name = `${firstName} ${lastName}`.trim()
    return name || `ID: ${id}`
  }
  const getDayName = (id) => {
    if (!id) return '—'
    const day = days.find((d) => d.id === id)
    return day?.label || `ID: ${id}`
  }

  const normalizeTimeRangeString = (value) => {
    if (typeof value !== 'string') {
      return value
    }
    return value.replace(/[–—−]/g, '-')
  }

  const formatTo12Hour = (hour24, minute) => {
    const period = hour24 >= 12 ? 'PM' : 'AM'
    let hour12 = hour24 % 12
    if (hour12 === 0) hour12 = 12
    const minuteStr = minute.toString().padStart(2, '0')
    return `${hour12}:${minuteStr} ${period}`
  }

  const convert24To12 = (time24) => {
    if (!time24) return '—'
    const match = time24.match(/^(\d{1,2}):(\d{2})/)
    if (!match) return time24
    const hour24 = parseInt(match[1], 10)
    const minute = parseInt(match[2], 10)
    return formatTo12Hour(hour24, minute)
  }

  const formatTime12Hour = (timeStrRaw) => {
    if (!timeStrRaw) return '—'
    const timeStr = normalizeTimeRangeString(timeStrRaw)
    if (timeStr.includes('-') && /^\d+-\d+$/.test(timeStr)) {
      const [startMin, endMin] = timeStr.split('-').map(Number)
      const startHour = Math.floor(startMin / 60)
      const startMinute = startMin % 60
      const endHour = Math.floor(endMin / 60)
      const endMinute = endMin % 60
      const start12 = formatTo12Hour(startHour, startMinute)
      const end12 = formatTo12Hour(endHour, endMinute)
      return `${start12} - ${end12}`
    }
    if (timeStr.includes('-') && timeStr.includes(':')) {
      const [start, end] = timeStr.split('-')
      const start12 = convert24To12(start.trim())
      const end12 = convert24To12(end.trim())
      return `${start12} - ${end12}`
    }
    if (timeStr.includes(':')) {
      return convert24To12(timeStr.trim())
    }
    return timeStr
  }

  const formatTimeRange = (slot) => {
    if (slot.start_min != null && slot.end_min != null) {
      const startHour = Math.floor(slot.start_min / 60)
      const startMinute = slot.start_min % 60
      const endHour = Math.floor(slot.end_min / 60)
      const endMinute = slot.end_min % 60
      const start12 = formatTo12Hour(startHour, startMinute)
      const end12 = formatTo12Hour(endHour, endMinute)
      return `${start12} - ${end12}`
    }
    const timeStrRaw = slot.time || slot.time_label || slot.start_time
    const timeStr = normalizeTimeRangeString(timeStrRaw)
    if (timeStr) {
      return formatTime12Hour(timeStr)
    }
    return '—'
  }

  const filteredSchedule = useMemo(() => {
    if (!schedule || schedule.length === 0) return []
    const selectedYear = Number(year)
    const selectedSem = Number(sem)
    return schedule.filter((item) => {
      const itemYear = Number(item.year)
      const itemSem = Number(item.semester)
      return itemYear === selectedYear && itemSem === selectedSem
    })
  }, [schedule, year, sem])

  const expandedSchedule = useMemo(() => {
    if (!filteredSchedule || filteredSchedule.length === 0) {
      return {}
    }

    const dayLabelById = {}
    days.forEach((d) => {
      if (d && d.id != null) {
        dayLabelById[d.id] = d.label
      }
    })

    const dayOrder = { M: 0, T: 1, W: 2, TH: 3, F: 4, S: 5 }
    const grouped = {}
    filteredSchedule.forEach((item) => {
      const subjectKey = item.subject_id || item.subjectId || ''
      const instructorKey = item.instructor_id || item.instructorId || ''
      const roomKey = item.room_id || item.roomId || ''
      const timeKey = item.time || item.time_label || item.start_time || ''
      const blockKey = item.block || item._blockLabel || ''
      const groupKey = `${subjectKey}|${instructorKey}|${roomKey}|${timeKey}|${blockKey}`
      if (!grouped[groupKey]) {
        grouped[groupKey] = {
          ...item,
          _dayIds: [],
        }
      }
      const dayId = item.day_id || item.dayId
      if (dayId != null && !grouped[groupKey]._dayIds.includes(dayId)) {
        grouped[groupKey]._dayIds.push(dayId)
      }
    })

    const baseRows = Object.values(grouped).map((group) => {
      const dayIds = group._dayIds || []
      const labels = dayIds
        .map((id) => dayLabelById[id])
        .filter(Boolean)
        .sort((a, b) => {
          const aIdx = dayOrder[a] ?? 99
          const bIdx = dayOrder[b] ?? 99
          return aIdx - bIdx
        })

      let combinedDays = ''
      if (labels.length === 2) {
        const [d1, d2] = labels
        if ((d1 === 'M' && d2 === 'W') || (d1 === 'W' && d2 === 'M')) {
          combinedDays = 'MW'
        } else if (
          (d1 === 'T' && d2 === 'TH') ||
          (d1 === 'TH' && d2 === 'T')
        ) {
          combinedDays = 'TTH'
        } else {
          combinedDays = labels.join('')
        }
      } else {
        combinedDays = labels.join('')
      }

      const { _dayIds, ...rest } = group
      return {
        ...rest,
        day_id: dayIds[0] ?? group.day_id ?? group.dayId ?? null,
        _combinedDaysLabel: combinedDays || (labels[0] || '—'),
      }
    })

    const byBlock = {}
    baseRows.forEach((item) => {
      const rawBlock = item.block || item._blockLabel || null
      let blockLetter = ''
      if (typeof rawBlock === 'string' && rawBlock.trim().length > 0) {
        blockLetter = rawBlock.trim()
      }
      const displayLabel =
        blockLetter && blockLetter.length > 0
          ? `Block ${blockLetter}`
          : 'Block A'
      let blockNumber = 1
      if (blockLetter && blockLetter.length === 1) {
        const code = blockLetter.toUpperCase().charCodeAt(0) - 64
        if (code > 0) blockNumber = code
      }
      if (!byBlock[displayLabel]) {
        byBlock[displayLabel] = []
      }
      byBlock[displayLabel].push({
        ...item,
        _blockNumber: blockNumber,
        _blockLabel: displayLabel,
      })
    })
    return byBlock
  }, [filteredSchedule, days])

  const renderScheduleRow = (slot, idx) => {
    const subjectId = slot.subject_id || slot.subjectId
    const subjectCode = getSubjectCode(subjectId)
    const subjectDescription = getSubjectDescription(subjectId)
    const subjectType = getSubjectType(subjectId)
    const subjectUnit = getSubjectUnit(subjectId)
    const dayId = slot.day_id || slot.dayId
    const dayLabel = slot._combinedDaysLabel || getDayName(dayId)
    const timeLabel = formatTimeRange(slot)
    const roomId = slot.room_id || slot.roomId
    const roomLabel = getRoomName(roomId)
    const instructorId = slot.instructor_id || slot.instructorId
    const instructorLabel = getInstructorName(instructorId)
    const blockNum = slot._blockNumber || 1
    const uniqueKey = `${slot.subject_id || slot.room_id || idx}-${idx}-${blockNum}`
    return (
      <tr key={uniqueKey}>
        <td className="px-4 py-2 text-sm text-gray-700">{subjectCode}</td>
        <td className="px-4 py-2 text-sm text-gray-700">{subjectDescription}</td>
        <td className="px-4 py-2 text-sm text-gray-700">{subjectType}</td>
        <td className="px-4 py-2 text-sm text-gray-700">{subjectUnit}</td>
        <td className="px-4 py-2 text-sm text-gray-700">{dayLabel}</td>
        <td className="px-4 py-2 text-sm text-gray-700">{timeLabel}</td>
        <td className="px-4 py-2 text-sm text-gray-700">{roomLabel}</td>
        <td className="px-4 py-2 text-sm text-gray-700">{instructorLabel}</td>
      </tr>
    )
  }

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <h1 className="text-navy text-3xl font-semibold mb-4">Curriculum Timetable</h1>
      <div className="flex flex-wrap items-center gap-4 mb-4">
        <select className="px-3 pr-12 py-2 rounded border" value={courseId} onChange={(e) => setCourseId(e.target.value)}>
          <option value="">Select Course</option>
          {courses.map((c) => (
            <option key={c.id} value={c.id}>
              {c.code} — {c.description}
            </option>
          ))}
        </select>
        <select className="px-3 pr-12 py-2 rounded border" value={year} onChange={(e) => setYear(e.target.value)}>
          <option value="1">1st Year</option>
          <option value="2">2nd Year</option>
          <option value="3">3rd Year</option>
          <option value="4">4th Year</option>
        </select>
        <select className="px-3 pr-12 py-2 rounded border" value={sem} onChange={(e) => setSem(e.target.value)}>
          <option value="1">1st Sem</option>
          <option value="2">2nd Sem</option>
        </select>
        <div className="ml-auto flex items-center gap-2">
          <button
            className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-royal text-white shadow hover:opacity-95 disabled:opacity-60 disabled:cursor-not-allowed"
            onClick={handleLoadSchedule}
            disabled={isLoading || !courseId}
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 24 24"
              fill="currentColor"
              className="w-4 h-4"
            >
              <path d="M5 20h14v-2H5v2zM11 4h2v8h3l-4 4-4-4h3V4z" />
            </svg>
            <span>{isLoading ? 'Loading…' : 'Load Schedule'}</span>
          </button>
        </div>
      </div>

      {error && (
        <p className="mt-2 text-sm text-red-600 bg-red-50 border border-red-100 rounded px-3 py-2">{error}</p>
      )}

      {Object.keys(expandedSchedule).length > 0 && (
        <div className="mt-6">
          {Object.keys(expandedSchedule)
            .sort()
            .map((blockLabel) => (
              <div key={blockLabel} className="mb-6">
                <h3 className="text-md font-semibold mb-2 text-gray-700">{blockLabel}</h3>
                <div className="overflow-x-auto border border-gray-200 rounded">
                  <table className="min-w-full divide-y divide-gray-200">
                    <thead className="bg-gray-50">
                      <tr>
                        <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Code</th>
                        <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Descriptive Title</th>
                        <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Type</th>
                        <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Unit</th>
                        <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Days</th>
                        <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Time</th>
                        <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Room</th>
                        <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Instructor</th>
                      </tr>
                    </thead>
                    <tbody className="bg-white divide-y divide-gray-200">
                      {expandedSchedule[blockLabel].map(renderScheduleRow)}
                    </tbody>
                  </table>
                </div>
              </div>
            ))}
        </div>
      )}

      {!isLoading && Object.keys(expandedSchedule).length === 0 && !error && (
        <p className="mt-6 text-sm text-gray-500">Load a saved schedule to view the curriculum timetable.</p>
      )}
    </div>
  )
}
