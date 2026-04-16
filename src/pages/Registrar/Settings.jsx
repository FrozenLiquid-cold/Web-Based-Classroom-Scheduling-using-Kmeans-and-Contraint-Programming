import { useEffect, useState, useRef, useMemo } from 'react'

const API = 'http://localhost:8000/api'

export default function Settings() {
	// ─── Designation Deductions state ───
	const [items, setItems] = useState([])
	const [show, setShow] = useState(false)
	const [editing, setEditing] = useState(null)
	const [designation, setDesignation] = useState('')
	const [hours, setHours] = useState('')
	const [error, setError] = useState('')
	const [processing, setProcessing] = useState(false)

	// ─── Time Blocks state ───
	const [timeBlocks, setTimeBlocks] = useState([])
	const [days, setDays] = useState([])
	const [tbShow, setTbShow] = useState(false)
	const [tbEditing, setTbEditing] = useState(null)
	const [tbStartTime, setTbStartTime] = useState('07:30')
	const [tbEndTime, setTbEndTime] = useState('09:00')
	const [tbIsLab, setTbIsLab] = useState(false)
	const [tbSelectedDays, setTbSelectedDays] = useState([])
	const [tbError, setTbError] = useState('')
	const [tbProcessing, setTbProcessing] = useState(false)
	const [tbActiveDay, setTbActiveDay] = useState(null) // filter view by day

	const loadedRef = useRef(false)

	// ─── Load designation deductions ───
	async function load() {
		try {
			const res = await fetch(`${API}/designation-deductions`)
			if (res.ok) setItems(await res.json())
		} catch (e) {
			console.error('Failed to load deductions', e)
		}
	}

	// ─── Load time blocks + days ───
	async function loadTimeBlocks() {
		try {
			const [tbRes, dayRes] = await Promise.all([
				fetch(`${API}/time-blocks`),
				fetch(`${API}/days`),
			])
			if (tbRes.ok) setTimeBlocks(await tbRes.json())
			if (dayRes.ok) {
				const d = await dayRes.json()
				setDays(d)
				if (!tbActiveDay && d.length > 0) setTbActiveDay(d[0].id)
			}
		} catch (e) {
			console.error('Failed to load time blocks', e)
		}
	}

	useEffect(() => {
		if (!loadedRef.current) {
			loadedRef.current = true
			load()
			loadTimeBlocks()
		}
	}, [])

	// ─── Designation Deduction handlers ───
	function openAdd() {
		setEditing(null)
		setDesignation('')
		setHours('')
		setError('')
		setShow(true)
	}

	function openEdit(it) {
		setEditing(it)
		setDesignation(it.designation)
		setHours(String(it.deduction_hours))
		setError('')
		setShow(true)
	}

	async function onSave(e) {
		e.preventDefault()
		if (processing) return
		if (!designation.trim()) { setError('Designation is required'); return }
		if (!hours || isNaN(Number(hours)) || Number(hours) < 0) { setError('Hours must be 0 or more'); return }

		try {
			setProcessing(true)
			const body = { designation: designation.trim(), deduction_hours: Number(hours) }

			if (editing) {
				const res = await fetch(`${API}/designation-deductions/${editing.id}`, {
					method: 'PUT',
					headers: { 'Content-Type': 'application/json' },
					body: JSON.stringify(body),
				})
				if (!res.ok) {
					const data = await res.json().catch(() => ({}))
					throw new Error(data.detail || 'Failed to update')
				}
			} else {
				const res = await fetch(`${API}/designation-deductions`, {
					method: 'POST',
					headers: { 'Content-Type': 'application/json' },
					body: JSON.stringify(body),
				})
				if (!res.ok) {
					const data = await res.json().catch(() => ({}))
					throw new Error(data.detail || 'Failed to create')
				}
			}

			setShow(false)
			await load()
		} catch (err) {
			setError(err.message || 'Failed to save')
		} finally {
			setProcessing(false)
		}
	}

	async function onDelete(id) {
		if (processing) return
		if (!confirm('Delete this designation deduction?')) return
		try {
			setProcessing(true)
			await fetch(`${API}/designation-deductions/${id}`, { method: 'DELETE' })
			await load()
		} catch (err) {
			alert(err.message || 'Failed to delete')
		} finally {
			setProcessing(false)
		}
	}

	// ─── Time Block handlers ───
	function tbOpenAdd() {
		setTbEditing(null)
		setTbStartTime('07:30')
		setTbEndTime('09:00')
		setTbIsLab(false)
		setTbSelectedDays(days.map(d => d.id))
		setTbError('')
		setTbShow(true)
	}

	function tbOpenEdit(tb) {
		setTbEditing(tb)
		setTbStartTime(tb.start_time)
		setTbEndTime(tb.end_time)
		setTbIsLab(tb.is_lab)
		setTbSelectedDays([tb.day_id])
		setTbError('')
		setTbShow(true)
	}

	async function tbOnSave(e) {
		e.preventDefault()
		if (tbProcessing) return
		if (!tbStartTime || !tbEndTime) { setTbError('Start and end time are required'); return }
		if (tbStartTime >= tbEndTime) { setTbError('End time must be after start time'); return }
		if (!tbEditing && tbSelectedDays.length === 0) { setTbError('Select at least one day'); return }

		try {
			setTbProcessing(true)
			if (tbEditing) {
				const res = await fetch(`${API}/time-blocks/${tbEditing.block_id}`, {
					method: 'PUT',
					headers: { 'Content-Type': 'application/json' },
					body: JSON.stringify({
						start_time: tbStartTime,
						end_time: tbEndTime,
						is_lab: tbIsLab,
					}),
				})
				if (!res.ok) {
					const data = await res.json().catch(() => ({}))
					throw new Error(data.detail || 'Failed to update')
				}
			} else {
				const res = await fetch(`${API}/time-blocks`, {
					method: 'POST',
					headers: { 'Content-Type': 'application/json' },
					body: JSON.stringify({
						day_ids: tbSelectedDays,
						start_time: tbStartTime,
						end_time: tbEndTime,
						is_lab: tbIsLab,
					}),
				})
				if (!res.ok) {
					const data = await res.json().catch(() => ({}))
					throw new Error(data.detail || 'Failed to create')
				}
			}

			setTbShow(false)
			await loadTimeBlocks()
		} catch (err) {
			setTbError(err.message || 'Failed to save')
		} finally {
			setTbProcessing(false)
		}
	}

	async function tbOnDelete(blockId) {
		if (tbProcessing) return
		if (!confirm('Delete this time slot?')) return
		try {
			setTbProcessing(true)
			await fetch(`${API}/time-blocks/${blockId}`, { method: 'DELETE' })
			await loadTimeBlocks()
		} catch (err) {
			alert(err.message || 'Failed to delete')
		} finally {
			setTbProcessing(false)
		}
	}

	async function tbResetDefaults() {
		if (tbProcessing) return
		if (!confirm('This will delete all current time slots and restore the 14 default registrar windows for every day. Continue?')) return
		try {
			setTbProcessing(true)
			const res = await fetch(`${API}/time-blocks/reset-defaults`, { method: 'POST' })
			if (!res.ok) {
				const data = await res.json().catch(() => ({}))
				throw new Error(data.detail || 'Failed to reset')
			}
			await loadTimeBlocks()
		} catch (err) {
			alert(err.message || 'Failed to reset')
		} finally {
			setTbProcessing(false)
		}
	}

	function toggleDay(dayId) {
		setTbSelectedDays(prev =>
			prev.includes(dayId) ? prev.filter(id => id !== dayId) : [...prev, dayId]
		)
	}

	// Helpers
	function formatTo12Hour(timeStr) {
		if (!timeStr) return '—'
		const parts = timeStr.split(':')
		if (parts.length < 2) return timeStr
		let h = parseInt(parts[0], 10)
		const m = parseInt(parts[1], 10)
		const ampm = h >= 12 ? 'PM' : 'AM'
		if (h === 0) h = 12
		else if (h > 12) h -= 12
		return `${h}:${m.toString().padStart(2, '0')} ${ampm}`
	}

	function getDuration(startMin, endMin) {
		const diff = endMin - startMin
		if (diff >= 60 && diff % 60 === 0) return `${diff / 60} hr${diff / 60 > 1 ? 's' : ''}`
		const hrs = Math.floor(diff / 60)
		const mins = diff % 60
		if (hrs === 0) return `${mins} min`
		return `${hrs} hr ${mins} min`
	}

	const dayMap = useMemo(() => {
		const m = {}
		days.forEach(d => { m[d.id] = d.label })
		return m
	}, [days])

	// Group time blocks by day and sort
	const filteredBlocks = useMemo(() => {
		if (tbActiveDay === null) return timeBlocks
		return timeBlocks.filter(tb => tb.day_id === tbActiveDay)
	}, [timeBlocks, tbActiveDay])

	// Split blocks into LEC and LAB groups, sorted by time
	const { lecBlocks, labBlocks } = useMemo(() => {
		let blocks
		if (tbActiveDay !== null) {
			// Single day view — just return sorted blocks for that day
			blocks = [...filteredBlocks].sort((a, b) => a.start_min - b.start_min || a.end_min - b.end_min)
		} else {
			// "All" view — group by time range + is_lab
			const grouped = {}
			timeBlocks.forEach(tb => {
				const key = `${tb.start_min}-${tb.end_min}-${tb.is_lab}`
				if (!grouped[key]) {
					grouped[key] = { ...tb, _dayIds: [tb.day_id], _blockIds: [tb.block_id] }
				} else {
					grouped[key]._dayIds.push(tb.day_id)
					grouped[key]._blockIds.push(tb.block_id)
				}
			})
			blocks = Object.values(grouped).sort((a, b) => a.start_min - b.start_min || a.end_min - b.end_min)
		}
		return {
			lecBlocks: blocks.filter(b => !b.is_lab),
			labBlocks: blocks.filter(b => b.is_lab),
		}
	}, [timeBlocks, filteredBlocks, tbActiveDay])

	return (
		<div>
			<h1 className="text-navy text-3xl font-semibold mb-6">Settings</h1>

			{/* ══════════════════════════════════════════════════════════════════
			    Designation Deductions Section
			    ══════════════════════════════════════════════════════════════════ */}
			<div className="mb-8">
				<div className="flex items-center justify-between mb-4">
					<div>
						<h2 className="text-navy text-xl font-semibold">Designation Deductions</h2>
						<p className="text-sm text-gray-500 mt-1">
							Configure how many hours are deducted from the weekly load limit (24 hrs) for each designation role.
						</p>
					</div>
					<button
						className="px-3 py-2 rounded bg-royal text-white flex items-center gap-2 disabled:opacity-60 text-sm"
						onClick={openAdd}
						disabled={processing}
					>
						<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-4 h-4">
							<path d="M11 11V5h2v6h6v2h-6v6h-2v-6H5v-2h6z" />
						</svg>
						Add Designation
					</button>
				</div>

				<div className="bg-gray-50 rounded-lg border border-gray-200 p-4">
					<div className="text-xs text-gray-400 mb-3">
						<strong>Regular</strong> instructors base limit = <strong>24 hrs</strong> — deduction.
						&nbsp;|&nbsp;
						<strong>Visiting</strong> lecturers always = <strong>30 hrs</strong> (no deduction applied).
					</div>

					{items.length === 0 ? (
						<div className="text-center text-gray-400 py-6">No deductions configured. Default values (hardcoded fallback) will be used.</div>
					) : (
						<div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
							{items.map((it) => (
								<div
									key={it.id}
									className="bg-white rounded-lg border border-gray-200 p-4 flex items-center justify-between shadow-sm hover:shadow transition-shadow"
								>
									<div>
										<div className="font-semibold text-navy capitalize text-sm">{it.designation}</div>
										<div className="text-xs text-gray-500 mt-1">
											Deduction: <span className="font-bold text-red-600">{it.deduction_hours} hrs</span>
											&nbsp;→&nbsp;Limit: <span className="font-bold text-green-700">{Math.max(0, 24 - it.deduction_hours)} hrs</span>
										</div>
									</div>
									<div className="flex items-center gap-1.5 ml-3">
										<button
											className="inline-flex items-center justify-center w-7 h-7 rounded-full bg-blue-600 hover:opacity-90 text-white"
											title="Edit"
											onClick={() => openEdit(it)}
										>
											<svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="currentColor">
												<path d="M3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25zM20.71 7.04a1 1 0 000-1.41l-2.34-2.34a1 1 0 00-1.41 0l-1.83 1.83 3.75 3.75 1.83-1.83z" />
											</svg>
										</button>
										<button
											className="inline-flex items-center justify-center w-7 h-7 rounded-full bg-red-600 hover:opacity-90 text-white"
											title="Delete"
											onClick={() => onDelete(it.id)}
										>
											<svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="currentColor">
												<path d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z" />
											</svg>
										</button>
									</div>
								</div>
							))}
						</div>
					)}
				</div>
			</div>

			{/* Designation Modal */}
			{show && (
				<div className="fixed inset-0 bg-black/30 flex items-center justify-center p-4 z-50">
					<form onSubmit={onSave} className="w-full max-w-sm bg-white rounded-xl shadow p-5 space-y-3">
						<div className="text-lg font-semibold text-navy">
							{editing ? 'Edit Designation' : 'Add Designation'}
						</div>
						<input
							className="w-full px-3 py-2 rounded border"
							placeholder="Designation (e.g. Dean, Program Chair)"
							value={designation}
							onChange={(e) => setDesignation(e.target.value)}
						/>
						<div>
							<label className="block text-sm text-gray-600 mb-1">Deduction Hours</label>
							<input
								type="number"
								min="0"
								max="24"
								className="w-full px-3 py-2 rounded border"
								placeholder="Hours to deduct from 24-hr limit"
								value={hours}
								onChange={(e) => setHours(e.target.value)}
							/>
							{hours && !isNaN(Number(hours)) && (
								<p className="text-xs text-gray-400 mt-1">
									Effective limit: <strong>{Math.max(0, 24 - Number(hours))} hrs/week</strong>
								</p>
							)}
						</div>
						{error && <div className="text-sm text-red-600">{error}</div>}
						<div className="flex justify-end gap-2 pt-2">
							<button type="button" className="px-3 py-2 rounded border" onClick={() => setShow(false)} disabled={processing}>
								Cancel
							</button>
							<button className="px-3 py-2 rounded bg-royal text-white disabled:opacity-60" disabled={processing}>
								Save
							</button>
						</div>
					</form>
				</div>
			)}

			{/* ══════════════════════════════════════════════════════════════════
			    Time Slots Section
			    ══════════════════════════════════════════════════════════════════ */}
			<div className="mb-8">
				<div className="flex items-center justify-between mb-4">
					<div>
						<h2 className="text-navy text-xl font-semibold">Time Slots</h2>
						<p className="text-sm text-gray-500 mt-1">
							Configure the time windows available for scheduling classes. Each slot defines a start/end time the scheduler can assign subjects to.
						</p>
					</div>
					<div className="flex items-center gap-2">
						<button
							className="px-3 py-2 rounded border border-gray-300 text-gray-600 hover:bg-gray-50 flex items-center gap-2 disabled:opacity-60 text-sm"
							onClick={tbResetDefaults}
							disabled={tbProcessing}
							title="Restore the original 14 time windows for all days"
						>
							<svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
								<path d="M17.65 6.35A7.958 7.958 0 0012 4c-4.42 0-7.99 3.58-7.99 8s3.57 8 7.99 8c3.73 0 6.84-2.55 7.73-6h-2.08A5.99 5.99 0 0112 18c-3.31 0-6-2.69-6-6s2.69-6 6-6c1.66 0 3.14.69 4.22 1.78L13 11h7V4l-2.35 2.35z" />
							</svg>
							Reset Defaults
						</button>
						<button
							className="px-3 py-2 rounded bg-royal text-white flex items-center gap-2 disabled:opacity-60 text-sm"
							onClick={tbOpenAdd}
							disabled={tbProcessing}
						>
							<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-4 h-4">
								<path d="M11 11V5h2v6h6v2h-6v6h-2v-6H5v-2h6z" />
							</svg>
							Add Time Slot
						</button>
					</div>
				</div>

				{/* Day filter tabs */}
				<div className="flex gap-1 mb-3 flex-wrap">
					<button
						className={`px-3 py-1.5 rounded-full text-xs font-semibold transition-colors ${
							tbActiveDay === null
								? 'bg-navy text-white'
								: 'bg-gray-100 text-gray-600 hover:bg-gray-200'
						}`}
						onClick={() => setTbActiveDay(null)}
					>
						All
					</button>
					{days.map(d => (
						<button
							key={d.id}
							className={`px-3 py-1.5 rounded-full text-xs font-semibold transition-colors ${
								tbActiveDay === d.id
									? 'bg-navy text-white'
									: 'bg-gray-100 text-gray-600 hover:bg-gray-200'
							}`}
							onClick={() => setTbActiveDay(d.id)}
						>
							{d.label}
						</button>
					))}
				</div>

				<div className="bg-gray-50 rounded-lg border border-gray-200 p-4">
					<div className="text-xs text-gray-400 mb-3">
						<strong>{timeBlocks.length}</strong> total time blocks across <strong>{days.length}</strong> days.
						{tbActiveDay !== null && (
							<> Showing <strong>{filteredBlocks.length}</strong> blocks for <strong>{dayMap[tbActiveDay] || '—'}</strong>.</>
						)}
					</div>

					{(lecBlocks.length === 0 && labBlocks.length === 0) ? (
						<div className="text-center text-gray-400 py-6">
							No time slots configured. Click "Add Time Slot" or "Reset Defaults" to get started.
						</div>
					) : (
						<div className="space-y-4">
							{/* ── Lecture Slots ── */}
							{lecBlocks.length > 0 && (
								<div>
									<div className="flex items-center gap-2 mb-2">
										<span className="inline-block px-2.5 py-1 rounded-full text-xs font-bold bg-blue-100 text-blue-700">LEC</span>
										<span className="text-sm font-semibold text-navy">Lecture Slots</span>
										<span className="text-xs text-gray-400">({lecBlocks.length})</span>
									</div>
									<div className="overflow-x-auto">
										<table className="w-full text-sm">
											<thead>
												<tr className="text-left text-xs text-gray-500 border-b border-blue-200 bg-blue-50/50">
													<th className="py-2 px-3 font-semibold">Time Range</th>
													<th className="py-2 px-3 font-semibold">Duration</th>
													{tbActiveDay === null && <th className="py-2 px-3 font-semibold">Days</th>}
													<th className="py-2 px-3 font-semibold text-right">Actions</th>
												</tr>
											</thead>
											<tbody>
												{lecBlocks.map((tb, idx) => {
													const dayIds = tb._dayIds || [tb.day_id]
													return (
														<tr key={tb.block_id || `lec-${idx}`} className="border-b border-gray-100 hover:bg-blue-50/30 transition-colors">
															<td className="py-2.5 px-3">
																<span className="font-medium text-navy">
																	{formatTo12Hour(tb.start_time)} – {formatTo12Hour(tb.end_time)}
																</span>
																<span className="text-xs text-gray-400 ml-2">({tb.start_time}–{tb.end_time})</span>
															</td>
															<td className="py-2.5 px-3 text-gray-600">{getDuration(tb.start_min, tb.end_min)}</td>
															{tbActiveDay === null && (
																<td className="py-2.5 px-3">
																	<div className="flex gap-1 flex-wrap">
																		{dayIds.sort((a, b) => a - b).map(id => (
																			<span key={id} className="inline-block px-1.5 py-0.5 rounded bg-gray-200 text-gray-700 text-xs font-medium">{dayMap[id] || '?'}</span>
																		))}
																	</div>
																</td>
															)}
															<td className="py-2.5 px-3 text-right">
																<div className="flex items-center justify-end gap-1.5">
																	{tbActiveDay !== null && (
																		<button className="inline-flex items-center justify-center w-7 h-7 rounded-full bg-blue-600 hover:opacity-90 text-white" title="Edit" onClick={() => tbOpenEdit(tb)}>
																			<svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="currentColor"><path d="M3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25zM20.71 7.04a1 1 0 000-1.41l-2.34-2.34a1 1 0 00-1.41 0l-1.83 1.83 3.75 3.75 1.83-1.83z" /></svg>
																		</button>
																	)}
																	<button className="inline-flex items-center justify-center w-7 h-7 rounded-full bg-red-600 hover:opacity-90 text-white" title="Delete" onClick={() => {
																		const ids = tb._blockIds || [tb.block_id]
																		if (ids.length > 1) {
																			if (!confirm(`Delete this time slot from ${ids.length} days?`)) return
																			Promise.all(ids.map(id => fetch(`${API}/time-blocks/${id}`, { method: 'DELETE' }))).then(() => loadTimeBlocks())
																		} else { tbOnDelete(ids[0]) }
																	}}>
																		<svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="currentColor"><path d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z" /></svg>
																	</button>
																</div>
															</td>
														</tr>
													)
												})}
											</tbody>
										</table>
									</div>
								</div>
							)}

							{/* ── Laboratory Slots ── */}
							{labBlocks.length > 0 && (
								<div>
									<div className="flex items-center gap-2 mb-2">
										<span className="inline-block px-2.5 py-1 rounded-full text-xs font-bold bg-purple-100 text-purple-700">LAB</span>
										<span className="text-sm font-semibold text-navy">Laboratory Slots</span>
										<span className="text-xs text-gray-400">({labBlocks.length})</span>
									</div>
									<div className="overflow-x-auto">
										<table className="w-full text-sm">
											<thead>
												<tr className="text-left text-xs text-gray-500 border-b border-purple-200 bg-purple-50/50">
													<th className="py-2 px-3 font-semibold">Time Range</th>
													<th className="py-2 px-3 font-semibold">Duration</th>
													{tbActiveDay === null && <th className="py-2 px-3 font-semibold">Days</th>}
													<th className="py-2 px-3 font-semibold text-right">Actions</th>
												</tr>
											</thead>
											<tbody>
												{labBlocks.map((tb, idx) => {
													const dayIds = tb._dayIds || [tb.day_id]
													return (
														<tr key={tb.block_id || `lab-${idx}`} className="border-b border-gray-100 hover:bg-purple-50/30 transition-colors">
															<td className="py-2.5 px-3">
																<span className="font-medium text-navy">
																	{formatTo12Hour(tb.start_time)} – {formatTo12Hour(tb.end_time)}
																</span>
																<span className="text-xs text-gray-400 ml-2">({tb.start_time}–{tb.end_time})</span>
															</td>
															<td className="py-2.5 px-3 text-gray-600">{getDuration(tb.start_min, tb.end_min)}</td>
															{tbActiveDay === null && (
																<td className="py-2.5 px-3">
																	<div className="flex gap-1 flex-wrap">
																		{dayIds.sort((a, b) => a - b).map(id => (
																			<span key={id} className="inline-block px-1.5 py-0.5 rounded bg-gray-200 text-gray-700 text-xs font-medium">{dayMap[id] || '?'}</span>
																		))}
																	</div>
																</td>
															)}
															<td className="py-2.5 px-3 text-right">
																<div className="flex items-center justify-end gap-1.5">
																	{tbActiveDay !== null && (
																		<button className="inline-flex items-center justify-center w-7 h-7 rounded-full bg-blue-600 hover:opacity-90 text-white" title="Edit" onClick={() => tbOpenEdit(tb)}>
																			<svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="currentColor"><path d="M3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25zM20.71 7.04a1 1 0 000-1.41l-2.34-2.34a1 1 0 00-1.41 0l-1.83 1.83 3.75 3.75 1.83-1.83z" /></svg>
																		</button>
																	)}
																	<button className="inline-flex items-center justify-center w-7 h-7 rounded-full bg-red-600 hover:opacity-90 text-white" title="Delete" onClick={() => {
																		const ids = tb._blockIds || [tb.block_id]
																		if (ids.length > 1) {
																			if (!confirm(`Delete this time slot from ${ids.length} days?`)) return
																			Promise.all(ids.map(id => fetch(`${API}/time-blocks/${id}`, { method: 'DELETE' }))).then(() => loadTimeBlocks())
																		} else { tbOnDelete(ids[0]) }
																	}}>
																		<svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="currentColor"><path d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z" /></svg>
																	</button>
																</div>
															</td>
														</tr>
													)
												})}
											</tbody>
										</table>
									</div>
								</div>
							)}
						</div>
					)}
				</div>
			</div>

			{/* Time Block Modal */}
			{tbShow && (
				<div className="fixed inset-0 bg-black/30 flex items-center justify-center p-4 z-50">
					<form onSubmit={tbOnSave} className="w-full max-w-md bg-white rounded-xl shadow p-5 space-y-4">
						<div className="text-lg font-semibold text-navy">
							{tbEditing ? 'Edit Time Slot' : 'Add Time Slot'}
						</div>

						{/* Day selection (multi-select for add, single for edit) */}
						{!tbEditing && (
							<div>
								<label className="block text-sm text-gray-600 mb-2">Apply to Days</label>
								<div className="flex gap-2 flex-wrap">
									{days.map(d => (
										<label
											key={d.id}
											className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg border cursor-pointer text-sm transition-colors ${
												tbSelectedDays.includes(d.id)
													? 'bg-navy text-white border-navy'
													: 'bg-white text-gray-600 border-gray-300 hover:border-navy'
											}`}
										>
											<input
												type="checkbox"
												className="sr-only"
												checked={tbSelectedDays.includes(d.id)}
												onChange={() => toggleDay(d.id)}
											/>
											{d.label}
										</label>
									))}
								</div>
								{days.length > 1 && (
									<div className="flex gap-2 mt-2">
										<button type="button" className="text-xs text-blue-600 hover:underline" onClick={() => setTbSelectedDays(days.map(d => d.id))}>Select All</button>
										<button type="button" className="text-xs text-blue-600 hover:underline" onClick={() => setTbSelectedDays([])}>Clear</button>
									</div>
								)}
							</div>
						)}

						{tbEditing && (
							<div className="text-sm text-gray-500">
								Day: <strong>{dayMap[tbEditing.day_id] || '—'}</strong>
							</div>
						)}

						{/* Time pickers */}
						<div className="grid grid-cols-2 gap-3">
							<div>
								<label className="block text-sm text-gray-600 mb-1">Start Time</label>
								<input
									type="time"
									className="w-full px-3 py-2 rounded border"
									value={tbStartTime}
									onChange={(e) => setTbStartTime(e.target.value)}
								/>
								{tbStartTime && (
									<p className="text-xs text-gray-400 mt-1">{formatTo12Hour(tbStartTime)}</p>
								)}
							</div>
							<div>
								<label className="block text-sm text-gray-600 mb-1">End Time</label>
								<input
									type="time"
									className="w-full px-3 py-2 rounded border"
									value={tbEndTime}
									onChange={(e) => setTbEndTime(e.target.value)}
								/>
								{tbEndTime && (
									<p className="text-xs text-gray-400 mt-1">{formatTo12Hour(tbEndTime)}</p>
								)}
							</div>
						</div>

						{/* Duration preview */}
						{tbStartTime && tbEndTime && tbStartTime < tbEndTime && (() => {
							const [sh, sm] = tbStartTime.split(':').map(Number)
							const [eh, em] = tbEndTime.split(':').map(Number)
							const sMin = sh * 60 + sm
							const eMin = eh * 60 + em
							return (
								<div className="text-xs text-gray-500 bg-gray-50 rounded px-3 py-2">
									Duration: <strong>{getDuration(sMin, eMin)}</strong>
								</div>
							)
						})()}

						{/* Lab toggle */}
						<label className="flex items-center gap-2 cursor-pointer">
							<input
								type="checkbox"
								className="w-4 h-4 rounded border-gray-300 text-purple-600 focus:ring-purple-500"
								checked={tbIsLab}
								onChange={(e) => setTbIsLab(e.target.checked)}
							/>
							<span className="text-sm text-gray-700">
								Laboratory slot
								<span className="text-xs text-gray-400 ml-1">(1.5-hour slots for LAB subjects)</span>
							</span>
						</label>

						{tbError && <div className="text-sm text-red-600">{tbError}</div>}

						<div className="flex justify-end gap-2 pt-2">
							<button type="button" className="px-3 py-2 rounded border" onClick={() => setTbShow(false)} disabled={tbProcessing}>
								Cancel
							</button>
							<button className="px-3 py-2 rounded bg-royal text-white disabled:opacity-60" disabled={tbProcessing}>
								{tbEditing ? 'Update' : 'Add'}
							</button>
						</div>
					</form>
				</div>
			)}
		</div>
	)
}
