import { useEffect, useState, useRef, useMemo } from 'react'
import { useLocation } from 'react-router-dom'

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

	// ─── Day Patterns state ───
	const [dayPatterns, setDayPatterns] = useState([])
	const [dpShow, setDpShow] = useState(false)
	const [dpEditing, setDpEditing] = useState(null)
	const [dpName, setDpName] = useState('')
	const [dpSelectedDays, setDpSelectedDays] = useState([])
	const [dpAppliesTo, setDpAppliesTo] = useState('ALL')
	const [dpIsActive, setDpIsActive] = useState(true)
	const [dpError, setDpError] = useState('')
	const [dpProcessing, setDpProcessing] = useState(false)

	// ─── System Settings state ───
	const [sysSettings, setSysSettings] = useState({})

	// ─── Accordion section state ───
	const location = useLocation()
	const hash = location.hash?.replace('#', '') || 'load-limits'
	const [openSection, setOpenSection] = useState(hash)
	const [sysProcessing, setSysProcessing] = useState(false)

	// ─── Confirmation Modal state ───
	const [confirmModal, setConfirmModal] = useState(null) // { title, message, type, onConfirm }

	function showConfirm({ title, message, type = 'danger', confirmLabel = 'Confirm', onConfirm }) {
		setConfirmModal({ title, message, type, confirmLabel, onConfirm })
	}

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

	// ─── Load day patterns ───
	async function loadDayPatterns() {
		try {
			const res = await fetch(`${API}/day-patterns`)
			if (res.ok) setDayPatterns(await res.json())
		} catch (e) {
			console.error('Failed to load day patterns', e)
		}
	}

	async function loadSystemSettings() {
		try {
			const res = await fetch(`${API}/system-settings`)
			if (res.ok) {
				const list = await res.json()
				const map = {}
				for (const s of list) map[s.key] = s.value
				setSysSettings(map)
			}
		} catch (e) {
			console.error('Failed to load system settings', e)
		}
	}

	async function saveSystemSetting(key, value) {
		try {
			setSysProcessing(true)
			const res = await fetch(`${API}/system-settings/${key}`, {
				method: 'PUT',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ value: String(value) }),
			})
			if (res.ok) {
				setSysSettings(prev => ({ ...prev, [key]: String(value) }))
			}
		} catch (e) {
			console.error('Failed to save setting', e)
		} finally {
			setSysProcessing(false)
		}
	}

	useEffect(() => {
		if (!loadedRef.current) {
			loadedRef.current = true
			load()
			loadTimeBlocks()
			loadDayPatterns()
			loadSystemSettings()
		}
	}, [])

	// Sync accordion open section from hash
	useEffect(() => {
		const h = location.hash?.replace('#', '')
		if (h) {
			setOpenSection(h)
			setTimeout(() => {
				document.getElementById(h)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
			}, 100)
		}
	}, [location.hash])

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
		showConfirm({
			title: 'Delete Designation',
			message: 'Are you sure you want to delete this designation deduction? This action cannot be undone.',
			type: 'danger',
			confirmLabel: 'Delete',
			onConfirm: async () => {
				try {
					setProcessing(true)
					await fetch(`${API}/designation-deductions/${id}`, { method: 'DELETE' })
					await load()
				} catch (err) {
					showConfirm({ title: 'Error', message: err.message || 'Failed to delete', type: 'warning', confirmLabel: 'OK', onConfirm: () => {} })
				} finally {
					setProcessing(false)
				}
			}
		})
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
		showConfirm({
			title: 'Delete Time Slot',
			message: 'Are you sure you want to delete this time slot? This may affect existing schedules.',
			type: 'danger',
			confirmLabel: 'Delete',
			onConfirm: async () => {
				try {
					setTbProcessing(true)
					await fetch(`${API}/time-blocks/${blockId}`, { method: 'DELETE' })
					await loadTimeBlocks()
				} catch (err) {
					showConfirm({ title: 'Error', message: err.message || 'Failed to delete', type: 'warning', confirmLabel: 'OK', onConfirm: () => {} })
				} finally {
					setTbProcessing(false)
				}
			}
		})
	}

	async function tbResetDefaults() {
		if (tbProcessing) return
		showConfirm({
			title: 'Reset Time Slots',
			message: 'This will delete ALL current time slots and restore the 14 default registrar windows for every day. This action cannot be undone.',
			type: 'warning',
			confirmLabel: 'Reset All',
			onConfirm: async () => {
				try {
					setTbProcessing(true)
					const res = await fetch(`${API}/time-blocks/reset-defaults`, { method: 'POST' })
					if (!res.ok) {
						const data = await res.json().catch(() => ({}))
						throw new Error(data.detail || 'Failed to reset')
					}
					await loadTimeBlocks()
				} catch (err) {
					showConfirm({ title: 'Error', message: err.message || 'Failed to reset', type: 'warning', confirmLabel: 'OK', onConfirm: () => {} })
				} finally {
					setTbProcessing(false)
				}
			}
		})
	}

	function toggleDay(dayId) {
		setTbSelectedDays(prev =>
			prev.includes(dayId) ? prev.filter(id => id !== dayId) : [...prev, dayId]
		)
	}

	// ─── Day Pattern handlers ───
	function dpOpenAdd() {
		setDpEditing(null)
		setDpName('')
		setDpSelectedDays([])
		setDpAppliesTo('ALL')
		setDpIsActive(true)
		setDpError('')
		setDpShow(true)
	}

	function dpOpenEdit(p) {
		setDpEditing(p)
		setDpName(p.name)
		setDpSelectedDays(p.day_ids.split(',').map(Number).filter(Boolean))
		setDpAppliesTo(p.applies_to || 'ALL')
		setDpIsActive(p.is_active)
		setDpError('')
		setDpShow(true)
	}

	async function dpOnSave(e) {
		e.preventDefault()
		if (dpProcessing) return
		if (!dpName.trim()) { setDpError('Pattern name is required'); return }
		if (dpSelectedDays.length === 0) { setDpError('Select at least one day'); return }

		try {
			setDpProcessing(true)
			const body = {
				name: dpName.trim(),
				day_ids: dpSelectedDays.join(','),
				applies_to: dpAppliesTo,
				is_active: dpIsActive,
			}

			if (dpEditing) {
				const res = await fetch(`${API}/day-patterns/${dpEditing.id}`, {
					method: 'PUT',
					headers: { 'Content-Type': 'application/json' },
					body: JSON.stringify(body),
				})
				if (!res.ok) {
					const data = await res.json().catch(() => ({}))
					throw new Error(data.detail || 'Failed to update')
				}
			} else {
				body.priority = dayPatterns.length // append at end
				const res = await fetch(`${API}/day-patterns`, {
					method: 'POST',
					headers: { 'Content-Type': 'application/json' },
					body: JSON.stringify(body),
				})
				if (!res.ok) {
					const data = await res.json().catch(() => ({}))
					throw new Error(data.detail || 'Failed to create')
				}
			}

			setDpShow(false)
			await loadDayPatterns()
		} catch (err) {
			setDpError(err.message || 'Failed to save')
		} finally {
			setDpProcessing(false)
		}
	}

	async function dpOnDelete(id) {
		if (dpProcessing) return
		showConfirm({
			title: 'Delete Day Pattern',
			message: 'Are you sure you want to delete this day pattern? The scheduler will no longer use it.',
			type: 'danger',
			confirmLabel: 'Delete',
			onConfirm: async () => {
				try {
					setDpProcessing(true)
					await fetch(`${API}/day-patterns/${id}`, { method: 'DELETE' })
					await loadDayPatterns()
				} catch (err) {
					showConfirm({ title: 'Error', message: err.message || 'Failed to delete', type: 'warning', confirmLabel: 'OK', onConfirm: () => {} })
				} finally {
					setDpProcessing(false)
				}
			}
		})
	}

	async function dpResetDefaults() {
		if (dpProcessing) return
		showConfirm({
			title: 'Reset Day Patterns',
			message: 'This will delete ALL current patterns and restore the default M-W, T-TH, F patterns. Any custom patterns will be lost.',
			type: 'warning',
			confirmLabel: 'Reset All',
			onConfirm: async () => {
				try {
					setDpProcessing(true)
					const res = await fetch(`${API}/day-patterns/reset-defaults`, { method: 'POST' })
					if (!res.ok) throw new Error('Failed to reset')
					await loadDayPatterns()
				} catch (err) {
					showConfirm({ title: 'Error', message: err.message || 'Failed to reset', type: 'warning', confirmLabel: 'OK', onConfirm: () => {} })
				} finally {
					setDpProcessing(false)
				}
			}
		})
	}

	async function dpMovePriority(id, direction) {
		const idx = dayPatterns.findIndex(p => p.id === id)
		if (idx < 0) return
		const newIdx = idx + direction
		if (newIdx < 0 || newIdx >= dayPatterns.length) return

		const reordered = [...dayPatterns]
		const [item] = reordered.splice(idx, 1)
		reordered.splice(newIdx, 0, item)

		try {
			setDpProcessing(true)
			const res = await fetch(`${API}/day-patterns/reorder`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ ordered_ids: reordered.map(p => p.id) }),
			})
			if (res.ok) setDayPatterns(await res.json())
		} catch (err) {
			console.error('Failed to reorder', err)
		} finally {
			setDpProcessing(false)
		}
	}

	async function dpToggleActive(p) {
		try {
			setDpProcessing(true)
			const res = await fetch(`${API}/day-patterns/${p.id}`, {
				method: 'PUT',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ is_active: !p.is_active }),
			})
			if (res.ok) await loadDayPatterns()
		} catch (err) {
			console.error('Failed to toggle', err)
		} finally {
			setDpProcessing(false)
		}
	}

	function dpToggleDay(dayId) {
		setDpSelectedDays(prev =>
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

	const toggleSection = (id) => setOpenSection(prev => prev === id ? null : id)

	const AccSection = ({ id, title, desc, actions, children }) => {
		const isOpen = openSection === id
		return (
			<div id={id} className="mb-3 border border-gray-200 rounded-xl overflow-hidden bg-white shadow-sm">
				<button
					onClick={() => toggleSection(id)}
					className="w-full flex items-center justify-between px-5 py-4 bg-gray-50 hover:bg-gray-100 transition-colors"
				>
					<div className="text-left">
						<h2 className="text-navy text-lg font-semibold">{title}</h2>
						{desc && <p className="text-xs text-gray-400 mt-0.5">{desc}</p>}
					</div>
					<div className="flex items-center gap-3">
						{!isOpen && actions}
						<svg className={`w-5 h-5 text-gray-400 transition-transform duration-200 ${isOpen ? 'rotate-180' : ''}`} viewBox="0 0 24 24" fill="currentColor">
							<path d="M7.41 8.59L12 13.17l4.59-4.58L18 10l-6 6-6-6z"/>
						</svg>
					</div>
				</button>
				<div className={`transition-all duration-300 ${isOpen ? 'max-h-[3000px] opacity-100' : 'max-h-0 opacity-0 overflow-hidden'}`}>
					<div className="p-5 border-t border-gray-100">
						{isOpen && actions && <div className="flex justify-end gap-2 mb-4">{actions}</div>}
						{children}
					</div>
				</div>
			</div>
		)
	}

	return (
		<div>
			<h1 className="text-navy text-3xl font-semibold mb-6">Settings</h1>

			<AccSection id="load-limits" title="Instructor Load Limits" desc="Configure the base weekly hour limits for regular and visiting instructors.">
				<div className="bg-gray-50 rounded-lg border border-gray-200 p-5">
					<div className="grid grid-cols-1 md:grid-cols-2 gap-6">
						{/* Regular */}
						<div className="flex items-center gap-4">
							<div className="w-12 h-12 rounded-full bg-blue-100 flex items-center justify-center flex-shrink-0">
								<svg className="w-6 h-6 text-blue-600" viewBox="0 0 24 24" fill="currentColor"><path d="M12 12c2.761 0 5-2.239 5-5s-2.239-5-5-5-5 2.239-5 5 2.239 5 5 5zm0 2c-3.866 0-7 3.134-7 7h2a5 5 0 0110 0h2c0-3.866-3.134-7-7-7z"/></svg>
							</div>
							<div className="flex-1">
								<label className="text-sm font-semibold text-gray-700">Regular Instructor Base</label>
								<p className="text-xs text-gray-400">Before designation deductions</p>
							</div>
							<div className="flex items-center gap-2">
								<input
									type="number"
									min="1" max="60"
									className="w-20 border border-gray-300 rounded-lg px-3 py-2 text-center font-bold text-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
									value={sysSettings.regular_base_hours || '24'}
									onChange={e => setSysSettings(prev => ({ ...prev, regular_base_hours: e.target.value }))}
									onBlur={e => saveSystemSetting('regular_base_hours', e.target.value)}
									disabled={sysProcessing}
								/>
								<span className="text-sm text-gray-500 font-medium">hrs</span>
							</div>
						</div>
						{/* Visiting */}
						<div className="flex items-center gap-4">
							<div className="w-12 h-12 rounded-full bg-amber-100 flex items-center justify-center flex-shrink-0">
								<svg className="w-6 h-6 text-amber-600" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 17.93c-3.95-.49-7-3.85-7-7.93 0-.62.08-1.21.21-1.79L9 15v1c0 1.1.9 2 2 2v1.93zm6.9-2.54c-.26-.81-1-1.39-1.9-1.39h-1v-3c0-.55-.45-1-1-1H8v-2h2c.55 0 1-.45 1-1V7h2c1.1 0 2-.9 2-2v-.41c2.93 1.19 5 4.06 5 7.41 0 2.08-.8 3.97-2.1 5.39z"/></svg>
							</div>
							<div className="flex-1">
								<label className="text-sm font-semibold text-gray-700">Visiting Lecturer Limit</label>
								<p className="text-xs text-gray-400">No deduction applied</p>
							</div>
							<div className="flex items-center gap-2">
								<input
									type="number"
									min="1" max="60"
									className="w-20 border border-gray-300 rounded-lg px-3 py-2 text-center font-bold text-lg focus:ring-2 focus:ring-amber-500 focus:border-amber-500"
									value={sysSettings.visiting_base_hours || '30'}
									onChange={e => setSysSettings(prev => ({ ...prev, visiting_base_hours: e.target.value }))}
									onBlur={e => saveSystemSetting('visiting_base_hours', e.target.value)}
									disabled={sysProcessing}
								/>
								<span className="text-sm text-gray-500 font-medium">hrs</span>
							</div>
						</div>
					</div>
				</div>
			</AccSection>

			<AccSection id="deductions" title="Designation Deductions" desc="Configure designation-based hour deductions from the base weekly limit." actions={<>					<button
						className="px-3 py-2 rounded bg-royal text-white flex items-center gap-2 disabled:opacity-60 text-sm"
						onClick={openAdd}
						disabled={processing}
					>
						<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-4 h-4">
							<path d="M11 11V5h2v6h6v2h-6v6h-2v-6H5v-2h6z" />
						</svg>
						Add Designation
					</button>
</>}>

				<div className="bg-gray-50 rounded-lg border border-gray-200 p-4">
					<div className="text-xs text-gray-400 mb-3">
						<strong>Regular</strong> instructors base limit = <strong>{sysSettings.regular_base_hours || '24'} hrs</strong> — deduction.
						&nbsp;|&nbsp;
						<strong>Visiting</strong> lecturers always = <strong>{sysSettings.visiting_base_hours || '30'} hrs</strong> (no deduction applied).
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
			</AccSection>

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

			<AccSection id="day-patterns" title="Day Patterns" desc="Configure which day combinations the scheduler uses." actions={<>						<button
							className="px-3 py-2 rounded border border-gray-300 text-sm flex items-center gap-1 hover:bg-gray-50 disabled:opacity-60"
							onClick={dpResetDefaults}
							disabled={dpProcessing}
						>
							<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-4 h-4"><path d="M17.65 6.35A7.96 7.96 0 0 0 12 4a8 8 0 1 0 8 8h-2a6 6 0 1 1-1.76-4.24L14 10h7V3l-3.35 3.35z"/></svg>
							Reset Defaults
						</button>
						<button
							className="px-3 py-2 rounded bg-royal text-white flex items-center gap-2 disabled:opacity-60 text-sm"
							onClick={dpOpenAdd}
							disabled={dpProcessing}
						>
							<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-4 h-4"><path d="M11 11V5h2v6h6v2h-6v6h-2v-6H5v-2h6z" /></svg>
							Add Pattern
						</button>
</>}>

				{dayPatterns.length === 0 ? (
					<div className="text-center text-gray-400 py-6 bg-gray-50 rounded-lg border border-gray-200">
						No day patterns configured. Click "Reset Defaults" to create M-W, T-TH, F patterns.
					</div>
				) : (
					<div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
						<table className="w-full text-sm">
							<thead>
								<tr className="bg-navy text-white text-left">
									<th className="px-3 py-2 w-12">#</th>
									<th className="px-3 py-2">Pattern Name</th>
									<th className="px-3 py-2">Days</th>
									<th className="px-3 py-2 w-20">Type</th>
									<th className="px-3 py-2 w-20">Paired</th>
									<th className="px-3 py-2 w-20">Active</th>
									<th className="px-3 py-2 w-24">Priority</th>
									<th className="px-3 py-2 text-right w-28">Actions</th>
								</tr>
							</thead>
							<tbody>
								{dayPatterns.map((p, idx) => {
									const patternDayIds = p.day_ids.split(',').map(Number).filter(Boolean)
									const patternDayLabels = patternDayIds.map(id => dayMap[id] || `?${id}`)
									const isPaired = patternDayIds.length >= 2

									return (
										<tr key={p.id} className={`border-t border-gray-100 ${!p.is_active ? 'opacity-50' : ''} hover:bg-gray-50`}>
											<td className="px-3 py-2 text-gray-400 font-mono">{idx + 1}</td>
											<td className="px-3 py-2 font-semibold text-navy">{p.name}</td>
											<td className="px-3 py-2">
												<div className="flex gap-1 flex-wrap">
													{patternDayLabels.map((lbl, i) => (
														<span key={i} className="inline-block px-2 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
															{lbl}
														</span>
													))}
												</div>
											</td>
											<td className="px-3 py-2">
												<span className={`text-xs font-medium px-2 py-0.5 rounded ${
													p.applies_to === 'LEC' ? 'bg-green-100 text-green-700' :
													p.applies_to === 'LAB' ? 'bg-purple-100 text-purple-700' :
													'bg-gray-100 text-gray-600'
												}`}>
													{p.applies_to}
												</span>
											</td>
											<td className="px-3 py-2">
												{isPaired ? (
													<span className="text-xs text-blue-600 font-medium">🔗 Paired</span>
												) : (
													<span className="text-xs text-gray-500">Single</span>
												)}
											</td>
											<td className="px-3 py-2">
												<button
													className={`w-10 h-5 rounded-full relative transition-colors ${p.is_active ? 'bg-green-500' : 'bg-gray-300'}`}
													onClick={() => dpToggleActive(p)}
													disabled={dpProcessing}
												>
													<span className={`absolute top-0.5 w-4 h-4 bg-white rounded-full shadow transition-transform ${p.is_active ? 'left-5' : 'left-0.5'}`} />
												</button>
											</td>
											<td className="px-3 py-2">
												<div className="flex gap-1">
													<button
														className="w-6 h-6 rounded bg-gray-100 hover:bg-gray-200 flex items-center justify-center text-xs disabled:opacity-30"
														onClick={() => dpMovePriority(p.id, -1)}
														disabled={idx === 0 || dpProcessing}
														title="Move up (higher priority)"
													>
														▲
													</button>
													<button
														className="w-6 h-6 rounded bg-gray-100 hover:bg-gray-200 flex items-center justify-center text-xs disabled:opacity-30"
														onClick={() => dpMovePriority(p.id, 1)}
														disabled={idx === dayPatterns.length - 1 || dpProcessing}
														title="Move down (lower priority)"
													>
														▼
													</button>
												</div>
											</td>
											<td className="px-3 py-2 text-right">
												<div className="flex justify-end gap-1">
													<button
														className="w-7 h-7 rounded-full bg-royal text-white flex items-center justify-center hover:bg-blue-700"
														onClick={() => dpOpenEdit(p)}
														title="Edit"
													>
														<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-3.5 h-3.5"><path d="M3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25zM20.71 7.04a1 1 0 0 0 0-1.41l-2.34-2.34a1 1 0 0 0-1.41 0l-1.83 1.83 3.75 3.75 1.83-1.83z"/></svg>
													</button>
													<button
														className="w-7 h-7 rounded-full bg-red-600 text-white flex items-center justify-center hover:bg-red-700"
														onClick={() => dpOnDelete(p.id)}
														title="Delete"
													>
														<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-3.5 h-3.5"><path d="M6 19c0 1.1.9 2 2 2h8a2 2 0 0 0 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z"/></svg>
													</button>
												</div>
											</td>
										</tr>
									)
								})}
							</tbody>
						</table>
					</div>
				)}
			</AccSection>

			{/* Day Pattern Modal */}
			{dpShow && (
				<div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50" onClick={() => setDpShow(false)}>
					<form
						className="bg-white p-6 rounded-xl shadow-lg w-full max-w-md space-y-3"
						onClick={e => e.stopPropagation()}
						onSubmit={dpOnSave}
					>
						<div className="text-lg font-semibold text-navy">{dpEditing ? 'Edit Pattern' : 'Add Day Pattern'}</div>
						<input
							className="w-full px-3 py-2 rounded border"
							placeholder="Pattern name (e.g. M-W, SAT-SUN)"
							value={dpName}
							onChange={e => setDpName(e.target.value)}
						/>

						<div>
							<label className="block text-sm text-gray-600 mb-1">Select Days</label>
							<div className="flex gap-2 flex-wrap">
								{days.map(d => (
									<button
										type="button"
										key={d.id}
										className={`px-3 py-1.5 rounded-full text-sm font-medium border transition-colors ${
											dpSelectedDays.includes(d.id)
												? 'bg-royal text-white border-royal'
												: 'bg-white text-gray-600 border-gray-300 hover:border-royal'
										}`}
										onClick={() => dpToggleDay(d.id)}
									>
										{d.label}
									</button>
								))}
							</div>
							{dpSelectedDays.length >= 2 && (
								<p className="text-xs text-blue-500 mt-1">🔗 This will be a paired pattern — subject meets on all selected days at the same time.</p>
							)}
						</div>

						<div>
							<label className="block text-sm text-gray-600 mb-1">Applies To</label>
							<div className="flex gap-2">
								{['ALL', 'LEC', 'LAB'].map(opt => (
									<button
										type="button"
										key={opt}
										className={`px-3 py-1.5 rounded text-sm font-medium border transition-colors ${
											dpAppliesTo === opt
												? 'bg-navy text-white border-navy'
												: 'bg-white text-gray-600 border-gray-300 hover:border-navy'
										}`}
										onClick={() => setDpAppliesTo(opt)}
									>
										{opt}
									</button>
								))}
							</div>
						</div>

						<label className="flex items-center gap-2 text-sm">
							<input type="checkbox" checked={dpIsActive} onChange={e => setDpIsActive(e.target.checked)} />
							Active (scheduler will use this pattern)
						</label>

						{dpError && <div className="text-sm text-red-600">{dpError}</div>}
						<div className="flex justify-end gap-2 pt-2">
							<button type="button" className="px-3 py-2 rounded border" onClick={() => setDpShow(false)} disabled={dpProcessing}>Cancel</button>
							<button className="px-3 py-2 rounded bg-royal text-white disabled:opacity-60" disabled={dpProcessing}>Save</button>
						</div>
					</form>
				</div>
			)}

			<AccSection id="timeslots" title="Time Slots" desc="Configure the time windows available for scheduling classes." actions={<>						<button
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
</>}>

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
																			showConfirm({
																				title: 'Delete Time Slot',
																				message: `This will delete this time slot from ${ids.length} days. Continue?`,
																				type: 'danger',
																				confirmLabel: 'Delete All',
																				onConfirm: async () => { await Promise.all(ids.map(id => fetch(`${API}/time-blocks/${id}`, { method: 'DELETE' }))); await loadTimeBlocks() }
																			})
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
																			showConfirm({
																				title: 'Delete Time Slot',
																				message: `This will delete this time slot from ${ids.length} days. Continue?`,
																				type: 'danger',
																				confirmLabel: 'Delete All',
																				onConfirm: async () => { await Promise.all(ids.map(id => fetch(`${API}/time-blocks/${id}`, { method: 'DELETE' }))); await loadTimeBlocks() }
																			})
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
			</AccSection>

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
			{/* ══════════════════════════════════════════════════════════════════
			    Confirmation Modal
			    ══════════════════════════════════════════════════════════════════ */}
			{confirmModal && (
				<div className="fixed inset-0 bg-black/50 flex items-center justify-center z-[60]" onClick={() => setConfirmModal(null)}>
					<div
						className="bg-white rounded-xl shadow-2xl w-full max-w-sm p-6 space-y-4 animate-[fadeIn_0.15s_ease-out]"
						onClick={e => e.stopPropagation()}
					>
						{/* Icon */}
						<div className="flex justify-center">
							{confirmModal.type === 'danger' ? (
								<div className="w-14 h-14 rounded-full bg-red-100 flex items-center justify-center">
									<svg className="w-7 h-7 text-red-600" viewBox="0 0 24 24" fill="currentColor"><path d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z"/></svg>
								</div>
							) : (
								<div className="w-14 h-14 rounded-full bg-amber-100 flex items-center justify-center">
									<svg className="w-7 h-7 text-amber-600" viewBox="0 0 24 24" fill="currentColor"><path d="M1 21h22L12 2 1 21zm12-3h-2v-2h2v2zm0-4h-2v-4h2v4z"/></svg>
								</div>
							)}
						</div>

						{/* Title & Message */}
						<div className="text-center">
							<h3 className="text-lg font-bold text-gray-900">{confirmModal.title}</h3>
							<p className="text-sm text-gray-500 mt-2 leading-relaxed">{confirmModal.message}</p>
						</div>

						{/* Buttons */}
						<div className="flex gap-3 pt-2">
							<button
								className="flex-1 px-4 py-2.5 rounded-lg border border-gray-300 text-gray-700 font-medium hover:bg-gray-50 transition-colors"
								onClick={() => setConfirmModal(null)}
							>
								Cancel
							</button>
							<button
								className={`flex-1 px-4 py-2.5 rounded-lg text-white font-medium transition-colors ${
									confirmModal.type === 'danger'
										? 'bg-red-600 hover:bg-red-700'
										: 'bg-amber-600 hover:bg-amber-700'
								}`}
								onClick={async () => {
									setConfirmModal(null)
									if (confirmModal.onConfirm) await confirmModal.onConfirm()
								}}
							>
								{confirmModal.confirmLabel || 'Confirm'}
							</button>
						</div>
					</div>
				</div>
			)}
		</div>
	)
}
