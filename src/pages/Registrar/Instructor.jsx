import { useEffect, useMemo, useState, useRef } from 'react'
import { list, upsert, remove } from '../../store/db'

export default function Instructor() {
	const [items, setItems] = useState([])
	const [colleges, setColleges] = useState([])
	const [subjects, setSubjects] = useState([])
	const [q, setQ] = useState('')
	const [show, setShow] = useState(false)
	const [editing, setEditing] = useState(null)
	const [firstName, setFirstName] = useState('')
	const [middleName, setMiddleName] = useState('')
	const [lastName, setLastName] = useState('')
	const [collegeId, setCollegeId] = useState('')
	const [username, setUsername] = useState('')
	const [employmentType, setEmploymentType] = useState('regular')
	const [designation, setDesignation] = useState('')
	const [specialization, setSpecialization] = useState([])
	const [specializationSearch, setSpecializationSearch] = useState('')
	const [error, setError] = useState('')
	const [entries, setEntries] = useState(10)
	const [processing, setProcessing] = useState(false)
	
	// Prevent duplicate loads from React StrictMode
	const dataLoadingRef = useRef(false);
	const dataLoadedRef = useRef(false);

	async function load(force = false){ 
		// Skip if already loaded or currently loading (unless forced)
		if (!force && (dataLoadedRef.current || dataLoadingRef.current)) {
			return;
		}
		
		dataLoadingRef.current = true;
		try {
			const [instructorsData, collegesData, subjectsData] = await Promise.all([
				list('instructor'),
				list('college'),
				list('subject')
			])
			setItems(instructorsData)
			setColleges(collegesData)
			setSubjects(subjectsData || [])
			dataLoadedRef.current = true;
		} catch (error) {
			console.error('Error loading data:', error);
		} finally {
			dataLoadingRef.current = false;
		}
	}
	useEffect(()=>{ load() },[])

	const filtered = useMemo(()=>{
		return items.filter(i=> {
			const firstName = i.first_name || i.firstName || ''
			const middleName = i.middle_name || i.middleName || ''
			const lastName = i.last_name || i.lastName || ''
			return (`${firstName} ${middleName} ${lastName}`).toLowerCase().includes(q.toLowerCase())
		})
	},[items,q])

	const shown = useMemo(()=>{
		const n = Math.max(0, Number(entries)||0)
		return filtered.slice(0, n || filtered.length)
	}, [filtered, entries])

	function openAdd(){
		setEditing(null)
		setFirstName('')
		setMiddleName('')
		setLastName('')
		setCollegeId('')
		setUsername('')
		setEmploymentType('regular')
		setDesignation('')
		setSpecialization([])
		setSpecializationSearch('')
		setError('')
		setShow(true)
	}

	function openEdit(it){
		setEditing(it)
		setFirstName(it.first_name || it.firstName || '')
		setMiddleName(it.middle_name || it.middleName || '')
		setLastName(it.last_name || it.lastName || '')
		setCollegeId(it.college_id || it.collegeId || '')
		setUsername(it.username || '')
		setEmploymentType(it.employment_type || it.employmentType || 'regular')
		setDesignation(it.designation || '')
		{
			const raw = it.assignable_courses || it.assignableCourses || ''
			const parsed = raw
				.split(',')
				.map(s => s.trim())
				.filter(Boolean)
			setSpecialization(parsed)
		}
		setSpecializationSearch('')
		setError('')
		setShow(true)
	}

	async function onSave(e){
		e.preventDefault()
		if (processing) return
		if (!firstName.trim() || !lastName.trim()) { setError('First and Last name are required'); return }
		try {
			setProcessing(true)
			const payload = {
				id: editing?.id,
				first_name: firstName.trim(),
				middle_name: middleName.trim() || null,
				last_name: lastName.trim(),
				college_id: collegeId ? parseInt(collegeId) : null,
				username: username.trim() || null,
				employment_type: employmentType || null,
				designation: designation.trim() || null,
				assignable_courses: specialization && specialization.length
					? specialization.join(',')
					: null,
			}
			await upsert('instructor', payload)
			setShow(false)
			await load(true)
		} catch (error) {
			setError(error.message || 'Failed to save')
		} finally {
			setProcessing(false)
		}
	}

	const collegeName = (id) => {
		if (!id) return ''
		const college = colleges.find(c => c.id === id)
		return college?.code || ''
	}

	const subjectOptions = useMemo(() => {
		const query = specializationSearch.trim().toLowerCase()
		const selectedSet = new Set(specialization)
		return (subjects || [])
			.filter(s => {
				if (!s || !s.code) return false
				if (selectedSet.has(s.code)) return false
				if (!query) return true
				const code = String(s.code || '').toLowerCase()
				const desc = String(s.description || '').toLowerCase()
				return code.includes(query) || desc.includes(query)
			})
			.slice(0, 10)
	}, [subjects, specialization, specializationSearch])

	function addSpecialization(code){
		if (!code) return
		setSpecialization(prev => {
			if (prev.includes(code)) return prev
			return [...prev, code]
		})
	}

	function removeSpecialization(code){
		setSpecialization(prev => prev.filter(c => c !== code))
	}

	async function onDelete(id){
		if (processing) return
		if (!confirm('Delete this instructor?')) return
		try {
			setProcessing(true)
			await remove('instructor', id)
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
				<h1 className="text-navy text-3xl font-semibold">INSTRUCTOR</h1>
				<button className="px-3 py-2 rounded bg-royal text-white flex items-center gap-2 disabled:opacity-60" onClick={openAdd} disabled={processing}>
					<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-4 h-4"><path d="M11 11V5h2v6h6v2h-6v6h-2v-6H5v-2h6z"/></svg>
					<span>Add Instructor</span>
				</button>
			</div>
		{/* Standardized fixed-height container for list/table area */}
		<div className="h-[520px] overflow-auto pr-1 [&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none]">
		<div className="mb-1 text-navy text-1xl font-semibold">List of Instructor</div>
		<div className="mb-3 text-[11px] text-gray-700 max-w-2xl">
			Default instructor login:
			<span className="font-semibold"> username</span> is based on their name (for example,
			"<span className="italic">Juan Dela Cruz</span>" → <span className="font-mono">juan.dela.cruz</span>), and
			<span className="font-semibold"> password</span> is the instructor&apos;s last name.
			Instructors are required to change these on their first login.
		</div>
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
			<input className="w-full max-w-sm px-3 py-2 rounded-full border" placeholder="Search: Instructor" value={q} onChange={e=>setQ(e.target.value)} />
		</div>
			<div className="overflow-x-auto">
				<table className="min-w-full text-sm border border-gray-400">
					<thead>
						<tr className="bg-navy text-white border-b-2 border-gray-500">
							<th className="text-left px-3 py-2 border-r border-gray-300">No.</th>
							<th className="text-left px-3 py-2 border-r border-gray-300">Instructor</th>
							<th className="text-left px-3 py-2 border-r border-gray-300">College</th>
							<th className="text-left px-3 py-2 border-r border-gray-300">Specialization</th>
							<th className="text-center px-3 py-2 w-36">Action</th>
						</tr>
					</thead>
					<tbody className="divide-y divide-gray-300">
						{shown.map((it, idx)=> {
							const firstName = it.first_name || it.firstName || ''
							const middleName = it.middle_name || it.middleName || ''
							const lastName = it.last_name || it.lastName || ''
							const fullName = `${firstName} ${middleName ? middleName + ' ' : ''}${lastName}`.trim()
							const specializationText = it.assignable_courses || it.assignableCourses || ''
							return (
								<tr key={it.id} className={idx%2? 'bg-gray-50':''}>
									<td className="px-3 py-2 border-r border-gray-300">{idx+1}</td>
									<td className="px-3 py-2 border-r border-gray-300">{fullName || 'N/A'}</td>
									<td className="px-3 py-2 border-r border-gray-300">{collegeName(it.college_id || it.collegeId) || '-'}</td>
									<td className="px-3 py-2 border-r border-gray-300">{specializationText || '-'}</td>
									<td className="px-3 py-2 space-x-3 text-center">
									<button className="inline-flex items-center justify-center w-8 h-8 rounded-full bg-blue-600 hover:opacity-90" title="Edit" onClick={()=>openEdit(it)}>
										<img src="/assets/edit.png" alt="Edit" className="w-4 h-4 object-contain" onError={(e)=>{e.currentTarget.style.display='none'}} />
									</button>
									<button className="inline-flex items-center justify-center w-8 h-8 rounded-full bg-red-600 hover:opacity-90" title="Delete" onClick={()=>onDelete(it.id)}>
										<img src="/assets/delete.png" alt="Delete" className="w-4 h-4 object-contain" onError={(e)=>{e.currentTarget.style.display='none'}} />
									</button>
								</td>
							</tr>
						)
					})}
						{filtered.length===0 && (
							<tr className="border-t border-gray-300"><td className="px-3 py-6 text-center text-gray-500" colSpan={5}>No records</td></tr>
						)}
					</tbody>
				</table>
			</div>
		</div>

				{show && (
					<div className="fixed inset-0 bg-black/30 flex items-center justify-center p-4">
						<form onSubmit={onSave} className="w-full max-w-md bg-white rounded-xl shadow p-5 space-y-3">
							<div className="text-lg font-semibold text-navy">{editing? 'Edit Instructor':'Add Instructor'}</div>
							<input className="w-full px-3 py-2 rounded border" placeholder="First Name" value={firstName} onChange={e=>setFirstName(e.target.value)} />
							<input className="w-full px-3 py-2 rounded border" placeholder="Middle Name (optional)" value={middleName} onChange={e=>setMiddleName(e.target.value)} />
							<input className="w-full px-3 py-2 rounded border" placeholder="Last Name" value={lastName} onChange={e=>setLastName(e.target.value)} />
							<input className="w-full px-3 py-2 rounded border" placeholder="Username (optional, defaults to Firstname Lastname)" value={username} onChange={e=>setUsername(e.target.value)} />
							<select className="w-full px-3 py-2 rounded border" value={employmentType} onChange={e=>setEmploymentType(e.target.value)}>
								<option value="regular">Regular</option>
								<option value="visiting">Visiting Lecturer</option>
							</select>
							<select className="w-full px-3 py-2 rounded border" value={designation} onChange={e=>setDesignation(e.target.value)}>
								<option value="">No designation</option>
								<option value="Program Chair">Program Chair</option>
								<option value="College Secretary">College Secretary</option>
								<option value="Dean">Dean</option>
								<option value="Associate Dean">Associate Dean</option>
								<option value="Director">Director</option>
							</select>
							<select className="w-full px-3 py-2 rounded border" value={collegeId} onChange={e=>setCollegeId(e.target.value)}>
								<option value="">Select College (optional)</option>
								{colleges.map(c=> <option key={c.id} value={c.id}>{c.code} — {c.description}</option>)}
							</select>
							<div className="space-y-2">
								<div className="text-sm font-medium text-navy">Specialization (subjects)</div>
								<input
									className="w-full px-3 py-2 rounded border"
									placeholder="Search subject code or description"
									value={specializationSearch}
									onChange={e=>setSpecializationSearch(e.target.value)}
								/>
								{specialization.length > 0 && (
									<div className="flex flex-wrap gap-2 mt-1">
										{specialization.map(code => (
											<button
												key={code}
												type="button"
												className="px-2 py-1 rounded-full bg-royal text-white text-xs flex items-center gap-1"
												onClick={()=>removeSpecialization(code)}
											>
												<span>{code}</span>
												<span className="text-white/80 text-[10px]">✕</span>
											</button>
										))}
									</div>
								)}
								<div className="max-h-40 overflow-auto border rounded mt-1 bg-gray-50">
									{subjectOptions.length === 0 && (
										<div className="px-3 py-2 text-xs text-gray-500">No matching subjects</div>
									)}
									{subjectOptions.map(s => (
										<button
											key={s.id}
											type="button"
											className="w-full text-left px-3 py-1.5 text-xs hover:bg-royal/10 border-b last:border-b-0 border-gray-200"
											onClick={()=>addSpecialization(s.code)}
										>
											<span className="font-semibold">{s.code}</span>
											<span className="ml-2 text-gray-600">{s.description}</span>
										</button>
									))}
								</div>
							</div>
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

