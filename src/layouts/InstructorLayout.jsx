import { useEffect, useState } from 'react'
import { NavLink, Outlet, useNavigate, useLocation } from 'react-router-dom'
import { logout } from '../store/auth'
import ConfirmDialog from '../components/ConfirmDialog'

const nav = [
	{ to: '/i/dashboard', label: 'Dashboard' },
	{ to: '/i/schedule', label: 'Schedule' },
	{ to: '/i/swap-requests', label: 'Swap Requests' },
	{ to: '/i/account', label: 'Account' },
]

function NavIcon({ label }) {
	const common = 'w-4 h-4';
	switch (label) {
		case 'Dashboard':
			return (
				<svg className={common} viewBox="0 0 24 24" fill="currentColor" aria-hidden>
					<path d="M3 13h8V3H3v10zm0 8h8v-6H3v6zm10 0h8v-10h-8v10zm0-18v6h8V3h-8z" />
				</svg>
			)
		case 'Schedule':
			return (
				<svg className={common} viewBox="0 0 24 24" fill="currentColor" aria-hidden>
					<path d="M12 1a11 11 0 1011 11A11.012 11.012 0 0012 1zm1 11V6h-2v8h7v-2z" />
				</svg>
			)
		case 'Swap Requests':
			return (
				<svg className={common} viewBox="0 0 24 24" fill="currentColor" aria-hidden>
					<path d="M7.5 21L3 16.5l1.4-1.4 2.1 2.1V8h2v9.2l2.1-2.1L12 16.5 7.5 21zM16.5 3L21 7.5l-1.4 1.4-2.1-2.1V16h-2V6.8l-2.1 2.1L12 7.5 16.5 3z" />
				</svg>
			)
		case 'Account':
			return (
				<svg className={common} viewBox="0 0 24 24" fill="currentColor" aria-hidden>
					<path d="M12 12c2.761 0 5-2.239 5-5s-2.239-5-5-5-5 2.239-5 5 2.239 5 5 5zm0 2c-3.866 0-7 3.134-7 7h2a5 5 0 0110 0h2c0-3.866-3.134-7-7-7z" />
				</svg>
			)
		default:
			return null
	}
}

