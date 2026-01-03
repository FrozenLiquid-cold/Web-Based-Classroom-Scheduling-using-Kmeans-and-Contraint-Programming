import { useEffect, useMemo, useState, useRef } from 'react'
import { list, upsert, remove } from '../../store/db'

export default function Subject() {
	const [items, setItems] = useState([])
	const [courses, setCourses] = useState([])
	const [q, setQ] = useState('')
	const [show, setShow] = useState(false)
	const [editing, setEditing] = useState(null)
	const [code, setCode] = useState('')
	const [description, setDescription] = useState('')
	const [type, setType] = useState('LEC')
	const [unit, setUnit] = useState('3')
	const [yearLevel, setYearLevel] = useState('')
	const [semester, setSemester] = useState('')
	const [courseId, setCourseId] = useState('')
	const [priority, setPriority] = useState('unmarked')
	const [error, setError] = useState('')
	const [entries, setEntries] = useState(10)
	const [processing, setProcessing] = useState(false)
	
	// Prevent duplicate loads from React StrictMode
	const dataLoadingRef = useRef(false);
	const dataLoadedRef = useRef(false);

	async function load(force = false){ 
		// Skip if already loaded or currently loading
		if (!force && (dataLoadedRef.current || dataLoadingRef.current)) {
			return;
		}
		
		dataLoadingRef.current = true;
		try {
			const [subjectsData, coursesData] = await Promise.all([
				list('subject'),
				list('course')
			])
			setItems(subjectsData)
			setCourses(coursesData)
			dataLoadedRef.current = true;
		} catch (error) {
			console.error('Error loading data:', error);
		} finally {
			dataLoadingRef.current = false;
		}
	}
	useEffect(()=>{ load() },[])

	const filtered = useMemo(()=>{
		const query = q.toLowerCase()
		const result = items.filter(i=> (i.code+' '+i.description).toLowerCase().includes(query))
		const rank = (it) => {
			const v = (it.is_major ?? it.isMajor)
			if (v === null || v === undefined) return 0
			if (v === true) return 1
			return 2
		}
		return [...result].sort((a, b) => {
			const ra = rank(a)
			const rb = rank(b)
			if (ra !== rb) return ra - rb
			return String(a.code || '').localeCompare(String(b.code || ''))
		})
	},[items,q])

	const shown = useMemo(()=>{
		const n = Math.max(0, Number(entries)||0)
		return filtered.slice(0, n || filtered.length)
	}, [filtered, entries])

	function openAdd(){
		setEditing(null)
		setCode('')
		setDescription('')
		setType('LEC')
		setUnit('3')
		setYearLevel('')
		setSemester('')
		setCourseId('')
		setPriority('')
		setError('')
		setShow(true)
	}

	function openEdit(it){
		setEditing(it)
		setCode(it.code)
		setDescription(it.description)
		setType(it.type||'LEC')
		setUnit(String(it.unit||'3'))
		setYearLevel(String((it.year_level ?? it.yearLevel) ?? ''))
		setSemester(String((it.semester ?? it.semesterValue ?? it.sem) ?? ''))
		setCourseId(it.course_id || it.courseId || '')
		{
			const v = (it.is_major ?? it.isMajor)
			if (v === true) setPriority('major')
			else if (v === false) setPriority('minor')
			else setPriority('unmarked')
		}
		setError('')
		setShow(true)
	}

	async function onSave(e){
		e.preventDefault()
		if (processing) return
		if (!code.trim() || !description.trim() || !unit) { setError('All fields are required'); return }
		if (!yearLevel || !semester) { setError('Year level and semester are required'); return }
		if (!['1','2','3','4'].includes(String(yearLevel))) { setError('Year level must be 1, 2, 3, or 4'); return }
		if (!['1','2'].includes(String(semester))) { setError('Semester must be 1 or 2'); return }
		if (!editing && priority !== 'major' && priority !== 'minor') { setError('Priority (Major/Minor) is required'); return }
		const currentCourseId = courseId ? parseInt(courseId) : null
		const duplicate = items.find(i=> {
			const existingCode = String(i.code || '').trim().toLowerCase()
			const existingType = String(i.type || '').trim().toUpperCase()
			const existingYear = Number.isFinite(Number(i.year_level ?? i.yearLevel)) ? Number(i.year_level ?? i.yearLevel) : null
			const existingSem = Number.isFinite(Number(i.semester ?? i.semesterValue ?? i.sem)) ? Number(i.semester ?? i.semesterValue ?? i.sem) : null
			const rawExistingCourseId = (i.course_id ?? i.courseId) ?? null
			const existingCourseId = (rawExistingCourseId === null || rawExistingCourseId === undefined)
				? null
				: (Number.isFinite(Number(rawExistingCourseId)) ? Number(rawExistingCourseId) : null)
			return (
				existingCode === code.trim().toLowerCase() &&
				existingType === String(type || '').trim().toUpperCase() &&
				existingCourseId === currentCourseId &&
				existingYear === Number(yearLevel) &&
				existingSem === Number(semester) &&
				i.id !== (editing?.id)
			)
		})
		if (duplicate) { setError('Code must be unique within the same course, type, year level, and semester'); return }
		try {
			setProcessing(true)
			await upsert('subject', { 
				id: editing?.id, 
				code: code.trim(), 
				description: description.trim(), 
				type, 
				unit: Number(unit),
				year_level: Number(yearLevel),
				semester: Number(semester),
				course_id: courseId ? parseInt(courseId) : null,
				is_major: priority === 'major' ? true : priority === 'minor' ? false : null
			})
			setShow(false)
			await load(true)
		} catch (error) {
			setError(error.message || 'Failed to save')
		} finally {
			setProcessing(false)
		}
	}

	const courseName = (id) => {
		if (!id) return ''
		const course = courses.find(c => c.id === id)
		return course ? `${course.code} — ${course.description}` : ''
	}

	async function onDelete(id){
		if (processing) return
		if (!confirm('Delete this subject?')) return
		try {
			setProcessing(true)
			await remove('subject', id)
			await load(true)
		} catch (error) {
			alert(error.message || 'Failed to delete')
		} finally {
			setProcessing(false)
		}
	}

	return (
		<div>
			<div className="flex items-center justify-between mb-4">
				<h1 className="text-navy text-3xl font-semibold">SUBJECT</h1>
				<button className="px-3 py-2 rounded bg-royal text-white flex items-center gap-2 disabled:opacity-60" onClick={openAdd} disabled={processing}>
					<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-4 h-4"><path d="M11 11V5h2v6h6v2h-6v6h-2v-6H5v-2h6z"/></svg>
					<span>Add Subject</span>
				</button>
			</div>
		{/* Standardized fixed-height container for list/table area */}
		<div className="h-[520px] overflow-auto pr-1 [&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none]">
		<div className="mb-2 text-navy text-1xl font-semibold">List of Subject</div>
		<div className="flex items-center justify-between mb-3 gap-4">
			<div className="flex items-center gap-2 text-sm">
				<span>Show</span>
				<div className="flex items-stretch border border-gray-300 rounded overflow-hidden">
					<input type="number" min="1" className="w-16 px-2 outline-none text-center" value={entries} onChange={e=>setEntries(e.target.value)} />
					<div className="flex flex-col">
						<button type="button" aria-label="Increase" className="px-2 border-l border-b border-gray-300 hover:bg-gray-100" onClick={()=>setEntries(prev=>Number(prev||0)+1)}>▲</button>
						<button type="button" aria-label="Decrease" className="px-2 border-l border-gray-300 hover:bg-gray-100" onClick={()=>setEntries(prev=>Math.max(1, Number(prev||0)-1))}>▼</button>
					</div>
				</div>
				<span>entries</span>
			</div>
			<input className="w-full max-w-sm px-3 py-2 rounded-full border" placeholder="Search: Subject" value={q} onChange={e=>setQ(e.target.value)} />
		</div>
			<div className="overflow-x-auto">
				<table className="min-w-full text-sm border border-gray-400">
					<thead>
						<tr className="bg-navy text-white border-b-2 border-gray-500">
							<th className="text-left px-3 py-2 border-r border-gray-300">No.</th>
							<th className="text-left px-3 py-2 border-r border-gray-300">Code</th>
							<th className="text-left px-3 py-2 border-r border-gray-300">Description</th>
							<th className="text-left px-3 py-2 border-r border-gray-300">Priority</th>
							<th className="text-left px-3 py-2 border-r border-gray-300">Year</th>
							<th className="text-left px-3 py-2 border-r border-gray-300">Sem</th>
							<th className="text-left px-3 py-2 border-r border-gray-300">Course</th>
							<th className="text-left px-3 py-2 border-r border-gray-300">Type</th>
							<th className="text-left px-3 py-2 border-r border-gray-300">Unit</th>
							<th className="text-center px-3 py-2 w-36">Action</th>
						</tr>
					</thead>
					<tbody className="divide-y divide-gray-300">
					{shown.map((it, idx)=> (
							<tr
								key={it.id}
								className={(((it.is_major ?? it.isMajor) === null) || ((it.is_major ?? it.isMajor) === undefined)) ? 'bg-yellow-100' : (idx%2? 'bg-gray-50':'')}
							>
								<td className="px-3 py-2 border-r border-gray-300">{idx+1}</td>
								<td className="px-3 py-2 border-r border-gray-300">{it.code}</td>
								<td className="px-3 py-2 border-r border-gray-300">{it.description}</td>
								<td className="px-3 py-2 border-r border-gray-300">
									{((it.is_major ?? it.isMajor) === true) && (
										<span className="inline-flex px-2 py-1 rounded-full text-xs font-semibold bg-green-100 text-green-800">MAJOR</span>
									)}
									{((it.is_major ?? it.isMajor) === false) && (
										<span className="inline-flex px-2 py-1 rounded-full text-xs font-semibold bg-gray-200 text-gray-800">MINOR</span>
									)}
									{(((it.is_major ?? it.isMajor) === null) || ((it.is_major ?? it.isMajor) === undefined)) && (
										<span className="inline-flex px-2 py-1 rounded-full text-xs font-semibold bg-red-100 text-red-800">UNMARKED</span>
									)}
								</td>
								<td className="px-3 py-2 border-r border-gray-300">{(it.year_level ?? it.yearLevel) ?? '-'}</td>
								<td className="px-3 py-2 border-r border-gray-300">{(it.semester ?? it.semesterValue ?? it.sem) ?? '-'}</td>
								<td className="px-3 py-2 border-r border-gray-300">{courseName(it.course_id || it.courseId) || '-'}</td>
								<td className="px-3 py-2 border-r border-gray-300">{it.type}</td>
								<td className="px-3 py-2 border-r border-gray-300">{it.unit}</td>
								<td className="px-3 py-2 space-x-3 text-center">
									<button className="inline-flex items-center justify-center w-8 h-8 rounded-full bg-blue-600 hover:opacity-90" title="Edit" onClick={()=>openEdit(it)}>
										<img src="/assets/edit.png" alt="Edit" className="w-4 h-4 object-contain" onError={(e)=>{e.currentTarget.style.display='none'}} />
									</button>
									<button className="inline-flex items-center justify-center w-8 h-8 rounded-full bg-red-600 hover:opacity-90" title="Delete" onClick={()=>onDelete(it.id)}>
										<img src="/assets/delete.png" alt="Delete" className="w-4 h-4 object-contain" onError={(e)=>{e.currentTarget.style.display='none'}} />
									</button>
								</td>
							</tr>
						))}
						{filtered.length===0 && (
							<tr className="border-t border-gray-300"><td className="px-3 py-6 text-center text-gray-500" colSpan={10}>No records</td></tr>
						)}
					</tbody>
				</table>
			</div>
		</div>

			{show && (
				<div className="fixed inset-0 bg-black/30 flex items-center justify-center p-4">
					<form onSubmit={onSave} className="w-full max-w-md bg-white rounded-xl shadow p-5 space-y-3">
						<div className="text-lg font-semibold text-navy">{editing? 'Edit Subject':'Add Subject'}</div>
						<input className="w-full px-3 py-2 rounded border" placeholder="Code" value={code} onChange={e=>setCode(e.target.value)} />
						<input className="w-full px-3 py-2 rounded border" placeholder="Description" value={description} onChange={e=>setDescription(e.target.value)} />
						<select className="w-full px-3 py-2 rounded border" value={priority} onChange={e=>setPriority(e.target.value)}>
							{!editing && <option value="">Select Priority</option>}
							{editing && <option value="unmarked">Unmarked</option>}
							<option value="major">Major</option>
							<option value="minor">Minor</option>
						</select>
						<select className="w-full px-3 py-2 rounded border" value={yearLevel} onChange={e=>setYearLevel(e.target.value)}>
							<option value="">Select Year Level</option>
							<option value="1">1</option>
							<option value="2">2</option>
							<option value="3">3</option>
							<option value="4">4</option>
						</select>
						<select className="w-full px-3 py-2 rounded border" value={semester} onChange={e=>setSemester(e.target.value)}>
							<option value="">Select Semester</option>
							<option value="1">1</option>
							<option value="2">2</option>
						</select>
						<select className="w-full px-3 py-2 rounded border" value={courseId} onChange={e=>setCourseId(e.target.value)}>
							<option value="">Select Course (optional)</option>
							{courses.map(c=> <option key={c.id} value={c.id}>{c.code} — {c.description}</option>)}
						</select>
						<select className="w-full px-3 py-2 rounded border" value={type} onChange={e=>setType(e.target.value)}>
							<option value="LEC">LEC</option>
							<option value="LAB">LAB</option>
						</select>
						<input type="number" min="0" className="w-full px-3 py-2 rounded border" placeholder="Unit" value={unit} onChange={e=>setUnit(e.target.value)} />
						{error && <div className="text-sm text-red-600">{error}</div>}
						<div className="flex justify-end gap-2 pt-2">
							<button type="button" className="px-3 py-2 rounded border" onClick={()=>setShow(false)} disabled={processing}>Cancel</button>
							<button className="px-3 py-2 rounded bg-royal text-white disabled:opacity-60" disabled={processing}>Save</button>
						</div>
					</form>
				</div>
			)}
		</div>
	)
}

