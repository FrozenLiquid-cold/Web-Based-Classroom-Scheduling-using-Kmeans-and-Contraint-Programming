import { useEffect, useMemo, useState, useRef } from 'react'

export default function BuildingDistances() {
    const [buildings, setBuildings] = useState([])
    const [distances, setDistances] = useState({}) // Key: "fromId-toId", Value: minutes
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState('')
    const [saving, setSaving] = useState(false)
    const [changes, setChanges] = useState({}) // Track unsaved changes: "fromId-toId": minutes

    const dataLoadingRef = useRef(false);
    const dataLoadedRef = useRef(false);

    async function load(force = false) {
        if (!force && (dataLoadedRef.current || dataLoadingRef.current)) return;
        dataLoadingRef.current = true;
        setLoading(true);
        try {
            const [bRes, dRes] = await Promise.all([
                fetch('http://localhost:8000/api/buildings'),
                fetch('http://localhost:8000/api/buildings/distances')
            ]);

            if (bRes.ok && dRes.ok) {
                const bData = await bRes.json();
                const dData = await dRes.json();

                setBuildings(bData);

                const distMap = {};
                dData.forEach(d => {
                    distMap[`${d.from_building_id}-${d.to_building_id}`] = d.travel_time_minutes;
                    // Also store symmetric if needed, but model might store one way. 
                    // Let's assume symmetric for the UI simplify finding
                    distMap[`${d.to_building_id}-${d.from_building_id}`] = d.travel_time_minutes;
                });
                setDistances(distMap);
                setChanges({});
                dataLoadedRef.current = true;
            } else {
                setError("Failed to load data");
            }
        } catch (error) {
            console.error('Error loading data:', error);
            setError(error.message);
        } finally {
            dataLoadingRef.current = false;
            setLoading(false);
        }
    }
    useEffect(() => { load() }, [])

    function handleDistanceChange(id1, id2, val) {
        const minutes = parseInt(val) || 0;
        const key = `${id1}-${id2}`;
        const revKey = `${id2}-${id1}`;
        setChanges(prev => ({
            ...prev,
            [key]: minutes,
            [revKey]: minutes
        }));
    }

    async function saveChanges() {
        setSaving(true);
        setError('');
        try {
            // Process changes. Since we stored symmetric keys in 'changes', we need to be careful not to double save if API handles symmetry or one-way.
            // But API upsert_distance takes from/to.
            // Let's just save the specific pairs we have. 
            // Deduplicate pairs: (1,2) is same as (2,1).
            // Helper to canonicalize key
            const processedPairs = new Set();

            const promises = [];
            for (const [key, minutes] of Object.entries(changes)) {
                const [id1, id2] = key.split('-').map(Number);
                const canonical = id1 < id2 ? `${id1}-${id2}` : `${id2}-${id1}`;
                if (processedPairs.has(canonical)) continue;
                processedPairs.add(canonical);

                promises.push(
                    fetch('http://localhost:8000/api/buildings/distances', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            from_building_id: id1,
                            to_building_id: id2,
                            travel_time_minutes: minutes
                        })
                    })
                );
            }

            await Promise.all(promises);
            await load(true);
            alert("Saved successfully!");
        } catch (err) {
            setError("Failed to save changes");
            console.error(err);
        } finally {
            setSaving(false);
        }
    }

    if (loading && !buildings.length) return <div className="p-5">Loading...</div>

    return (
        <div className="flex flex-col h-full">
            <div className="flex items-center justify-between mb-4">
                <h1 className="text-navy text-3xl font-semibold">TRAVEL TIME MATRIX (Minutes)</h1>
                <button
                    className="px-4 py-2 rounded bg-royal text-white flex items-center gap-2 disabled:opacity-60 disabled:cursor-not-allowed"
                    onClick={saveChanges}
                    disabled={saving || Object.keys(changes).length === 0}
                >
                    <span>{saving ? 'Saving...' : 'Save Changes'}</span>
                </button>
            </div>

            {error && <div className="bg-red-100 text-red-700 p-3 rounded mb-4">{error}</div>}

            <div className="flex-1 overflow-auto bg-white rounded shadow p-4">
                <table className="w-full text-sm border-collapse">
                    <thead>
                        <tr>
                            <th className="p-2 border bg-gray-100 sticky top-0 left-0 z-20"></th>
                            {buildings.map(b => (
                                <th key={b.id} className="p-2 border bg-gray-100 sticky top-0 z-10 min-w-[100px]">
                                    <div className="font-semibold text-navy">{b.code || b.name}</div>
                                    <div className="text-xs font-normal text-gray-500 truncate max-w-[100px]">{b.name}</div>
                                </th>
                            ))}
                        </tr>
                    </thead>
                    <tbody>
                        {buildings.map((rowB, i) => (
                            <tr key={rowB.id}>
                                <th className="p-2 border bg-gray-100 sticky left-0 z-10 text-left min-w-[150px]">
                                    <div className="font-semibold text-navy">{rowB.code || rowB.name}</div>
                                    <div className="text-xs font-normal text-gray-500 truncate max-w-[150px]">{rowB.name}</div>
                                </th>
                                {buildings.map((colB, j) => {
                                    if (i === j) return <td key={colB.id} className="p-2 border bg-gray-50 text-center text-gray-400">-</td>;

                                    // Current value: check changes first, then loaded distances
                                    const key = `${rowB.id}-${colB.id}`;
                                    const val = changes[key] !== undefined ? changes[key] : (distances[key] || 0);

                                    return (
                                        <td key={colB.id} className="p-2 border text-center">
                                            <input
                                                type="number"
                                                min="0"
                                                className={`w-16 p-1 border rounded text-center focus:outline-none focus:border-royal ${changes[key] !== undefined ? 'bg-yellow-50 border-yellow-400' : ''}`}
                                                value={val}
                                                onChange={(e) => handleDistanceChange(rowB.id, colB.id, e.target.value)}
                                            />
                                        </td>
                                    );
                                })}
                            </tr>
                        ))}
                    </tbody>
                </table>
                {buildings.length === 0 && <div className="text-center p-10 text-gray-500">No buildings defined. Go to Buildings page to add some.</div>}
            </div>
        </div>
    )
}
