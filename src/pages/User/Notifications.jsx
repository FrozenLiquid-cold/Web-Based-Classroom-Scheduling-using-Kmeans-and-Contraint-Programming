import { Link, useNavigate } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { logout } from '../../store/auth'

export default function Notifications(){
	const [items, setItems] = useState([])
	const navigate = useNavigate()
	useEffect(()=>{
		setItems([
			{ id: 1, dt: new Date().toLocaleString(), msg: 'Welcome to JRMSU Scheduler.' },
			{ id: 2, dt: new Date().toLocaleString(), msg: 'Seed data loaded. You can start creating schedules.' },
		])
	},[])

	return (
		<div>
			<div className="flex items-center justify-between mb-4">
				<h1 className="text-navy font-archivo tracking-wide uppercase text-2xl">Notification</h1>
				
			</div>
			<div className="bg-white/90 rounded-xl shadow-xl overflow-hidden ring-1 ring-black/10">
				<div className="overflow-x-auto">
					<table className="min-w-full text-[15px] border border-gray-400">
						<thead>
							<tr className="bg-navy text-white border-b-2 border-gray-500">
								<th className="text-left px-5 py-3 w-64 border-r border-gray-300 last:border-r-0">Date & Time</th>
								<th className="text-left px-5 py-3 border-r border-gray-300 last:border-r-0">Message</th>
							</tr>
						</thead>
						<tbody className="divide-y divide-gray-300">
							{items.map((it, idx)=> (
								<tr key={it.id} className={idx%2? 'bg-white' : 'bg-[#f5f7fb]'}>
									<td className="px-5 py-3 align-top text-[13px] text-gray-700 whitespace-nowrap border-r border-gray-300 last:border-r-0">{it.dt}</td>
									<td className="px-5 py-3 text-green-700 border-r border-gray-300 last:border-r-0">{it.msg}</td>
								</tr>
							))}
							{items.length===0 && (
								<tr className="border-t border-gray-300"><td className="px-5 py-8 text-center text-gray-500" colSpan={2}>No notifications</td></tr>
							)}
						</tbody>
					</table>
				</div>
			</div>
		</div>
	)
}

