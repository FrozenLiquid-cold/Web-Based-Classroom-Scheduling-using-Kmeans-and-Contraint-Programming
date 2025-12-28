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
	const [courseId, setCourseId] = useState('')
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
		return items.filter(i=> (i.code+' '+i.description).toLowerCase().includes(q.toLowerCase()))
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
		setCourseId('')
		setError('')
		setShow(true)
	}

	function openEdit(it){
		setEditing(it)
		setCode(it.code)
		setDescription(it.description)
		setType(it.type||'LEC')
		setUnit(String(it.unit||'3'))
		setCourseId(it.course_id || it.courseId || '')
		setError('')
		setShow(true)
	}

	async function onSave(e){
		e.preventDefault()
		if (processing) return
		if (!code.trim() || !description.trim() || !unit) { setError('All fields are required'); return }
		const duplicate = items.find(i=> i.code.toLowerCase() === code.trim().toLowerCase() && i.id !== (editing?.id))
		if (duplicate) { setError('Code must be unique'); return }
		try {
			setProcessing(true)
			await upsert('subject', { 
				id: editing?.id, 
				code: code.trim(), 
				description: description.trim(), 
				type, 
				unit: Number(unit),
				course_id: courseId ? parseInt(courseId) : null
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
							<th className="text-left px-3 py-2 border-r border-gray-300">Course</th>
							<th className="text-left px-3 py-2 border-r border-gray-300">Type</th>
							<th className="text-left px-3 py-2 border-r border-gray-300">Unit</th>
							<th className="text-center px-3 py-2 w-36">Action</th>
						</tr>
					</thead>
					<tbody className="divide-y divide-gray-300">
					{shown.map((it, idx)=> (
							<tr key={it.id} className={idx%2? 'bg-gray-50':''}>
								<td className="px-3 py-2 border-r border-gray-300">{idx+1}</td>
								<td className="px-3 py-2 border-r border-gray-300">{it.code}</td>
								<td className="px-3 py-2 border-r border-gray-300">{it.description}</td>
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
							<tr className="border-t border-gray-300"><td className="px-3 py-6 text-center text-gray-500" colSpan={7}>No records</td></tr>
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

