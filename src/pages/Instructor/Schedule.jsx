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

	const session = (()=>{
        try{ return JSON.parse(localStorage.getItem('jrmsu.session')||'null') }catch{ return null }
    })()

	const currentInstructorId = session?.instructorId || null

	useEffect(()=>{
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
	},[])

	useEffect(()=>{
		let cancelled = false
		async function findCoursesWithSchedule() {
			if (!currentInstructorId) {
				setCoursesWithScheduleIds([])
				setHasCheckedSchedule(true)
				return
			}
			if (!courses || !courses.length) {
				return
			}
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
			if (!idsArray.length) {
				setCourseId('')
				setRows([])
			} else {
				setCourseId(prev=>{
					const prevNum = parseInt(prev, 10)
					return prevNum && idsArray.includes(prevNum) ? prev : String(idsArray[0])
				})
			}
		}
		findCoursesWithSchedule()
		return ()=>{ cancelled = true }
	}, [courses, currentInstructorId])

	const key = useMemo(()=> `jrmsu.schedule.${courseId||'none'}.${year}.${sem}`, [courseId, year, sem])

	useEffect(()=>{
		async function loadSchedule() {
			if (!courseId) {
				setRows([])
				return
			}
			try {
				const saved = await getKey(key, [])
				if (saved && Array.isArray(saved)) {
					// Filter schedule to show only current instructor's classes
					const filtered = currentInstructorId 
						? saved.filter(s => (s.instructorId === currentInstructorId || s.instructor_id === currentInstructorId))
						: saved

					const dayLabelById = {}
					for (const d of (days || [])) {
						if (d && d.id != null) dayLabelById[d.id] = d.label
					}
					const dayOrder = { M: 0, T: 1, W: 2, TH: 3, F: 4, S: 5 }

					const grouped = {}
					for (const item of filtered) {
						const subjectKey = item.subject_id || item.subjectId || ''
						const instructorKey = item.instructor_id || item.instructorId || ''
						const roomKey = item.room_id || item.roomId || ''
						const rawTimeKey = item.time || ''
						const timeKey = typeof rawTimeKey === 'string'
							? rawTimeKey.replace(/^(M|T|W|TH|F)\s+/, '')
							: rawTimeKey
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
						const labels = dayIds
							.map(id => dayLabelById[id])
							.filter(Boolean)
							.sort((a, b) => (dayOrder[a] ?? 99) - (dayOrder[b] ?? 99))
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
						return {
							...rest,
							day_id: dayIds[0] ?? g.day_id ?? g.dayId ?? null,
							_combinedDaysLabel: combinedDays || (labels[0] || ''),
						}
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

	const getSubject = (id)=> subjects.find(s=>s.id===id)
	const getDay = (r)=> {
		const combined = r?._combinedDaysLabel
		if (combined) return combined
		const id = r?.dayId || r?.day_id
		return days.find(d=>d.id===id)?.label || ''
	}
	const getRoom = (id)=> rooms.find(r=>r.id===id)?.name || ''
	const getInst = (id)=> {
		const i = instructors.find(x=>x.id===id)
		if (!i) return ''
		const firstName = i.first_name || i.firstName || ''
		const lastName = i.last_name || i.lastName || ''
		return `${firstName} ${lastName}`.trim()
	}

	const currentInstructor = instructors.find(i => i.id === currentInstructorId)
	const instructorName = currentInstructor 
		? `${currentInstructor.first_name || currentInstructor.firstName || ''} ${currentInstructor.last_name || currentInstructor.lastName || ''}`.trim()
		: 'Unknown'

	const hasAnySchedule = hasCheckedSchedule && coursesWithScheduleIds.length > 0
	const noScheduleForInstructor = hasCheckedSchedule && currentInstructorId && !hasAnySchedule
	const visibleCourses = hasAnySchedule
		? courses.filter(c => coursesWithScheduleIds.includes(c.id))
		: []

	return (
		<div>
			<div className="flex items-center justify-between mb-4">
				<h1 className="text-navy text-3xl font-semibold">SCHEDULE</h1>
				<div />
			</div>

			{currentInstructorId && (
				<div className="mb-4 p-3 bg-royal/10 rounded-lg border border-royal/20">
					<p className="text-navy font-semibold">Viewing schedule for: <span className="text-royal">{instructorName}</span></p>
				</div>
			)}
			{noScheduleForInstructor ? (
				<div className="h-[520px] flex items-center justify-center text-gray-500">
					<div className="text-center">
						<p className="text-lg">No schedule has been assigned to you yet.</p>
						<p className="text-sm mt-2">Please contact the registrar for more information.</p>
					</div>
				</div>
			) : (
				<>
					<div className="flex flex-wrap items-center gap-3 mb-4">
						<select className="px-3 pr-12 py-2 rounded border" value={courseId} onChange={e=>setCourseId(e.target.value)}>
							<option value="">Select Course</option>
							{visibleCourses.map(c=> <option key={c.id} value={c.id}>{c.code} — {c.description}</option>)}
						</select>
						<select className="px-3 pr-12 py-2 rounded border" value={year} onChange={e=>setYear(e.target.value)}>
							<option value="1">1st Year</option>
							<option value="2">2nd Year</option>
							<option value="3">3rd Year</option>
							<option value="4">4th Year</option>
						</select>
						<select className="px-3 pr-12 py-2 rounded border" value={sem} onChange={e=>setSem(e.target.value)}>
							<option value="1">1st Sem</option>
							<option value="2">2nd Sem</option>
						</select>
					</div>

					{/* Standardized fixed-height container for list/table area */}
					{rows.length > 0 ? (
						<div className="h-[520px] overflow-auto pr-1 [&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none]">
							<div className="overflow-x-auto">
								<table className="min-w-full text-sm border border-gray-400">
									<thead>
										<tr className="bg-navy text-white border-b-2 border-gray-500">
											<th className="text-left px-3 py-2 border-r border-gray-300">No.</th>
											<th className="text-left px-3 py-2 border-r border-gray-300">Code</th>
											<th className="text-left px-3 py-2 border-r border-gray-300">Description</th>
											<th className="text-left px-3 py-2 border-r border-gray-300">Type</th>
											<th className="text-left px-3 py-2 border-r border-gray-300">Unit</th>
											<th className="text-left px-3 py-2 border-r border-gray-300">Day</th>
											<th className="text-left px-3 py-2 border-r border-gray-300">Room</th>
											<th className="text-left px-3 py-2 border-r border-gray-300">Time</th>
											<th className="text-left px-3 py-2">Instructor</th>
										</tr>
									</thead>
									<tbody className="divide-y divide-gray-300">
										{rows.map((r, idx)=>{
											const s = getSubject(r.subjectId || r.subject_id) || {}
											return (
												<tr key={idx} className={idx%2? 'bg-gray-50':''}>
													<td className="px-3 py-2 border-r border-gray-300">{idx+1}</td>
													<td className="px-3 py-2 border-r border-gray-300">{s.code}</td>
													<td className="px-3 py-2 border-r border-gray-300">{s.description}</td>
													<td className="px-3 py-2 border-r border-gray-300">{s.type}</td>
													<td className="px-3 py-2 border-r border-gray-300">{s.unit}</td>
													<td className="px-3 py-2 border-r border-gray-300">{getDay(r)}</td>
													<td className="px-3 py-2 border-r border-gray-300">{getRoom(r.roomId || r.room_id)}</td>
													<td className="px-3 py-2 border-r border-gray-300">{r.time || ''}</td>
													<td className="px-3 py-2">{getInst(r.instructorId || r.instructor_id)}</td>
												</tr>
										)
									})}
								</tbody>
							</table>
						</div>
					</div>
					) : courseId ? (
						<div className="h-[520px] flex items-center justify-center text-gray-500">
							<div className="text-center">
								<p className="text-lg">No schedule found for the selected course, year, and semester.</p>
								<p className="text-sm mt-2">Please ensure a schedule has been generated by the registrar.</p>
							</div>
						</div>
					) : (
						<div className="h-[520px] flex items-center justify-center text-gray-500">
							<p className="text-lg">Please select a course to view your schedule.</p>
						</div>
					)}
				</>
			)}
		</div>
	)
}

