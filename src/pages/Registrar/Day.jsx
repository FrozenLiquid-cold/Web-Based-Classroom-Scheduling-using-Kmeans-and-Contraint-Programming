import { useEffect, useMemo, useState, useRef } from 'react'
import { list, upsert, remove } from '../../store/db'
import ConfirmDialog from '../../components/ConfirmDialog'

export default function Day() {
	const [items, setItems] = useState([])
	const [q, setQ] = useState('')
	const [show, setShow] = useState(false)
	const [editing, setEditing] = useState(null)
	const [label, setLabel] = useState('')
	const [error, setError] = useState('')
	const [entries, setEntries] = useState(10)
	const [processing, setProcessing] = useState(false) // For Save/Delete
	const [confirmDialog, setConfirmDialog] = useState({ open: false })

	// Prevent duplicate loads from React StrictMode
	const dataLoadingRef = useRef(false)
	const dataLoadedRef = useRef(false)

	async function load(force = false) {
		if (!force && (dataLoadedRef.current || dataLoadingRef.current)) return
		dataLoadingRef.current = true
		try {
			const data = await list('day')
			setItems(data)
			dataLoadedRef.current = true
		} catch (err) {
			console.error('Error loading days:', err)
		} finally {
			dataLoadingRef.current = false
		}
	}

	useEffect(() => { load() }, [])

	const filtered = useMemo(() => {
		return items.filter(i => (i.label || '').toLowerCase().includes(q.toLowerCase()))
	}, [items, q])

	const shown = useMemo(() => {
		const n = Math.max(0, Number(entries) || 0)
		return filtered.slice(0, n || filtered.length)
	}, [filtered, entries])

	function openAdd() {
		setEditing(null)
		setLabel('')
		setError('')
		setShow(true)
	}

	function openEdit(it) {
		setEditing(it)
		setLabel(it.label || '')
		setError('')
		setShow(true)
	}

	async function onSave(e) {
		e.preventDefault()
		if (processing) return
		setProcessing(true)

		if (!label.trim()) { setError('Day label is required'); setProcessing(false); return }
		const duplicate = items.find(i => (i.label || '').toLowerCase() === label.trim().toLowerCase() && i.id !== editing?.id)
		if (duplicate) { setError('Day must be unique'); setProcessing(false); return }

		try {
			await upsert('day', { id: editing?.id, label: label.trim() })
			setShow(false)
			await load(true)
		} catch (err) {
			setError(err.message || 'Failed to save')
		} finally {
			setProcessing(false)
		}
	}

	function onDelete(id) {
		if (processing) return
		setConfirmDialog({
			open: true,
			title: 'Delete Day',
			message: 'Are you sure you want to delete this day? This action cannot be undone.',
			confirmText: 'Delete',
			variant: 'danger',
			onConfirm: async () => {
				setConfirmDialog({ open: false })
				setProcessing(true)
				try {
					await remove('day', id)
					await load(true)
				} catch (err) {
					alert(err.message || 'Failed to delete')
				} finally {
					setProcessing(false)
				}
			},
		})
	}

	return (
		<div>
			<div className="flex items-center justify-between mb-4">
				<h1 className="text-navy text-3xl font-semibold">DAY</h1>
				<button
					className="px-3 py-2 rounded bg-royal text-white flex items-center gap-2"
					onClick={openAdd}
					disabled={processing}
				>
					<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-4 h-4"><path d="M11 11V5h2v6h6v2h-6v6h-2v-6H5v-2h6z" /></svg>
					<span>Add Day</span>
				</button>
			</div>

			<div className="h-[520px] overflow-auto pr-1 [&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none]">
				<div className="mb-2 text-navy text-1xl font-semibold">List of Day</div>
				<div className="flex items-center justify-between mb-3 gap-4">
					<div className="flex items-center gap-2 text-sm">
						<span>Show</span>
						<div className="flex items-stretch border border-gray-300 rounded overflow-hidden">
							<input type="number" min="1" className="w-16 px-2 outline-none text-center" value={entries} onChange={e => setEntries(e.target.value)} />
							<div className="flex flex-col">
								<button type="button" className="px-2 border-l border-b border-gray-300 hover:bg-gray-100" onClick={() => setEntries(prev => Number(prev || 0) + 1)}>▲</button>
								<button type="button" className="px-2 border-l border-gray-300 hover:bg-gray-100" onClick={() => setEntries(prev => Math.max(1, Number(prev || 0) - 1))}>▼</button>
							</div>
						</div>
						<span>entries</span>
					</div>
					<input className="w-full max-w-sm px-3 py-2 rounded-full border" placeholder="Search: Day" value={q} onChange={e => setQ(e.target.value)} />
				</div>

				<div className="overflow-x-auto">
					<table className="min-w-full text-sm border border-gray-400">
						<thead>
							<tr className="bg-navy text-white border-b-2 border-gray-500">
								<th className="text-left px-3 py-2 border-r border-gray-300">No.</th>
								<th className="text-left px-3 py-2 border-r border-gray-300">Day</th>
								<th className="text-center px-3 py-2 w-36">Action</th>
							</tr>
						</thead>
						<tbody className="divide-y divide-gray-300">
							{shown.map((it, idx) => (
								<tr key={it.id} className={idx % 2 ? 'bg-gray-50' : ''}>
									<td className="px-3 py-2 border-r border-gray-300">{idx + 1}</td>
									<td className="px-3 py-2 border-r border-gray-300">{it.label}</td>
									<td className="px-3 py-2 space-x-3 text-center">
										<button className="inline-flex items-center justify-center w-8 h-8 rounded-full bg-blue-600 hover:opacity-90" title="Edit" onClick={() => openEdit(it)} disabled={processing}>
											<img src="/assets/edit.png" alt="Edit" className="w-4 h-4 object-contain" onError={e => { e.currentTarget.style.display = 'none' }} />
										</button>
										<button className="inline-flex items-center justify-center w-8 h-8 rounded-full bg-red-600 hover:opacity-90" title="Delete" onClick={() => onDelete(it.id)} disabled={processing}>
											<img src="/assets/delete.png" alt="Delete" className="w-4 h-4 object-contain" onError={e => { e.currentTarget.style.display = 'none' }} />
										</button>
									</td>
								</tr>
							))}
							{filtered.length === 0 && (
								<tr className="border-t border-gray-300"><td className="px-3 py-6 text-center text-gray-500" colSpan={3}>No records</td></tr>
							)}
						</tbody>
					</table>
				</div>
			</div>

			{show && (
				<div className="fixed inset-0 bg-black/30 flex items-center justify-center p-4">
					<form onSubmit={onSave} className="w-full max-w-md bg-white rounded-xl shadow p-5 space-y-3">
						<div className="text-lg font-semibold text-navy">{editing ? 'Edit Day' : 'Add Day'}</div>
						<input className="w-full px-3 py-2 rounded border" placeholder="Day (e.g., M, T, W, TH, F)" value={label} onChange={e => setLabel(e.target.value)} />
						{error && <div className="text-sm text-red-600">{error}</div>}
						<div className="flex justify-end gap-2 pt-2">
							<button type="button" className="px-3 py-2 rounded border" onClick={() => setShow(false)} disabled={processing}>Cancel</button>
							<button type="submit" className="px-3 py-2 rounded bg-royal text-white" disabled={processing}>Save</button>
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
