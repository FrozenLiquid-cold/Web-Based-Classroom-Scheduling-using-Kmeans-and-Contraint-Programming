import { NavLink, Outlet, useNavigate, useLocation } from 'react-router-dom'
import { logout } from '../store/auth'

const nav = [
    { to: '/a/dashboard', label: 'Dashboard' },
    { to: '/a/users', label: 'Users' },
]

function NavIcon({ label }) {
    const common = 'w-4 h-4';
    switch (label) {
        case 'Dashboard':
            return (
                <svg className={common} viewBox="0 0 24 24" fill="currentColor" aria-hidden>
                    <path d="M3 13h8V3H3v10zm0 8h8v-6H3v6zm10 0h8v-10h-8v10zm0-18v6h8V3h-8z"/>
                </svg>
            )
        case 'Users':
            return (
                <svg className={common} viewBox="0 0 24 24" fill="currentColor" aria-hidden>
                    <path d="M16 11c1.66 0 2.99-1.34 2.99-3S17.66 5 16 5c-1.66 0-3 1.34-3 3s1.34 3 3 3zm-8 0c1.66 0 2.99-1.34 2.99-3S9.66 5 8 5C6.34 5 5 6.34 5 8s1.34 3 3 3zm0 2c-2.33 0-7 1.17-7 3.5V19h14v-2.5c0-2.33-4.67-3.5-7-3.5zm8 0c-.29 0-.62.02-.97.05 1.16.84 1.97 1.97 1.97 3.45V19h6v-2.5c0-2.33-4.67-3.5-7-3.5z"/>
                </svg>
            )
        default:
            return null
    }
}

export default function AdminLayout() {
	const navigate = useNavigate()
	const { pathname } = useLocation()
	const isDashboard = pathname === '/a/dashboard' || pathname === '/a'

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
                            className={({isActive})=>[
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
						onClick={()=>{ 
							if(confirm('Are you sure you want to log out?')) {
								logout(); 
								navigate('/login/admin')
							}
						}}
						className="w-48 text-left px-4 py-2 rounded transition-all duration-300 ease-out font-semibold tracking-wide flex items-center gap-3 text-white/90 hover:text-white hover:bg-red-600/20"
					>
						<span className="text-white/90">
							<img src="/assets/out.png" alt="Logout" className="w-4 h-4 object-contain" onError={(e)=>{e.currentTarget.style.display='none'}} />
						</span>
						<span>Logout</span>
					</button>
				</div>
			</aside>
			<main className="flex-1 bg-[url('/assets/bg-circuit.png')] bg-cover bg-fixed">
				<div className="p-6">
					{isDashboard ? (
						<Outlet />
					) : (
						<div className="bg-white/90 rounded-xl shadow p-6">
							<div className="h-[520px] overflow-auto pr-1 [&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none]">
								<Outlet />
							</div>
						</div>
					)}
				</div>
			</main>
		</div>
	)
}


