import { useEffect, useMemo, useState, useRef } from 'react'
import { list, upsert, remove } from '../../store/db'
import ConfirmDialog from '../../components/ConfirmDialog'

export default function Course() {
	const [items, setItems] = useState([])
	const [colleges, setColleges] = useState([])
	const [q, setQ] = useState('')
	const [show, setShow] = useState(false)
	const [editing, setEditing] = useState(null)
	const [collegeId, setCollegeId] = useState('')
	const [code, setCode] = useState('')
	const [description, setDescription] = useState('')
	const [major, setMajor] = useState('')
	const [error, setError] = useState('')
	const [entries, setEntries] = useState(50)
	const [processing, setProcessing] = useState(false)
	const [confirmDialog, setConfirmDialog] = useState({ open: false })

	// Prevent duplicate loads from React StrictMode
	const dataLoadingRef = useRef(false);
	const dataLoadedRef = useRef(false);

	async function load(force = false) {
		// Skip if already loaded or currently loading
		if (!force && (dataLoadedRef.current || dataLoadingRef.current)) {
			return;
		}

		dataLoadingRef.current = true;
		try {
			const [coursesData, collegesData] = await Promise.all([
				list('course'),
				list('college')
			])
			setItems(coursesData)
			setColleges(collegesData)
			dataLoadedRef.current = true;
		} catch (error) {
			console.error('Error loading data:', error);
		} finally {
			dataLoadingRef.current = false;
		}
	}
	useEffect(() => { load() }, [])

	const filtered = useMemo(() => {
		return items.filter(i => (i.code + ' ' + i.description + ' ' + (i.major || '')).toLowerCase().includes(q.toLowerCase()))
	}, [items, q])

	const shown = useMemo(() => {
		const n = Math.max(0, Number(entries) || 0)
		return filtered.slice(0, n || filtered.length)
	}, [filtered, entries])

	// Group items by college for display
	const grouped = useMemo(() => {
		const collegeMap = {}
		colleges.forEach(c => { collegeMap[c.id] = c })

		const groups = []
		const byCollege = {}

		shown.forEach(it => {
			const cid = it.college_id || it.collegeId
			if (!byCollege[cid]) {
				byCollege[cid] = []
			}
			byCollege[cid].push(it)
		})

		// Sort colleges alphabetically
		const sortedCollegeIds = Object.keys(byCollege).sort((a, b) => {
			const ca = collegeMap[a]?.code || ''
			const cb = collegeMap[b]?.code || ''
			return ca.localeCompare(cb)
		})

		sortedCollegeIds.forEach(cid => {
			const college = collegeMap[cid]
			// Sort programs: by code, then by major
			const programs = byCollege[cid].sort((a, b) => {
				const codeCompare = (a.code || '').localeCompare(b.code || '')
				if (codeCompare !== 0) return codeCompare
				return (a.major || '').localeCompare(b.major || '')
			})
			groups.push({
				college,
				programs,
			})
		})

		return groups
	}, [shown, colleges])

	function openAdd() {
		setEditing(null)
		setCollegeId('')
		setCode('')
		setDescription('')
		setMajor('')
		setError('')
		setShow(true)
	}

	function openEdit(it) {
		setEditing(it)
		setCollegeId(it.college_id || it.collegeId || '')
		setCode(it.code)
		setDescription(it.description)
		setMajor(it.major || '')
		setError('')
		setShow(true)
	}

	async function onSave(e) {
		e.preventDefault()
		if (processing) return
		if (!collegeId || !code.trim() || !description.trim()) { setError('College, Code, and Description are required'); return }

		// Unique check: same code + same major (case-insensitive)
		const trimCode = code.trim().toLowerCase()
		const trimMajor = (major.trim() || '').toLowerCase()
		const duplicate = items.find(i =>
			i.code.toLowerCase() === trimCode &&
			(i.major || '').toLowerCase() === trimMajor &&
			i.id !== (editing?.id)
		)
		if (duplicate) {
			setError(trimMajor ? `"${code.trim()}" with major "${major.trim()}" already exists` : `"${code.trim()}" already exists`)
			return
		}

		try {
			setProcessing(true)
			await upsert('course', {
				id: editing?.id,
				college_id: parseInt(collegeId),
				code: code.trim(),
				description: description.trim(),
				major: major.trim() || null
			})
			setShow(false)
			await load(true)
		} catch (error) {
			setError(error.message || 'Failed to save')
		} finally {
			setProcessing(false)
		}
	}

	function onDelete(id) {
		if (processing) return
		setConfirmDialog({
			open: true,
			title: 'Delete Program',
			message: 'Are you sure you want to delete this program? This action cannot be undone.',
			confirmText: 'Delete',
			variant: 'danger',
			onConfirm: async () => {
				setConfirmDialog({ open: false })
				try {
					setProcessing(true)
					await remove('course', id)
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
				<h1 className="text-navy text-3xl font-semibold">PROGRAM</h1>
				<button className="px-3 py-2 rounded bg-royal text-white flex items-center gap-2 disabled:opacity-60" onClick={openAdd} disabled={processing}>
					<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-4 h-4"><path d="M11 11V5h2v6h6v2h-6v6h-2v-6H5v-2h6z" /></svg>
					<span>Add Program</span>
				</button>
			</div>
			{/* Standardized fixed-height container for list/table area */}
			<div className="h-[520px] overflow-auto pr-1 [&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none]">
				<div className="mb-2 text-navy text-1xl font-semibold">List of Program</div>
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
					<input className="w-full max-w-sm px-3 py-2 rounded-full border" placeholder="Search: Program" value={q} onChange={e => setQ(e.target.value)} />
				</div>
				<div className="overflow-x-auto space-y-4">
					{grouped.length === 0 && (
						<div className="text-center text-gray-400 py-10">No records found</div>
					)}
					{grouped.map(({ college, programs }) => (
						<div key={college?.id || 'unknown'} className="border border-gray-300 rounded-lg overflow-hidden">
							{/* College header */}
							<div className="bg-navy/90 text-white px-4 py-2 font-semibold text-sm flex items-center gap-2">
								<svg className="w-4 h-4 opacity-70" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2L1 7l11 5 9-4.09V17h2V7L12 2zM3 19h18v2H3z" /></svg>
								<span>{college?.code || 'Unknown'}</span>
								<span className="font-normal opacity-70">— {college?.description || ''}</span>
								<span className="ml-auto text-xs opacity-60">{programs.length} program{programs.length !== 1 ? 's' : ''}</span>
							</div>
							{/* Programs table */}
							<table className="min-w-full text-sm">
								<thead>
									<tr className="bg-gray-100 border-b border-gray-300">
										<th className="text-left px-3 py-1.5 w-12 text-gray-500 text-xs font-medium">#</th>
										<th className="text-left px-3 py-1.5 text-gray-500 text-xs font-medium">Code</th>
										<th className="text-left px-3 py-1.5 text-gray-500 text-xs font-medium">Description</th>
										<th className="text-left px-3 py-1.5 text-gray-500 text-xs font-medium">Major</th>
										<th className="text-center px-3 py-1.5 w-28 text-gray-500 text-xs font-medium">Action</th>
									</tr>
								</thead>
								<tbody className="divide-y divide-gray-200">
									{programs.map((it, idx) => (
										<tr key={it.id} className={idx % 2 ? 'bg-gray-50/50' : ''}>
											<td className="px-3 py-2 text-gray-400 text-xs">{idx + 1}</td>
											<td className="px-3 py-2 font-medium">{it.code}</td>
											<td className="px-3 py-2">{it.description}</td>
											<td className="px-3 py-2">
												{it.major
													? <span className="inline-block bg-blue-50 text-blue-700 text-xs px-2 py-0.5 rounded-full font-medium">{it.major}</span>
													: <span className="text-gray-300">—</span>
												}
											</td>
											<td className="px-3 py-2 space-x-2 text-center">
												<button className="inline-flex items-center justify-center w-7 h-7 rounded-full bg-blue-600 hover:opacity-90" title="Edit" onClick={() => openEdit(it)}>
													<img src="/assets/edit.png" alt="Edit" className="w-3.5 h-3.5 object-contain" onError={(e) => { e.currentTarget.style.display = 'none' }} />
												</button>
												<button className="inline-flex items-center justify-center w-7 h-7 rounded-full bg-red-600 hover:opacity-90" title="Delete" onClick={() => onDelete(it.id)}>
													<img src="/assets/delete.png" alt="Delete" className="w-3.5 h-3.5 object-contain" onError={(e) => { e.currentTarget.style.display = 'none' }} />
												</button>
											</td>
										</tr>
									))}
								</tbody>
							</table>
						</div>
					))}
				</div>
			</div>

			{show && (
				<div className="fixed inset-0 bg-black/30 flex items-center justify-center p-4">
					<form onSubmit={onSave} className="w-full max-w-md bg-white rounded-xl shadow p-5 space-y-3">
						<div className="text-lg font-semibold text-navy">{editing ? 'Edit Program' : 'Add Program'}</div>
						<select className="w-full px-3 py-2 rounded border" value={collegeId} onChange={e => setCollegeId(e.target.value)}>
							<option value="">Select College</option>
							{colleges.map(c => <option key={c.id} value={c.id}>{c.code} — {c.description}</option>)}
						</select>
						<input className="w-full px-3 py-2 rounded border" placeholder="Code (e.g. BSED)" value={code} onChange={e => setCode(e.target.value)} />
						<input className="w-full px-3 py-2 rounded border" placeholder="Description (e.g. BS Education)" value={description} onChange={e => setDescription(e.target.value)} />
						<input className="w-full px-3 py-2 rounded border" placeholder="Major (optional — e.g. English, Mathematics)" value={major} onChange={e => setMajor(e.target.value)} />
						<p className="text-xs text-gray-400">Leave Major empty for programs without a specialization</p>
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
