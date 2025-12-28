import { useEffect, useMemo, useState } from 'react'
import { list, upsert } from '../../store/db'

export default function Users() {
	const [items, setItems] = useState([])
	const [q, setQ] = useState('')
	const [show, setShow] = useState(false)
	const [editing, setEditing] = useState(null)
	const [username, setUsername] = useState('')
	const [fullName, setFullName] = useState('')
	const [email, setEmail] = useState('')
	const [role, setRole] = useState('registrar')
	const [password, setPassword] = useState('')
	const [error, setError] = useState('')
	const [entries, setEntries] = useState(10)

	async function load(){ 
		// Note: Users endpoint may not exist in backend yet
		// This will return empty array if endpoint doesn't exist
		const data = await list('user')
		setItems(data)
	}
	useEffect(()=>{ load() },[])

	const filtered = useMemo(()=>{
		return items.filter(i=> 
			(i.username || '').toLowerCase().includes(q.toLowerCase()) ||
			(i.fullName || '').toLowerCase().includes(q.toLowerCase()) ||
			(i.email || '').toLowerCase().includes(q.toLowerCase()) ||
			(i.role || '').toLowerCase().includes(q.toLowerCase())
		)
	},[items,q])

	const shown = useMemo(()=>{
		const n = Math.max(0, Number(entries)||0)
		return filtered.slice(0, n || filtered.length)
	}, [filtered, entries])

	function openAdd(){
		setEditing(null)
		setUsername('')
		setFullName('')
		setEmail('')
		setRole('registrar')
		setPassword('')
		setError('')
		setShow(true)
	}

	function openEdit(it){
		setEditing(it)
		setUsername(it.username || '')
		setFullName(it.fullName || '')
		setEmail(it.email || '')
		setRole(it.role || 'registrar')
		setPassword('')
		setError('')
		setShow(true)
	}

	async function onSave(e){
		e.preventDefault()
		if (!username.trim() || !fullName.trim() || !email.trim() || !role) { 
			setError('All fields are required'); 
			return 
		}
		if (!editing && !password.trim()) {
			setError('Password is required for new users'); 
			return 
		}
		
		const duplicate = items.find(i=> 
			i.username.toLowerCase() === username.trim().toLowerCase() && 
			i.id !== (editing?.id)
		)
		if (duplicate) { 
			setError('Username must be unique'); 
			return 
		}

		const userData = { 
			id: editing?.id, 
			username: username.trim(), 
			fullName: fullName.trim(),
			email: email.trim(),
			role: role,
			status: editing?.status !== undefined ? editing.status : 'active'
		}

		if (password.trim()) {
			userData.password = password.trim()
		}

		try {
			await upsert('user', userData)
			setShow(false)
			await load()
		} catch (error) {
			setError(error.message || 'Failed to save user')
		}
	}

	async function toggleStatus(id){
		const user = items.find(u => u.id === id)
		if (!user) return
		const newStatus = user.status === 'active' ? 'inactive' : 'active'
		try {
			await upsert('user', { ...user, status: newStatus })
			await load()
		} catch (error) {
			alert(error.message || 'Failed to update user status')
		}
	}

	return (
		<div>
			<div className="flex items-center justify-between mb-4">
				<h1 className="text-navy text-3xl font-semibold">USERS</h1>
				<button className="px-3 py-2 rounded bg-royal text-white flex items-center gap-2" onClick={openAdd}>
					<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-4 h-4"><path d="M11 11V5h2v6h6v2h-6v6h-2v-6H5v-2h6z"/></svg>
					<span>Add User</span>
				</button>
			</div>
			{/* Standardized fixed-height container for list/table area */}
			<div className="h-[520px] overflow-auto pr-1 [&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none]">
				<div className="mb-2 text-navy text-1xl font-semibold">List of Users</div>
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
					<input className="w-full max-w-sm px-3 py-2 rounded-full border" placeholder="Search: Users" value={q} onChange={e=>setQ(e.target.value)} />
				</div>
				<div className="overflow-x-auto">
					<table className="min-w-full text-sm border border-gray-400">
						<thead>
							<tr className="bg-navy text-white border-b-2 border-gray-500">
								<th className="text-left px-3 py-2 border-r border-gray-300">No.</th>
								<th className="text-left px-3 py-2 border-r border-gray-300">Username</th>
								<th className="text-left px-3 py-2 border-r border-gray-300">Full Name</th>
								<th className="text-left px-3 py-2 border-r border-gray-300">Email</th>
								<th className="text-left px-3 py-2 border-r border-gray-300">Role</th>
								<th className="text-left px-3 py-2 border-r border-gray-300">Status</th>
								<th className="text-center px-3 py-2 w-36">Action</th>
							</tr>
						</thead>
						<tbody className="divide-y divide-gray-300">
							{shown.map((it, idx)=> (
								<tr key={it.id} className={idx%2? 'bg-gray-50':''}>
									<td className="px-3 py-2 border-r border-gray-300">{idx+1}</td>
									<td className="px-3 py-2 border-r border-gray-300">{it.username}</td>
									<td className="px-3 py-2 border-r border-gray-300">{it.fullName}</td>
									<td className="px-3 py-2 border-r border-gray-300">{it.email}</td>
									<td className="px-3 py-2 border-r border-gray-300 capitalize">{it.role || 'registrar'}</td>
									<td className="px-3 py-2 border-r border-gray-300">
										<span className={`inline-block px-2 py-1 rounded-full text-xs font-semibold ${
											it.status === 'active' 
												? 'bg-green-100 text-green-800' 
												: 'bg-red-100 text-red-800'
										}`}>
											{it.status === 'active' ? 'Active' : 'Inactive'}
										</span>
									</td>
									<td className="px-3 py-2 space-x-3 text-center">
										<button 
											className={`inline-flex items-center justify-center w-8 h-8 rounded-full hover:opacity-90 ${
												it.status === 'active' 
													? 'bg-red-600' 
													: 'bg-green-600'
											}`} 
											title={it.status === 'active' ? 'Deactivate' : 'Activate'} 
											onClick={()=>toggleStatus(it.id)}
										>
											{it.status === 'active' ? (
												<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-4 h-4 text-white">
													<path d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z"/>
												</svg>
											) : (
												<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-4 h-4 text-white">
													<path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/>
												</svg>
											)}
										</button>
									</td>
								</tr>
							))}
							{shown.length===0 && (
								<tr className="border-t border-gray-300"><td className="px-3 py-6 text-center text-gray-500" colSpan={7}>No records</td></tr>
							)}
						</tbody>
					</table>
				</div>
			</div>

			{show && (
				<div className="fixed inset-0 bg-black/30 flex items-center justify-center p-4">
					<form onSubmit={onSave} className="w-full max-w-md bg-white rounded-xl shadow p-5 space-y-3">
						<div className="text-lg font-semibold text-navy">{editing? 'Edit User':'Add User'}</div>
						<input 
							className="w-full px-3 py-2 rounded border" 
							placeholder="Username" 
							value={username} 
							onChange={e=>setUsername(e.target.value)} 
						/>
						<input 
							className="w-full px-3 py-2 rounded border" 
							placeholder="Full Name" 
							value={fullName} 
							onChange={e=>setFullName(e.target.value)} 
						/>
						<input 
							type="email"
							className="w-full px-3 py-2 rounded border" 
							placeholder="Email" 
							value={email} 
							onChange={e=>setEmail(e.target.value)} 
						/>
						<select 
							className="w-full px-3 py-2 rounded border" 
							value={role} 
							onChange={e=>setRole(e.target.value)}
						>
							<option value="registrar">Registrar</option>
							<option value="instructor">Instructor</option>
							<option value="admin">Admin</option>
						</select>
						<input 
							type="password"
							className="w-full px-3 py-2 rounded border" 
							placeholder={editing ? "New Password (leave blank to keep current)" : "Password"} 
							value={password} 
							onChange={e=>setPassword(e.target.value)} 
						/>
						{error && <div className="text-sm text-red-600">{error}</div>}
						<div className="flex justify-end gap-2 pt-2">
							<button type="button" className="px-3 py-2 rounded border" onClick={()=>setShow(false)}>Cancel</button>
							<button className="px-3 py-2 rounded bg-royal text-white">Save</button>
						</div>
					</form>
				</div>
			)}
		</div>
	)
}


