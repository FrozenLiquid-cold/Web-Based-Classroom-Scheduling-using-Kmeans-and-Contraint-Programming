import { useEffect, useMemo, useState, useRef } from 'react'


export default function Buildings() {
    const [items, setItems] = useState([])
    const [q, setQ] = useState('')
    const [show, setShow] = useState(false)
    const [editing, setEditing] = useState(null)
    const [name, setName] = useState('')
    const [code, setCode] = useState('')
    const [description, setDescription] = useState('')
    const [error, setError] = useState('')
    const [entries, setEntries] = useState(10)
    const [processing, setProcessing] = useState(false)

    const dataLoadingRef = useRef(false);
    const dataLoadedRef = useRef(false);

    async function load(force = false) {
        if (!force && (dataLoadedRef.current || dataLoadingRef.current)) return;

        dataLoadingRef.current = true;
        try {
            // Using direct API call because 'building' might not be in the store/db helper mapping yet
            // or if it is, that's fine. Let's assume we can use api.get('/buildings') or similar.
            // But wait, the 'list' helper uses the generic store. Let's try to stick to the pattern if possible.
            // Actually, for a new entity, I might need to update store/db if it relies on a hardcoded list of stores?
            // Let's check store/db later. For now, I'll use direct fetch if needed, 
            // but for consistency I will try to use the same pattern as Room.
            // If 'list' function supports 'buildings', great.
            // I'll assume I need to fetch from /api/buildings.

            const res = await fetch('http://localhost:8000/api/buildings')
            if (res.ok) {
                const data = await res.json()
                setItems(data)
                dataLoadedRef.current = true;
            } else {
                console.error("Failed to load buildings");
            }

        } catch (error) {
            console.error('Error loading buildings:', error);
        } finally {
            dataLoadingRef.current = false;
        }
    }
    useEffect(() => { load() }, [])

    const filtered = useMemo(() => {
        return items.filter(i => (i.name || '').toLowerCase().includes(q.toLowerCase()) || (i.code || '').toLowerCase().includes(q.toLowerCase()))
    }, [items, q])

    const shown = useMemo(() => {
        const n = Math.max(0, Number(entries) || 0)
        return filtered.slice(0, n || filtered.length)
    }, [filtered, entries])

    function openAdd() {
        setEditing(null)
        setName('')
        setCode('')
        setDescription('')
        setError('')
        setShow(true)
    }

    function openEdit(it) {
        setEditing(it)
        setName(it.name || '')
        setCode(it.code || '')
        setDescription(it.description || '')
        setError('')
        setShow(true)
    }

    async function onSave(e) {
        e.preventDefault()
        if (processing) return
        if (!name.trim()) { setError('Building name is required'); return }

        try {
            setProcessing(true)
            const payload = { name: name.trim(), code: code.trim() || null, description: description.trim() || null }
            let res;
            if (editing) {
                res = await fetch(`http://localhost:8000/api/buildings/${editing.id}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                })
            } else {
                res = await fetch(`http://localhost:8000/api/buildings`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                })
            }

            if (!res.ok) {
                const json = await res.json().catch(() => ({}))
                throw new Error(json.detail || json.error || 'Failed to save')
            }

            setShow(false)
            await load(true)
        } catch (error) {
            setError(error.message || 'Failed to save')
        } finally {
            setProcessing(false)
        }
    }

    async function onDelete(id) {
        if (processing) return
        if (!confirm('Delete this building?')) return
        try {
            setProcessing(true)
            const res = await fetch(`http://localhost:8000/api/buildings/${id}`, { method: 'DELETE' })
            if (!res.ok) {
                const json = await res.json().catch(() => ({}))
                throw new Error(json.detail || 'Failed to delete')
            }
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
                <h1 className="text-navy text-3xl font-semibold">BUILDINGS</h1>
                <button className="px-3 py-2 rounded bg-royal text-white flex items-center gap-2 disabled:opacity-60" onClick={openAdd} disabled={processing}>
                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-4 h-4"><path d="M11 11V5h2v6h6v2h-6v6h-2v-6H5v-2h6z" /></svg>
                    <span>Add Building</span>
                </button>
            </div>
            <div className="h-[520px] overflow-auto pr-1 [&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none]">
                <div className="mb-2 text-navy text-1xl font-semibold">List of Buildings</div>
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
                    <input className="w-full max-w-sm px-3 py-2 rounded-full border" placeholder="Search: Building" value={q} onChange={e => setQ(e.target.value)} />
                </div>
                <div className="overflow-x-auto">
                    <table className="min-w-full text-sm border border-gray-400">
                        <thead>
                            <tr className="bg-navy text-white border-b-2 border-gray-500">
                                <th className="text-left px-3 py-2 border-r border-gray-300 w-12">No.</th>
                                <th className="text-left px-3 py-2 border-r border-gray-300">Building Name</th>
                                <th className="text-left px-3 py-2 border-r border-gray-300 w-24">Code</th>
                                <th className="text-left px-3 py-2 border-r border-gray-300">Description</th>
                                <th className="text-center px-3 py-2 w-36">Action</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-300">
                            {shown.map((it, idx) => (
                                <tr key={it.id} className={idx % 2 ? 'bg-gray-50' : ''}>
                                    <td className="px-3 py-2 border-r border-gray-300">{idx + 1}</td>
                                    <td className="px-3 py-2 border-r border-gray-300 font-medium">{it.name}</td>
                                    <td className="px-3 py-2 border-r border-gray-300">{it.code}</td>
                                    <td className="px-3 py-2 border-r border-gray-300 text-gray-600 truncate max-w-xs">{it.description}</td>
                                    <td className="px-3 py-2 space-x-3 text-center">
                                        <button className="inline-flex items-center justify-center w-8 h-8 rounded-full bg-blue-600 hover:opacity-90" title="Edit" onClick={() => openEdit(it)}>
                                            <img src="/assets/edit.png" alt="Edit" className="w-4 h-4 object-contain" onError={(e) => { e.currentTarget.style.display = 'none' }} />
                                        </button>
                                        <button className="inline-flex items-center justify-center w-8 h-8 rounded-full bg-red-600 hover:opacity-90" title="Delete" onClick={() => onDelete(it.id)}>
                                            <img src="/assets/delete.png" alt="Delete" className="w-4 h-4 object-contain" onError={(e) => { e.currentTarget.style.display = 'none' }} />
                                        </button>
                                    </td>
                                </tr>
                            ))}
                            {filtered.length === 0 && (
                                <tr className="border-t border-gray-300"><td className="px-3 py-6 text-center text-gray-500" colSpan={5}>No records</td></tr>
                            )}
                        </tbody>
                    </table>
                </div>
            </div>

            {show && (
                <div className="fixed inset-0 bg-black/30 flex items-center justify-center p-4">
                    <form onSubmit={onSave} className="w-full max-w-md bg-white rounded-xl shadow p-5 space-y-3">
                        <div className="text-lg font-semibold text-navy">{editing ? 'Edit Building' : 'Add Building'}</div>

                        <div>
                            <label className="block text-xs font-semibold text-gray-600 mb-1">Building Name</label>
                            <input className="w-full px-3 py-2 rounded border" placeholder="e.g. Science Building" value={name} onChange={e => setName(e.target.value)} />
                        </div>

                        <div>
                            <label className="block text-xs font-semibold text-gray-600 mb-1">Code (Optional)</label>
                            <input className="w-full px-3 py-2 rounded border" placeholder="e.g. SCI" value={code} onChange={e => setCode(e.target.value)} />
                        </div>

                        <div>
                            <label className="block text-xs font-semibold text-gray-600 mb-1">Description</label>
                            <textarea className="w-full px-3 py-2 rounded border" placeholder="Description / Notes" rows="3" value={description} onChange={e => setDescription(e.target.value)}></textarea>
                        </div>

                        {error && <div className="text-sm text-red-600">{error}</div>}
                        <div className="flex justify-end gap-2 pt-2">
                            <button type="button" className="px-3 py-2 rounded border" onClick={() => setShow(false)} disabled={processing}>Cancel</button>
                            <button className="px-3 py-2 rounded bg-royal text-white disabled:opacity-60" disabled={processing}>Save</button>
                        </div>
                    </form>
                </div>
            )}
        </div>
    )
}
