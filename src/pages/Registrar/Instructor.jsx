import { useEffect, useMemo, useState, useRef } from 'react'
import { list, upsert, remove } from '../../store/db'
import ConfirmDialog from '../../components/ConfirmDialog'

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
	const [employmentType, setEmploymentType] = useState('regular')
	const [designation, setDesignation] = useState('')
	const [specialization, setSpecialization] = useState([])
	const [specializationSearch, setSpecializationSearch] = useState('')
	const [error, setError] = useState('')
	const [entries, setEntries] = useState(10)
	const [processing, setProcessing] = useState(false)
	const [confirmDialog, setConfirmDialog] = useState({ open: false })

	// Prevent duplicate loads from React StrictMode
	const dataLoadingRef = useRef(false);
	const dataLoadedRef = useRef(false);

	async function load(force = false) {
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
	useEffect(() => { load() }, [])

	const filtered = useMemo(() => {
		return items.filter(i => {
			const firstName = i.first_name || i.firstName || ''
			const middleName = i.middle_name || i.middleName || ''
			const lastName = i.last_name || i.lastName || ''
			return (`${firstName} ${middleName} ${lastName}`).toLowerCase().includes(q.toLowerCase())
		})
	}, [items, q])

	const shown = useMemo(() => {
		const n = Math.max(0, Number(entries) || 0)
		return filtered.slice(0, n || filtered.length)
	}, [filtered, entries])

	function openAdd() {
		setEditing(null)
		setFirstName('')
		setMiddleName('')
		setLastName('')
		setCollegeId('')
		setEmploymentType('regular')
		setDesignation('')
		setSpecialization([])
		setSpecializationSearch('')
		setError('')
		setShow(true)
	}

	function openEdit(it) {
		setEditing(it)
		setFirstName(it.first_name || it.firstName || '')
		setMiddleName(it.middle_name || it.middleName || '')
		setLastName(it.last_name || it.lastName || '')
		setCollegeId(it.college_id || it.collegeId || '')
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

	async function onSave(e) {
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

	// Build a map of code → all variant subjects (for showing descriptions)
	const subjectVariantsMap = useMemo(() => {
		const map = {} // normalised code → [{ code, description, type, unit, semester, id }]
		for (const s of (subjects || [])) {
			if (!s || !s.code) continue
			const norm = s.code.trim().toUpperCase().replace(/\s+/g, ' ')
			if (!map[norm]) map[norm] = { code: s.code, variants: [], semesters: new Set() }
			// Avoid duplicate description+type combos
			const key = `${(s.description || '').toLowerCase()}|${s.type}`
			if (!map[norm].variants.find(v => `${(v.description || '').toLowerCase()}|${v.type}` === key)) {
				map[norm].variants.push({ id: s.id, code: s.code, description: s.description, type: s.type, unit: s.unit, semester: s.semester })
			}
			if (s.semester) map[norm].semesters.add(s.semester)
		}
		return map
	}, [subjects])

	const subjectOptions = useMemo(() => {
		const query = specializationSearch.trim().toLowerCase()
		const selectedSet = new Set(specialization)
		// Group subjects by normalised code and return one entry per code
		const seen = new Set()
		return (subjects || [])
			.filter(s => {
				if (!s || !s.code) return false
				const norm = s.code.trim().toUpperCase().replace(/\s+/g, ' ')
				if (seen.has(norm)) return false
				if (selectedSet.has(s.code)) return false
				if (selectedSet.has(norm)) return false
				// Also check if any variant's code is already selected
				if ([...selectedSet].some(sel => sel.trim().toUpperCase().replace(/\s+/g, ' ') === norm)) return false
				if (!query) { seen.add(norm); return true }
				// Search across ALL variants of this code
				const group = subjectVariantsMap[norm]
				if (!group) return false
				const matchesCode = norm.toLowerCase().includes(query) || s.code.toLowerCase().includes(query)
				const matchesDesc = group.variants.some(v => (v.description || '').toLowerCase().includes(query))
				if (matchesCode || matchesDesc) { seen.add(norm); return true }
				return false
			})
			.slice(0, 10)
	}, [subjects, specialization, specializationSearch, subjectVariantsMap])

	// Map subject codes to their semester(s) for display
	const subjectSemMap = useMemo(() => {
		const map = {} // normalised code -> Set of semesters
		for (const s of (subjects || [])) {
			if (!s || !s.code) continue
			const norm = s.code.trim().toUpperCase().replace(/\s+/g, ' ')
			if (!map[norm]) map[norm] = new Set()
			if (s.semester) map[norm].add(s.semester)
		}
		return map
	}, [subjects])

	function getSubjectSem(code) {
		const norm = (code || '').trim().toUpperCase().replace(/\s+/g, ' ')
		const sems = subjectSemMap[norm]
		if (!sems || sems.size === 0) return { label: '?', color: 'bg-slate-200 text-slate-600' }
		if (sems.has(1) && sems.has(2)) return { label: 'S1+S2', color: 'bg-emerald-100 text-emerald-700' }
		if (sems.has(1)) return { label: 'S1', color: 'bg-indigo-100 text-indigo-700' }
		if (sems.has(2)) return { label: 'S2', color: 'bg-teal-100 text-teal-700' }
		return { label: '?', color: 'bg-slate-200 text-slate-600' }
	}

	function getVariantCount(code) {
		const norm = (code || '').trim().toUpperCase().replace(/\s+/g, ' ')
		return subjectVariantsMap[norm]?.variants?.length || 0
	}

	function addSpecialization(code) {
		if (!code) return
		setSpecialization(prev => {
			if (prev.includes(code)) return prev
			return [...prev, code]
		})
	}

	function removeSpecialization(code) {
		setSpecialization(prev => prev.filter(c => c !== code))
	}

	function onDelete(id) {
		if (processing) return
		setConfirmDialog({
			open: true,
			title: 'Delete Instructor',
			message: 'Are you sure you want to delete this instructor? This action cannot be undone.',
			confirmText: 'Delete',
			variant: 'danger',
			onConfirm: async () => {
				setConfirmDialog({ open: false })
				try {
					setProcessing(true)
					await remove('instructor', id)
					await load(true)
				} catch (error) {
					alert(error.message || 'Failed to delete')
				} finally {
					setProcessing(false)
				}
			},
		})
	}

	return (
		<div>
			<div className="flex items-center justify-between mb-4">
				<h1 className="text-navy text-3xl font-semibold">INSTRUCTOR</h1>
				<button className="px-3 py-2 rounded bg-royal text-white flex items-center gap-2 disabled:opacity-60" onClick={openAdd} disabled={processing}>
					<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-4 h-4"><path d="M11 11V5h2v6h6v2h-6v6h-2v-6H5v-2h6z" /></svg>
					<span>Add Instructor</span>
				</button>
			</div>
			{/* Standardized fixed-height container for list/table area */}
			<div className="h-[520px] overflow-auto pr-1 [&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none]">
				<div className="mb-1 text-navy text-1xl font-semibold">List of Instructor</div>

				<div className="flex items-center justify-between mb-3 gap-4">
					<div className="flex items-center gap-2 text-sm">
						<span>Show</span>
						<div className="flex items-stretch border border-gray-300 rounded overflow-hidden">
							<input type="number" min="1" className="w-16 px-2 outline-none text-center" value={entries} onChange={e => setEntries(e.target.value)} />
							<div className="flex flex-col">
								<button type="button" aria-label="Increase" className="px-2 border-l border-b border-gray-300 hover:bg-gray-100" onClick={() => setEntries(prev => Number(prev || 0) + 1)}>▲</button>
								<button type="button" aria-label="Decrease" className="px-2 border-l border-gray-300 hover:bg-gray-100" onClick={() => setEntries(prev => Math.max(1, Number(prev || 0) - 1))}>▼</button>
							</div>
						</div>
						<span>entries</span>
					</div>
					<input className="w-full max-w-sm px-3 py-2 rounded-full border" placeholder="Search: Instructor" value={q} onChange={e => setQ(e.target.value)} />
				</div>
				<div className="overflow-x-auto">
					<table className="min-w-full text-sm border border-gray-400">
						<thead>
							<tr className="bg-navy text-white border-b-2 border-gray-500">
								<th className="text-left px-3 py-2 border-r border-gray-300">No.</th>
								<th className="text-left px-3 py-2 border-r border-gray-300">Instructor</th>
								<th className="text-left px-3 py-2 border-r border-gray-300">College</th>
								<th className="text-left px-3 py-2 border-r border-gray-300">Specialization</th>
								<th className="text-center px-3 py-2 border-r border-gray-300">Status</th>
								<th className="text-center px-3 py-2 w-36">Action</th>
							</tr>
						</thead>
						<tbody className="divide-y divide-gray-300">
							{shown.map((it, idx) => {
								const firstName = it.first_name || it.firstName || ''
								const middleName = it.middle_name || it.middleName || ''
								const lastName = it.last_name || it.lastName || ''
								const fullName = `${firstName} ${middleName ? middleName + ' ' : ''}${lastName}`.trim()
								const specializationText = it.assignable_courses || it.assignableCourses || ''
								return (
									<tr key={it.id} className={idx % 2 ? 'bg-gray-50' : ''}>
										<td className="px-3 py-2 border-r border-gray-300">{idx + 1}</td>
										<td className="px-3 py-2 border-r border-gray-300">{fullName || 'N/A'}</td>
										<td className="px-3 py-2 border-r border-gray-300">{collegeName(it.college_id || it.collegeId) || '-'}</td>
										<td className="px-3 py-2 border-r border-gray-300">{specializationText || '-'}</td>
										<td className="px-3 py-2 border-r border-gray-300 text-center">
											<button
												className={`inline-block px-2 py-0.5 rounded-full text-xs font-semibold cursor-pointer hover:opacity-80 ${it.is_active !== false ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
													}`}
												title={it.is_active !== false ? 'Click to deactivate' : 'Click to activate'}
												onClick={() => {
													const fullName = `${it.first_name || ''} ${it.last_name || ''}`.trim()
													const newActive = it.is_active === false
													setConfirmDialog({
														open: true,
														title: newActive ? 'Activate Instructor' : 'Deactivate Instructor',
														message: `Are you sure you want to ${newActive ? 'activate' : 'deactivate'} "${fullName}"?`,
														confirmText: newActive ? 'Activate' : 'Deactivate',
														variant: 'warning',
														onConfirm: async () => {
															setConfirmDialog({ open: false })
															try {
																await upsert('instructor', { id: it.id, is_active: newActive })
																await load(true)
															} catch (err) { alert(err.message || 'Failed to toggle status') }
														},
													})
												}}
											>
												{it.is_active !== false ? 'Active' : 'Inactive'}
											</button>
										</td>
										<td className="px-3 py-2 space-x-3 text-center">
											<button className="inline-flex items-center justify-center w-8 h-8 rounded-full bg-blue-600 hover:opacity-90" title="Edit" onClick={() => openEdit(it)}>
												<img src="/assets/edit.png" alt="Edit" className="w-4 h-4 object-contain" onError={(e) => { e.currentTarget.style.display = 'none' }} />
											</button>
											<button className="inline-flex items-center justify-center w-8 h-8 rounded-full bg-red-600 hover:opacity-90" title="Delete" onClick={() => onDelete(it.id)}>
												<img src="/assets/delete.png" alt="Delete" className="w-4 h-4 object-contain" onError={(e) => { e.currentTarget.style.display = 'none' }} />
											</button>
										</td>
									</tr>
								)
							})}
							{filtered.length === 0 && (
								<tr className="border-t border-gray-300"><td className="px-3 py-6 text-center text-gray-500" colSpan={6}>No records</td></tr>
							)}
						</tbody>
					</table>
				</div>
			</div>

			{show && (
				<div className="fixed inset-0 bg-black/30 flex items-center justify-center p-4">
					<form onSubmit={onSave} className="w-full max-w-md bg-white rounded-xl shadow p-5 space-y-3">
						<div className="text-lg font-semibold text-navy">{editing ? 'Edit Instructor' : 'Add Instructor'}</div>
						<input className="w-full px-3 py-2 rounded border" placeholder="First Name" value={firstName} onChange={e => setFirstName(e.target.value)} />
						<input className="w-full px-3 py-2 rounded border" placeholder="Middle Name (optional)" value={middleName} onChange={e => setMiddleName(e.target.value)} />
						<input className="w-full px-3 py-2 rounded border" placeholder="Last Name" value={lastName} onChange={e => setLastName(e.target.value)} />
						<select className="w-full px-3 py-2 rounded border" value={employmentType} onChange={e => setEmploymentType(e.target.value)}>
							<option value="regular">Regular</option>
							<option value="visiting">Visiting Lecturer</option>
						</select>
						<select className="w-full px-3 py-2 rounded border" value={designation} onChange={e => setDesignation(e.target.value)}>
							<option value="">No designation</option>
							<option value="Program Chair">Program Chair</option>
							<option value="College Secretary">College Secretary</option>
							<option value="Dean">Dean</option>
							<option value="Associate Dean">Associate Dean</option>
							<option value="Director">Director</option>
						</select>
						<select className="w-full px-3 py-2 rounded border" value={collegeId} onChange={e => setCollegeId(e.target.value)}>
							<option value="">Select College (optional)</option>
							{colleges.map(c => <option key={c.id} value={c.id}>{c.code} — {c.description}</option>)}
						</select>
						<div className="space-y-2">
							<div className="text-sm font-medium text-navy">Specialization (subjects)</div>
							<input
								className="w-full px-3 py-2 rounded border"
								placeholder="Search subject code or description"
								value={specializationSearch}
								onChange={e => setSpecializationSearch(e.target.value)}
							/>
							{specialization.length > 0 && (
								<>
								<div className="flex flex-wrap gap-2 mt-1">
									{specialization.map(code => {
										const sem = getSubjectSem(code)
										const vCount = getVariantCount(code)
										const norm = code.trim().toUpperCase().replace(/\s+/g, ' ')
										const group = subjectVariantsMap[norm]
										const tooltip = group?.variants?.map(v => `${v.description} (${v.type} ${v.unit}u)`).join('\n') || ''
										return (
											<button
												key={code}
												type="button"
												className="px-2 py-1 rounded-full bg-royal text-white text-xs flex items-center gap-1"
												onClick={() => removeSpecialization(code)}
												title={vCount > 1 ? `Matches ${vCount} subjects:\n${tooltip}` : tooltip}
											>
												<span>{code}</span>
												{vCount > 1 && <span className="text-[9px] font-bold px-1 py-px rounded bg-amber-400 text-amber-900">×{vCount}</span>}
												<span className={`text-[9px] font-bold px-1 py-px rounded ${sem.color}`}>{sem.label}</span>
												<span className="text-white/80 text-[10px]">✕</span>
											</button>
										)
									})}
								</div>
								{/* Semester balance summary */}
								{(() => {
									const s1 = specialization.filter(c => { const s = getSubjectSem(c); return s.label === 'S1' || s.label === 'S1+S2' }).length
									const s2 = specialization.filter(c => { const s = getSubjectSem(c); return s.label === 'S2' || s.label === 'S1+S2' }).length
									const unmatched = specialization.filter(c => getSubjectSem(c).label === '?').length
									const maxS = Math.max(s1, s2, 1)
									const isLopsided = (s1 > 0 && s2 === 0) || (s2 > 0 && s1 === 0)
									return (
										<div className={`mt-2 p-2 rounded-lg border text-xs ${isLopsided ? 'bg-amber-50 border-amber-200' : 'bg-slate-50 border-slate-200'}`}>
											<div className="flex items-center gap-3 mb-1">
												<span className="font-bold text-slate-500">Semester Balance</span>
												{isLopsided && <span className="text-[10px] text-amber-600 font-bold">⚠ Lopsided</span>}
											</div>
											<div className="flex items-center gap-2">
												<span className="text-[10px] font-bold text-indigo-600 w-5">S1</span>
												<div className="flex-1 bg-slate-200 rounded-full h-2 overflow-hidden">
													<div className="h-2 rounded-full bg-indigo-500 transition-all" style={{width: `${(s1 / maxS) * 100}%`}}></div>
												</div>
												<span className="font-bold text-slate-700 w-4 text-right">{s1}</span>
												<span className="text-[10px] font-bold text-teal-600 w-5 ml-2">S2</span>
												<div className="flex-1 bg-slate-200 rounded-full h-2 overflow-hidden">
													<div className="h-2 rounded-full bg-teal-500 transition-all" style={{width: `${(s2 / maxS) * 100}%`}}></div>
												</div>
												<span className="font-bold text-slate-700 w-4 text-right">{s2}</span>
											</div>
											{unmatched > 0 && <div className="text-[10px] text-rose-500 mt-1">⚠ {unmatched} subject(s) not found in database</div>}
										</div>
									)
								})()}
								</>
							)}
							<div className="max-h-40 overflow-auto border rounded mt-1 bg-gray-50">
								{subjectOptions.length === 0 && (
									<div className="px-3 py-2 text-xs text-gray-500">No matching subjects</div>
								)}
								{subjectOptions.map(s => {
									const sem = getSubjectSem(s.code)
									const norm = s.code.trim().toUpperCase().replace(/\s+/g, ' ')
									const group = subjectVariantsMap[norm]
									const variants = group?.variants || [{ description: s.description, type: s.type, unit: s.unit }]
									return (
										<button
											key={s.id}
											type="button"
											className="w-full text-left px-3 py-2 text-xs hover:bg-royal/10 border-b last:border-b-0 border-gray-200"
											onClick={() => addSpecialization(s.code)}
										>
											<div className="flex items-center gap-2">
												<span className="font-semibold">{s.code}</span>
												<span className={`text-[9px] font-bold px-1 py-px rounded ${sem.color}`}>{sem.label}</span>
												{variants.length > 1 && <span className="text-[9px] font-bold px-1 py-px rounded bg-amber-100 text-amber-700">{variants.length} subjects</span>}
											</div>
											{variants.map((v, vi) => (
												<div key={vi} className="text-[10px] text-gray-500 pl-1 mt-0.5 flex items-center gap-1">
													<span className="text-[9px] font-bold text-slate-400">{v.type}</span>
													<span className="text-[9px] text-slate-400">{v.unit}u</span>
													<span className="truncate">{v.description}</span>
												</div>
											))}
										</button>
									)
								})}
							</div>
						</div>
						{error && <div className="text-sm text-red-600">{error}</div>}
						<div className="flex justify-end gap-2 pt-2">
							<button type="button" className="px-3 py-2 rounded border" onClick={() => setShow(false)} disabled={processing}>Cancel</button>
							<button className="px-3 py-2 rounded bg-royal text-white disabled:opacity-60" disabled={processing}>Save</button>
						</div>
					</form>
				</div>
			)}

			<ConfirmDialog
				{...confirmDialog}
				onCancel={() => setConfirmDialog({ open: false })}
			/>
		</div>
	)
}