export default function InstructorLayout() {
	const navigate = useNavigate()
	const { pathname } = useLocation()
	const isDashboard = pathname === '/i/dashboard' || pathname === '/i'
	const isAccount = pathname === '/i/account'
	const session = (() => {
		try { return JSON.parse(localStorage.getItem('jrmsu.session') || 'null') } catch { return null }
	})()

	// Check if instructor needs to change credentials (first login)
	const mustChangeKey = session?.instructorId ? `jrmsu.instructor.mustChange.${session.instructorId}` : null
	const mustChangeCredentials = mustChangeKey ? localStorage.getItem(mustChangeKey) === 'true' : false

	// Theme state
	const [isDark, setIsDark] = useState(() => {
		const saved = localStorage.getItem('jrmsu.theme')
		return saved ? saved === 'dark' : false
	})
	const [confirmDialog, setConfirmDialog] = useState({ open: false })

	useEffect(() => {
		localStorage.setItem('jrmsu.theme', isDark ? 'dark' : 'light')
	}, [isDark])

	return (
		<div className="min-h-screen flex">
			<aside className="w-64 bg-navy text-white p-6 space-y-4 flex flex-col items-center">
				<div className="flex flex-col items-center text-center space-y-3">
					<img src="/assets/jrmsu-logo.png" alt="JRMSU" className="mx-auto w-16 h-16 object-contain" />
					<div className="text-s tracking-wider">JOSE RIZAL MEMORIAL STATE UNIVERSITY</div>
				</div>
				<div className="text-gold font-bold text-lg text-center">CLASS - KCP</div>
				<nav className="flex flex-col items-center space-y-1">
					{nav.map(i => (
						<NavLink
							key={i.to}
							to={i.to}
							className={({ isActive }) => [
								'w-48 text-left px-4 py-2 rounded transition-all duration-300 ease-out font-semibold tracking-wide flex items-center gap-3',
								isActive ? 'bg-[#27308a] text-amber-300 shadow-inner font-extrabold scale-[1.02]' : 'text-white/90 hover:text-white hover:bg-[#222b80]'
							].join(' ')}
						>
							<span className="text-white/90">{<NavIcon label={i.label} />}</span>
							<span>{i.label}</span>
						</NavLink>
					))}
				</nav>
				<div className="mt-auto pt-6 w-full">
					<button
						onClick={() => {
							setConfirmDialog({
								open: true,
								title: 'Log Out',
								message: 'Are you sure you want to log out?',
								confirmText: 'Log Out',
								variant: 'warning',
								onConfirm: () => {
									setConfirmDialog({ open: false })
									logout();
									navigate('/login/instructor')
								},
							})
						}}
						className="w-48 text-left px-4 py-2 rounded transition-all duration-300 ease-out font-semibold tracking-wide flex items-center gap-3 text-white/90 hover:text-white hover:bg-red-600/20"
					>
						<span className="text-white/90">
							<img src="/assets/out.png" alt="Logout" className="w-4 h-4 object-contain" onError={(e) => { e.currentTarget.style.display = 'none' }} />
						</span>
						<span>Logout</span>
					</button>
				</div>
			</aside>
			<main className="flex-1 bg-[url('/assets/bg-circuit.png')] bg-cover bg-fixed">
				<div className="p-6">
					<div className="flex justify-end items-center mb-4 gap-3">
						{/* Dark/Light Mode Toggle */}
						<button
							onClick={() => setIsDark(!isDark)}
							className="relative rounded-full w-14 h-14 bg-white/90 border border-white/60 shadow hover:shadow-lg transition-all duration-300 flex items-center justify-center"
							title={isDark ? 'Switch to Light Mode' : 'Switch to Dark Mode'}
						>
							{isDark ? (
								<svg className="w-6 h-6 text-yellow-500" fill="currentColor" viewBox="0 0 20 20">
									<path fillRule="evenodd" d="M10 2a1 1 0 011 1v1a1 1 0 11-2 0V3a1 1 0 011-1zm4 8a4 4 0 11-8 0 4 4 0 018 0zm-.464 4.95l.707.707a1 1 0 001.414-1.414l-.707-.707a1 1 0 00-1.414 1.414zm2.12-10.607a1 1 0 010 1.414l-.706.707a1 1 0 11-1.414-1.414l.707-.707a1 1 0 011.414 0zM17 11a1 1 0 100-2h-1a1 1 0 100 2h1zm-7 4a1 1 0 011 1v1a1 1 0 11-2 0v-1a1 1 0 011-1zM5.05 6.464A1 1 0 106.465 5.05l-.708-.707a1 1 0 00-1.414 1.414l.707.707zm1.414 8.486l-.707.707a1 1 0 01-1.414-1.414l.707-.707a1 1 0 011.414 1.414zM4 11a1 1 0 100-2H3a1 1 0 000 2h1z" clipRule="evenodd" />
								</svg>
							) : (
								<svg className="w-6 h-6 text-slate-600" fill="currentColor" viewBox="0 0 20 20">
									<path d="M17.293 13.293A8 8 0 016.707 2.707a8.001 8.001 0 1010.586 10.586z" />
								</svg>
							)}
						</button>
						{/* Notifications */}
						<button className="relative rounded-full w-14 h-14 bg-white/90 border border-white/60 shadow hover:shadow-lg transition-all duration-300" title="Notifications" onClick={() => navigate('/i/notifications')}>
							<img src="/assets/notification-bell.png" alt="Notifications" className="absolute inset-0 m-auto w-6 h-6 object-contain" onError={(e) => { e.currentTarget.style.display = 'none' }} />
						</button>
					</div>
					{isDashboard ? (
						<Outlet context={{ mustChangeCredentials, isDark }} />
					) : isAccount ? (
						<Outlet context={{ mustChangeCredentials, isDark }} />
					) : (
						<div className={`${isDark ? 'bg-slate-800/90' : 'bg-white/90'} rounded-xl shadow p-6`}>
							<div className="h-[520px] overflow-auto pr-1 [&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none]">
								<Outlet context={{ mustChangeCredentials, isDark }} />
							</div>
						</div>
					)}
				</div>
			</main>

			<ConfirmDialog
				{...confirmDialog}
				onCancel={() => setConfirmDialog({ open: false })}
			/>
		</div>
	)
}

