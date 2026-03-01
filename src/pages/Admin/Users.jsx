import { useEffect, useMemo, useState } from 'react'
import { list, upsert, remove } from '../../store/db'

export default function Users() {
	const [items, setItems] = useState([])
	const [instructors, setInstructors] = useState([])
	const [q, setQ] = useState('')
	const [show, setShow] = useState(false)
	const [editing, setEditing] = useState(null)
	const [username, setUsername] = useState('')
	const [role, setRole] = useState('registrar')
	const [instructorId, setInstructorId] = useState('')
	const [password, setPassword] = useState('')
	const [error, setError] = useState('')
	const [entries, setEntries] = useState(10)
	const [processing, setProcessing] = useState(false)

	async function load() {
		try {
			const [usersData, instructorsData] = await Promise.all([
				list('user'),
				list('instructor'),
			])
			setItems(usersData)
			setInstructors(instructorsData)
		} catch (err) {
			console.error('Failed to load data:', err)
		}
	}
	useEffect(() => { load() }, [])

	// Instructors that don't have a linked user account yet
	const unlinkedInstructors = useMemo(() => {
		const linkedIds = new Set(items.filter(u => u.instructor_id).map(u => u.instructor_id))
		return instructors.filter(i => !linkedIds.has(i.id))
	}, [items, instructors])

	const filtered = useMemo(() => {
		return items.filter(i =>
			(i.username || '').toLowerCase().includes(q.toLowerCase()) ||
			(i.role || '').toLowerCase().includes(q.toLowerCase()) ||
			(i.instructor_name || '').toLowerCase().includes(q.toLowerCase())
		)
	}, [items, q])

	const shown = useMemo(() => {
		const n = Math.max(0, Number(entries) || 0)
		return filtered.slice(0, n || filtered.length)
	}, [filtered, entries])

	function openAdd() {
		setEditing(null)
		setUsername('')
		setRole('registrar')
		setInstructorId('')
		setPassword('')
		setError('')
		setShow(true)
	}

	function openEdit(it) {
		setEditing(it)
		setUsername(it.username || '')
		setRole(it.role || 'registrar')
		setInstructorId(it.instructor_id || '')
		setPassword('')
		setError('')
		setShow(true)
	}

	async function onSave(e) {
		e.preventDefault()
		if (processing) return
		if (!username.trim()) { setError('Username is required'); return }
		if (!role) { setError('Role is required'); return }
		if (!editing && !password.trim()) {
			setError('Password is required for new users')
			return
		}
		if (role === 'instructor' && !editing && !instructorId) {
			setError('Please select an instructor to link')
			return
		}

		const duplicate = items.find(i =>
			i.username.toLowerCase() === username.trim().toLowerCase() &&
			i.id !== (editing?.id)
		)
		if (duplicate) { setError('Username must be unique'); return }

		const userData = {
			id: editing?.id,
			username: username.trim(),
			role: role,
		}

		if (role === 'instructor' && !editing) {
			userData.instructor_id = parseInt(instructorId)
		}

		if (password.trim()) {
			userData.password = password.trim()
		}

		try {
			setProcessing(true)
			await upsert('user', userData)
			setShow(false)
			await load()
		} catch (error) {
			setError(error.message || 'Failed to save user')
		} finally {
			setProcessing(false)
		}
	}

	async function onDelete(id) {
		if (processing) return
		if (!confirm('Delete this user account?')) return
		try {
			setProcessing(true)
			await remove('user', id)
			await load()
		} catch (error) {
			alert(error.message || 'Failed to delete user')
		} finally {
			setProcessing(false)
		}
	}

	// Helper to get instructor name for inline display
	function getInstructorName(instructorId) {
		if (!instructorId) return null
		const instr = instructors.find(i => i.id === instructorId)
		if (!instr) return null
		const parts = [instr.first_name || '']
		if (instr.middle_name) parts.push(instr.middle_name)
		parts.push(instr.last_name || '')
		return parts.filter(Boolean).join(' ')
	}

	return (
		<div>
			<div className="flex items-center justify-between mb-4">
				<h1 className="text-navy text-3xl font-semibold">USERS</h1>
				<button className="px-3 py-2 rounded bg-royal text-white flex items-center gap-2 disabled:opacity-60" onClick={openAdd} disabled={processing}>
					<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-4 h-4"><path d="M11 11V5h2v6h6v2h-6v6h-2v-6H5v-2h6z" /></svg>
					<span>Add User</span>
				</button>
			</div>

			{/* Instructors without accounts notice */}
			{unlinkedInstructors.length > 0 && (
				<div className="mb-4 p-3 bg-amber-50 border border-amber-200 rounded-lg">
					<div className="text-sm font-semibold text-amber-800 mb-1">
						⚠️ {unlinkedInstructors.length} instructor{unlinkedInstructors.length > 1 ? 's' : ''} without accounts
					</div>
					<div className="text-xs text-amber-700">
						{unlinkedInstructors.slice(0, 5).map(i => {
							const name = `${i.first_name || ''} ${i.last_name || ''}`.trim()
							return name
						}).join(', ')}
						{unlinkedInstructors.length > 5 && ` and ${unlinkedInstructors.length - 5} more...`}
					</div>
				</div>
			)}

			{/* Standardized fixed-height container for list/table area */}
			<div className="h-[520px] overflow-auto pr-1 [&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none]">
				<div className="mb-2 text-navy text-1xl font-semibold">List of Users</div>
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
					<input className="w-full max-w-sm px-3 py-2 rounded-full border" placeholder="Search: Users" value={q} onChange={e => setQ(e.target.value)} />
				</div>
				<div className="overflow-x-auto">
					<table className="min-w-full text-sm border border-gray-400">
						<thead>
							<tr className="bg-navy text-white border-b-2 border-gray-500">
								<th className="text-left px-3 py-2 border-r border-gray-300">No.</th>
								<th className="text-left px-3 py-2 border-r border-gray-300">Username</th>
								<th className="text-left px-3 py-2 border-r border-gray-300">Role</th>
								<th className="text-left px-3 py-2 border-r border-gray-300">Linked Instructor</th>
								<th className="text-center px-3 py-2 w-36">Action</th>
							</tr>
						</thead>
						<tbody className="divide-y divide-gray-300">
							{shown.map((it, idx) => (
								<tr key={it.id} className={idx % 2 ? 'bg-gray-50' : ''}>
									<td className="px-3 py-2 border-r border-gray-300">{idx + 1}</td>
									<td className="px-3 py-2 border-r border-gray-300">{it.username}</td>
									<td className="px-3 py-2 border-r border-gray-300 capitalize">
										<span className={`inline-block px-2 py-0.5 rounded-full text-xs font-semibold ${it.role === 'admin' ? 'bg-purple-100 text-purple-800' :
												it.role === 'registrar' ? 'bg-blue-100 text-blue-800' :
													'bg-green-100 text-green-800'
											}`}>
											{it.role}
										</span>
									</td>
									<td className="px-3 py-2 border-r border-gray-300">
										{it.instructor_name || (it.instructor_id ? getInstructorName(it.instructor_id) : '—')}
									</td>
									<td className="px-3 py-2 space-x-3 text-center">
										<button
											className="inline-flex items-center justify-center w-8 h-8 rounded-full bg-blue-600 hover:opacity-90 disabled:opacity-60"
											title="Edit"
											onClick={() => openEdit(it)}
											disabled={processing}
										>
											<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-4 h-4 text-white">
												<path d="M3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25zM20.71 7.04c.39-.39.39-1.02 0-1.41l-2.34-2.34c-.39-.39-1.02-.39-1.41 0l-1.83 1.83 3.75 3.75 1.83-1.83z" />
											</svg>
										</button>
										<button
											className="inline-flex items-center justify-center w-8 h-8 rounded-full bg-red-600 hover:opacity-90 disabled:opacity-60"
											title="Delete"
											onClick={() => onDelete(it.id)}
											disabled={processing}
										>
											<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-4 h-4 text-white">
												<path d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z" />
											</svg>
										</button>
									</td>
								</tr>
							))}
							{shown.length === 0 && (
								<tr className="border-t border-gray-300"><td className="px-3 py-6 text-center text-gray-500" colSpan={5}>No records</td></tr>
							)}
						</tbody>
					</table>
				</div>
			</div>

			{show && (
				<div className="fixed inset-0 bg-black/30 flex items-center justify-center p-4 z-50">
					<form onSubmit={onSave} className="w-full max-w-md bg-white rounded-xl shadow p-5 space-y-3">
						<div className="text-lg font-semibold text-navy">{editing ? 'Edit User' : 'Add User'}</div>
						<div>
							<label className="block text-sm font-medium text-gray-700 mb-1">Role</label>
							<select
								className="w-full px-3 py-2 rounded border"
								value={role}
								onChange={e => {
									setRole(e.target.value)
									if (e.target.value !== 'instructor') setInstructorId('')
								}}
								disabled={!!editing}
							>
								<option value="admin">Admin</option>
								<option value="registrar">Registrar</option>
								<option value="instructor">Instructor</option>
							</select>
						</div>

						{/* Show instructor picker when role is instructor and adding new */}
						{role === 'instructor' && !editing && (
							<div>
								<label className="block text-sm font-medium text-gray-700 mb-1">Link to Instructor</label>
								<select
									className="w-full px-3 py-2 rounded border"
									value={instructorId}
									onChange={e => setInstructorId(e.target.value)}
								>
									<option value="">Select an instructor...</option>
									{unlinkedInstructors.map(i => {
										const name = `${i.first_name || ''} ${i.middle_name ? i.middle_name + ' ' : ''}${i.last_name || ''}`.trim()
										return <option key={i.id} value={i.id}>{name}</option>
									})}
								</select>
								{unlinkedInstructors.length === 0 && (
									<div className="text-xs text-amber-600 mt-1">All instructors already have accounts.</div>
								)}
							</div>
						)}

						{role === 'instructor' && editing && editing.instructor_id && (
							<div className="text-sm text-gray-600 bg-gray-50 p-2 rounded border">
								Linked to: <span className="font-semibold">{editing.instructor_name || getInstructorName(editing.instructor_id) || `Instructor #${editing.instructor_id}`}</span>
							</div>
						)}

						<div>
							<label className="block text-sm font-medium text-gray-700 mb-1">Username</label>
							<input
								className="w-full px-3 py-2 rounded border"
								placeholder="Username"
								value={username}
								onChange={e => setUsername(e.target.value)}
							/>
						</div>
						<div>
							<label className="block text-sm font-medium text-gray-700 mb-1">Password</label>
							<input
								type="password"
								className="w-full px-3 py-2 rounded border"
								placeholder={editing ? "New password (leave blank to keep)" : "Password"}
								value={password}
								onChange={e => setPassword(e.target.value)}
							/>
						</div>
						{error && <div className="text-sm text-red-600">{error}</div>}
						<div className="flex justify-end gap-2 pt-2">
							<button type="button" className="px-3 py-2 rounded border" onClick={() => setShow(false)} disabled={processing}>Cancel</button>
							<button className="px-3 py-2 rounded bg-royal text-white disabled:opacity-60" disabled={processing}>
								{processing ? 'Saving...' : 'Save'}
							</button>
						</div>
					</form>
				</div>
			)}
		</div>
	)
}
