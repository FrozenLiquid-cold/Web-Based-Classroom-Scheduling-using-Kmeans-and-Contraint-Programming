import { NavLink, Outlet, useNavigate, useLocation } from 'react-router-dom'
import { logout } from '../store/auth'

const nav = [
    { to: '/r/dashboard', label: 'Dashboard' },
    { to: '/r/college', label: 'College' },
    { to: '/r/course', label: 'Course' },
    { to: '/r/instructor', label: 'Instructor' },
    { to: '/r/day', label: 'Day' },
    { to: '/r/subject', label: 'Subject' },
    { to: '/r/room', label: 'Room' },
    { to: '/r/buildings', label: 'Buildings' },
    { to: '/r/distances', label: 'Matrix' },
    { to: '/r/schedule', label: 'Schedule' },
    { to: '/r/curriculum', label: 'Curriculum' },
    { to: '/r/account', label: 'Account' },
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
        case 'College':
            return (
                <svg className={common} viewBox="0 0 24 24" fill="currentColor" aria-hidden>
                    <path d="M12 2L1 7l11 5 9-4.09V17h2V7L12 2zM3 19h18v2H3z" />
                </svg>
            )
        case 'Course':
            return (
                <svg className={common} viewBox="0 0 24 24" fill="currentColor" aria-hidden>
                    <path d="M4 3h16v2H4V3zm0 4h16v12H4V7zm2 2v8h12V9H6z" />
                </svg>
            )
        case 'Instructor':
            return (
                <svg className={common} viewBox="0 0 24 24" fill="currentColor" aria-hidden>
                    <path d="M12 12c2.761 0 5-2.239 5-5s-2.239-5-5-5-5 2.239-5 5 2.239 5 5 5zm0 2c-3.866 0-7 3.134-7 7h2a5 5 0 0110 0h2c0-3.866-3.134-7-7-7z" />
                </svg>
            )
        case 'Day':
            return (
                <svg className={common} viewBox="0 0 24 24" fill="currentColor" aria-hidden>
                    <path d="M7 2v2H5a2 2 0 00-2 2v3h18V6a2 2 0 00-2-2h-2V2h-2v2H9V2H7zm14 9H3v9a2 2 0 002 2h14a2 2 0 002-2v-9z" />
                </svg>
            )
        case 'Subject':
            return (
                <svg className={common} viewBox="0 0 24 24" fill="currentColor" aria-hidden>
                    <path d="M6 2h9l5 5v15a2 2 0 01-2 2H6a2 2 0 01-2-2V4a2 2 0 012-2zm8 6h4.5L14 3.5V8z" />
                </svg>
            )
        case 'Room':
            return (
                <svg className={common} viewBox="0 0 24 24" fill="currentColor" aria-hidden>
                    <path d="M12 3l10 9h-3v9H5v-9H2l10-9z" />
                </svg>
            )
        case 'Buildings':
            return (
                <svg className={common} viewBox="0 0 24 24" fill="currentColor" aria-hidden>
                    <path d="M4 22V8h16v14h-4v-8h-8v8H4zm2-2h4v-6h4v6h4v-8H6v8z" />
                </svg>
            )
        case 'Matrix':
            return (
                <svg className={common} viewBox="0 0 24 24" fill="currentColor" aria-hidden>
                    <path d="M8 2h8v2H8V2zm4 4h4v2h-4V6zm-6 4h4v2H6v-2zm8 4h4v2h-4v-2zM6 18h4v2H6v-2z" />
                </svg>
            )
        case 'Curriculum':
            return (
                <svg className={common} viewBox="0 0 24 24" fill="currentColor" aria-hidden>
                    <path d="M4 4h16v2H4V4zm0 4h10v2H4V8zm0 4h16v2H4v-2zm0 4h10v2H4v-2z" />
                </svg>
            )
        case 'Schedule':
            return (
                <svg className={common} viewBox="0 0 24 24" fill="currentColor" aria-hidden>
                    <path d="M12 1a11 11 0 1011 11A11.012 11.012 0 0012 1zm1 11V6h-2v8h7v-2z" />
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

export default function RegistrarLayout() {
    const navigate = useNavigate()
    const { pathname } = useLocation()
    const isDashboard = pathname === '/r/dashboard' || pathname === '/r'
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
                {/* Logout moved to Users section */}
            </aside>
            <main className="flex-1 bg-[url('/assets/bg-circuit.png')] bg-cover bg-fixed">
                <div className="p-6">
                    <div className="flex justify-end items-center mb-4">
                        <button className="relative rounded-full w-14 h-14 bg-white/90 border border-white/60 shadow hover:shadow-lg transition-all duration-300" title="Notifications" onClick={() => navigate('/r/user')}>
                            <img src="/assets/notification-bell.png" alt="Notifications" className="absolute inset-0 m-auto w-6 h-6 object-contain" onError={(e) => { e.currentTarget.style.display = 'none' }} />
                        </button>
                    </div>
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

