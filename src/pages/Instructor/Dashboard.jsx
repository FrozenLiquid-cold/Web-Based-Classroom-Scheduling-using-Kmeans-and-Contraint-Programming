import { useEffect, useMemo, useState } from 'react'
import { getInstructorWorkload } from '../../services/api'

export default function Dashboard(){
	const session = useMemo(()=>{
		try{ return JSON.parse(localStorage.getItem('jrmsu.session')||'null') }catch{ return null }
	},[])

	const instructorId = session?.instructorId || null
	const [semester, setSemester] = useState('1')
	const [workload, setWorkload] = useState(null)
	const [loading, setLoading] = useState(false)
	const [error, setError] = useState('')
	const [refreshTick, setRefreshTick] = useState(0)

	useEffect(()=>{
		let cancelled = false
		async function load() {
			if (!instructorId) {
				setWorkload(null)
				return
			}
			try {
				setLoading(true)
				setError('')
				const data = await getInstructorWorkload(instructorId, Number(semester))
				if (cancelled) return
				setWorkload(data || null)
			} catch (e) {
				if (cancelled) return
				setWorkload(null)
				setError(e?.message || 'Failed to load workload')
			} finally {
				if (!cancelled) setLoading(false)
			}
		}
		load()
		return ()=>{ cancelled = true }
	}, [instructorId, semester, refreshTick])

	useEffect(()=>{
		function onVisible() {
			if (document.visibilityState === 'visible') {
				setRefreshTick(t=>t+1)
			}
		}
		document.addEventListener('visibilitychange', onVisible)
		const timer = setInterval(()=> setRefreshTick(t=>t+1), 30000)
		return ()=>{
			document.removeEventListener('visibilitychange', onVisible)
			clearInterval(timer)
		}
	}, [])

	const weeklyHours = Number(workload?.weekly_hours || 0)
	const limitHours = Number(workload?.limit_hours || 0)
	const isOverloaded = limitHours > 0 ? weeklyHours > limitHours : weeklyHours > 0
	const percent = limitHours > 0 ? Math.min(100, Math.round((weeklyHours / limitHours) * 100)) : 0

	const size = 140
	const stroke = 12
	const r = (size - stroke) / 2
	const c = 2 * Math.PI * r
	const dash = (percent / 100) * c
	const ringColor = isOverloaded ? '#dc2626' : '#1d4ed8'

	return (
		<div className="relative flex flex-col items-center justify-center py-12">
			<div className="absolute top-6 right-6">
				<div className="flex items-center gap-2">
					<select className="px-3 py-2 rounded border" value={semester} onChange={e=>setSemester(e.target.value)}>
						<option value="1">Semester 1</option>
						<option value="2">Semester 2</option>
					</select>
					<button
						type="button"
						className="px-3 py-2 rounded border bg-white hover:bg-gray-50"
						onClick={()=>setRefreshTick(t=>t+1)}
						disabled={loading}
					>
						Refresh
					</button>
				</div>
			</div>

			<div className="mb-6 flex flex-col items-center">
				<div className="relative" style={{ width: size, height: size }}>
					<svg width={size} height={size} className="block">
						<circle
							cx={size/2}
							cy={size/2}
							r={r}
							stroke="#e5e7eb"
							strokeWidth={stroke}
							fill="none"
						/>
						<circle
							cx={size/2}
							cy={size/2}
							r={r}
							stroke={ringColor}
							strokeWidth={stroke}
							fill="none"
							strokeLinecap="round"
							strokeDasharray={`${dash} ${c - dash}`}
							transform={`rotate(-90 ${size/2} ${size/2})`}
						/>
					</svg>
					<div className="absolute inset-0 flex flex-col items-center justify-center text-center">
						<div className="text-3xl font-semibold" style={{ color: ringColor }}>{weeklyHours.toFixed(1)}</div>
						<div className="text-xs text-gray-600">hours / week</div>
						<div className="mt-1 text-xs text-gray-700">limit: {limitHours}</div>
					</div>
				</div>

				{loading && <div className="mt-3 text-sm text-gray-600">Loading workload...</div>}
				{error && <div className="mt-3 text-sm text-red-600">{error}</div>}
				{workload && Array.isArray(workload.warnings) && workload.warnings.length > 0 && (
					<div className="mt-3 w-full max-w-xl space-y-1">
						{workload.warnings.map((w, idx)=>(
							<div key={idx} className="text-xs text-red-700 bg-red-50 border border-red-200 rounded px-3 py-2">{w}</div>
						))}
					</div>
				)}
			</div>

			<img src="/assets/jrmsu-logo.png" alt="JRMSU" className="mx-auto w-40 h-40 object-contain" onError={(e)=>{e.currentTarget.style.display='none'}} />
			<div className="mt-6 text-[#1d8a50] font-oswald uppercase tracking-wider text-2xl">JOSE RIZAL MEMORIAL STATE UNIVERSITY</div>
			<div className="mt-4 text-center leading-tight">
				<div className="text-navy font-archivoBlack uppercase text-2xl tracking-wide">K-MEANS AND CONSTRAINT PROGRAMMING CLASSROOM</div>
				<div className="text-navy font-archivoBlack uppercase text-2xl tracking-wide">SCHEDULING SYSTEM</div>
			</div>
		</div>
	)
}

