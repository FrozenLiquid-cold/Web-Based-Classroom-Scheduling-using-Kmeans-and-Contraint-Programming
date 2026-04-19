import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { useState } from 'react'
import { logout } from '../store/auth'

const navGroups = [
    { type: 'link', to: '/r/dashboard', label: 'Dashboard' },
    {
        type: 'group', label: 'Academics', icon: 'Academics',
        children: [
            { to: '/r/college', label: 'College' },
            { to: '/r/course', label: 'Program' },
            { to: '/r/curriculum', label: 'Curriculum' },
        ]
    },
    {
        type: 'group', label: 'Courses', icon: 'Courses',
        children: [
            { to: '/r/subject', label: 'Course' },
            { to: '/r/instructor', label: 'Instructor' },
        ]
    },
    {
        type: 'group', label: 'Facilities', icon: 'Facilities',
        children: [
            { to: '/r/buildings', label: 'Buildings' },
            { to: '/r/room', label: 'Room' },
            { to: '/r/distances', label: 'Matrix' },
        ]
    },
    {
        type: 'group', label: 'Schedule', icon: 'Schedule',
        children: [
            { to: '/r/schedule', label: 'Scheduler' },
            { to: '/r/schedule#dashboard', label: 'Dashboard' },
            { to: '/r/schedule#room-schedule', label: 'Room Schedule' },
        ]
    },
    {
        type: 'group', label: 'Settings', icon: 'Settings',
        children: [
            { to: '/r/day', label: 'Day' },
            { to: '/r/settings#timeslots', label: 'Time Slots' },
            { to: '/r/settings#day-patterns', label: 'Day Patterns' },
            { to: '/r/settings#load-limits', label: 'Load Limits' },
            { to: '/r/settings#deductions', label: 'Deductions' },
        ]
    },
    { type: 'link', to: '/r/account', label: 'Account' },
]

function NavIcon({ label }) {
    const common = 'w-4 h-4';
    switch (label) {
        case 'Dashboard':
            return (<svg className={common} viewBox="0 0 24 24" fill="currentColor" aria-hidden><path d="M3 13h8V3H3v10zm0 8h8v-6H3v6zm10 0h8v-10h-8v10zm0-18v6h8V3h-8z" /></svg>)
        case 'College':
            return (<svg className={common} viewBox="0 0 24 24" fill="currentColor" aria-hidden><path d="M12 2L1 7l11 5 9-4.09V17h2V7L12 2zM3 19h18v2H3z" /></svg>)
        case 'Program':
            return (<svg className={common} viewBox="0 0 24 24" fill="currentColor" aria-hidden><path d="M4 3h16v2H4V3zm0 4h16v12H4V7zm2 2v8h12V9H6z" /></svg>)
        case 'Instructor':
            return (<svg className={common} viewBox="0 0 24 24" fill="currentColor" aria-hidden><path d="M12 12c2.761 0 5-2.239 5-5s-2.239-5-5-5-5 2.239-5 5 2.239 5 5 5zm0 2c-3.866 0-7 3.134-7 7h2a5 5 0 0110 0h2c0-3.866-3.134-7-7-7z" /></svg>)
        case 'Day':
            return (<svg className={common} viewBox="0 0 24 24" fill="currentColor" aria-hidden><path d="M7 2v2H5a2 2 0 00-2 2v3h18V6a2 2 0 00-2-2h-2V2h-2v2H9V2H7zm14 9H3v9a2 2 0 002 2h14a2 2 0 002-2v-9z" /></svg>)
        case 'Course':
            return (<svg className={common} viewBox="0 0 24 24" fill="currentColor" aria-hidden><path d="M6 2h9l5 5v15a2 2 0 01-2 2H6a2 2 0 01-2-2V4a2 2 0 012-2zm8 6h4.5L14 3.5V8z" /></svg>)
        case 'Room':
            return (<svg className={common} viewBox="0 0 24 24" fill="currentColor" aria-hidden><path d="M12 3l10 9h-3v9H5v-9H2l10-9z" /></svg>)
        case 'Buildings':
            return (<svg className={common} viewBox="0 0 24 24" fill="currentColor" aria-hidden><path d="M4 22V8h16v14h-4v-8h-8v8H4zm2-2h4v-6h4v6h4v-8H6v8z" /></svg>)
        case 'Matrix':
            return (<svg className={common} viewBox="0 0 24 24" fill="currentColor" aria-hidden><path d="M8 2h8v2H8V2zm4 4h4v2h-4V6zm-6 4h4v2H6v-2zm8 4h4v2h-4v-2zM6 18h4v2H6v-2z" /></svg>)
        case 'Curriculum':
            return (<svg className={common} viewBox="0 0 24 24" fill="currentColor" aria-hidden><path d="M4 4h16v2H4V4zm0 4h10v2H4V8zm0 4h16v2H4v-2zm0 4h10v2H4v-2z" /></svg>)
        case 'Schedule':
            return (<svg className={common} viewBox="0 0 24 24" fill="currentColor" aria-hidden><path d="M12 1a11 11 0 1011 11A11.012 11.012 0 0012 1zm1 11V6h-2v8h7v-2z" /></svg>)
        case 'Account':
            return (<svg className={common} viewBox="0 0 24 24" fill="currentColor" aria-hidden><path d="M12 12c2.761 0 5-2.239 5-5s-2.239-5-5-5-5 2.239-5 5 2.239 5 5 5zm0 2c-3.866 0-7 3.134-7 7h2a5 5 0 0110 0h2c0-3.866-3.134-7-7-7z" /></svg>)
        case 'Settings':
            return (<svg className={common} viewBox="0 0 24 24" fill="currentColor" aria-hidden><path d="M19.14 12.94c.04-.31.06-.63.06-.94 0-.31-.02-.63-.06-.94l2.03-1.58a.49.49 0 00.12-.61l-1.92-3.32a.49.49 0 00-.59-.22l-2.39.96c-.5-.38-1.03-.7-1.62-.94l-.36-2.54a.48.48 0 00-.48-.41h-3.84a.48.48 0 00-.48.41l-.36 2.54c-.59.24-1.13.57-1.62.94l-2.39-.96a.49.49 0 00-.59.22L2.74 8.87a.48.48 0 00.12.61l2.03 1.58c-.04.31-.06.63-.06.94s.02.63.06.94l-2.03 1.58a.49.49 0 00-.12.61l1.92 3.32c.12.22.37.29.59.22l2.39-.96c.5.38 1.03.7 1.62.94l.36 2.54c.05.24.26.41.48.41h3.84c.24 0 .44-.17.48-.41l.36-2.54c.59-.24 1.13-.56 1.62-.94l2.39.96c.22.08.47 0 .59-.22l1.92-3.32c.12-.22.07-.47-.12-.61l-2.01-1.58zM12 15.6A3.6 3.6 0 1115.6 12 3.61 3.61 0 0112 15.6z" /></svg>)
        // Group icons
        case 'Academics':
            return (<svg className={common} viewBox="0 0 24 24" fill="currentColor" aria-hidden><path d="M12 2L1 7l11 5 11-5-11-5zM1 17l11 5 11-5-11-5-11 5z" /></svg>)
        case 'Courses':
            return (<svg className={common} viewBox="0 0 24 24" fill="currentColor" aria-hidden><path d="M21 5c-1.11-.35-2.33-.5-3.5-.5-1.95 0-4.05.4-5.5 1.5-1.45-1.1-3.55-1.5-5.5-1.5S2.45 4.9 1 6v14.65c0 .25.25.5.5.5.1 0 .15-.05.25-.05C3.1 20.45 5.05 20 6.5 20c1.95 0 4.05.4 5.5 1.5 1.35-.85 3.8-1.5 5.5-1.5 1.65 0 3.35.3 4.75 1.05.1.05.15.05.25.05.25 0 .5-.25.5-.5V6c-.6-.45-1.25-.75-2-1zm0 13.5c-1.1-.35-2.3-.5-3.5-.5-1.7 0-4.15.65-5.5 1.5V8c1.35-.85 3.8-1.5 5.5-1.5 1.2 0 2.4.15 3.5.5v11.5z" /></svg>)
        case 'Facilities':
            return (<svg className={common} viewBox="0 0 24 24" fill="currentColor" aria-hidden><path d="M15 11V5l-3-3-3 3v2H3v14h18V11h-6zm-8 8H5v-2h2v2zm0-4H5v-2h2v2zm0-4H5V9h2v2zm6 8h-2v-2h2v2zm0-4h-2v-2h2v2zm0-4h-2V9h2v2zm0-4h-2V5h2v2zm6 12h-2v-2h2v2zm0-4h-2v-2h2v2z" /></svg>)
        case 'Scheduling':
            return (<svg className={common} viewBox="0 0 24 24" fill="currentColor" aria-hidden><path d="M19 4h-1V2h-2v2H8V2H6v2H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 16H5V10h14v10zM9 14H7v-2h2v2zm4 0h-2v-2h2v2zm4 0h-2v-2h2v2zm-8 4H7v-2h2v2zm4 0h-2v-2h2v2zm4 0h-2v-2h2v2z" /></svg>)
        // Sub-nav icons
        case 'Time Slots':
            return (<svg className={common} viewBox="0 0 24 24" fill="currentColor" aria-hidden><path d="M11.99 2C6.47 2 2 6.48 2 12s4.47 10 9.99 10C17.52 22 22 17.52 22 12S17.52 2 11.99 2zM12 20c-4.42 0-8-3.58-8-8s3.58-8 8-8 8 3.58 8 8-3.58 8-8 8zm.5-13H11v6l5.25 3.15.75-1.23-4.5-2.67z"/></svg>)
        case 'Day Patterns':
            return (<svg className={common} viewBox="0 0 24 24" fill="currentColor" aria-hidden><path d="M19 4h-1V2h-2v2H8V2H6v2H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 16H5V10h14v10zM9 14H7v-2h2v2zm4 0h-2v-2h2v2zm4 0h-2v-2h2v2zm-8 4H7v-2h2v2zm4 0h-2v-2h2v2zm4 0h-2v-2h2v2z"/></svg>)
        case 'Load Limits':
            return (<svg className={common} viewBox="0 0 24 24" fill="currentColor" aria-hidden><path d="M16 6l2.29 2.29-4.88 4.88-4-4L2 16.59 3.41 18l6-6 4 4 6.3-6.29L22 12V6z"/></svg>)
        case 'Deductions':
            return (<svg className={common} viewBox="0 0 24 24" fill="currentColor" aria-hidden><path d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm-2 10H7v-2h10v2z"/></svg>)
        case 'Scheduler':
            return (<svg className={common} viewBox="0 0 24 24" fill="currentColor" aria-hidden><path d="M19 4h-1V2h-2v2H8V2H6v2H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 16H5V10h14v10zM9 14H7v-2h2v2zm4 0h-2v-2h2v2zm4 0h-2v-2h2v2zm-8 4H7v-2h2v2zm4 0h-2v-2h2v2zm4 0h-2v-2h2v2z"/></svg>)
        case 'Room Schedule':
            return (<svg className={common} viewBox="0 0 24 24" fill="currentColor" aria-hidden><path d="M15 11V5l-3-3-3 3v2H3v14h18V11h-6zm-8 8H5v-2h2v2zm0-4H5v-2h2v2zm0-4H5V9h2v2zm6 8h-2v-2h2v2zm0-4h-2v-2h2v2zm0-4h-2V9h2v2zm0-4h-2V5h2v2zm6 12h-2v-2h2v2zm0-4h-2v-2h2v2z"/></svg>)
        default:
            return null
    }
}

function ChevronIcon({ open }) {
    return (
        <svg className={`w-3.5 h-3.5 transition-transform duration-200 ${open ? 'rotate-90' : ''}`} viewBox="0 0 24 24" fill="currentColor">
            <path d="M8.59 16.59L13.17 12 8.59 7.41 10 6l6 6-6 6z" />
        </svg>
    )
}

export default function RegistrarLayout() {
    const { pathname } = useLocation()
    const isDashboard = pathname === '/r/dashboard' || pathname === '/r'

    // Auto-open the group that contains the current route
    const findActiveGroup = () => {
        for (const g of navGroups) {
            if (g.type === 'group' && g.children?.some(c => {
                const basePath = c.to.split('#')[0]
                return pathname.startsWith(basePath)
            })) {
                return g.label
            }
        }
        return null
    }
    const [openGroup, setOpenGroup] = useState(findActiveGroup)

    const toggleGroup = (label) => {
        setOpenGroup(prev => prev === label ? null : label)
    }

    return (
        <div className="min-h-screen flex">
            <aside className="w-64 bg-navy text-white p-6 space-y-4 flex flex-col items-center">
                <div className="flex flex-col items-center text-center space-y-3">
                    <img src="/assets/jrmsu-logo.png" alt="JRMSU" className="mx-auto w-16 h-16 object-contain" />
                    <div className="text-s tracking-wider">JOSE RIZAL MEMORIAL STATE UNIVERSITY</div>
                </div>
                <div className="text-gold font-bold text-lg text-center">CLASS - KCP</div>
                <nav className="flex flex-col items-center space-y-0.5 w-full px-2">
                    {navGroups.map(item => {
                        if (item.type === 'link') {
                            return (
                                <NavLink
                                    key={item.to}
                                    to={item.to}
                                    className={({ isActive }) => [
                                        'w-full text-left px-4 py-2 rounded transition-all duration-200 font-semibold tracking-wide flex items-center gap-3 text-sm',
                                        isActive ? 'bg-[#27308a] text-amber-300 shadow-inner font-extrabold' : 'text-white/90 hover:text-white hover:bg-[#222b80]'
                                    ].join(' ')}
                                >
                                    <span className="text-white/80"><NavIcon label={item.label} /></span>
                                    <span>{item.label}</span>
                                </NavLink>
                            )
                        }

                        // Group with accordion
                        const isOpen = openGroup === item.label
                        const hasActive = item.children?.some(c => {
                            const basePath = c.to.split('#')[0]
                            return pathname.startsWith(basePath)
                        })

                        return (
                            <div key={item.label} className="w-full">
                                <button
                                    onClick={() => toggleGroup(item.label)}
                                    className={[
                                        'w-full text-left px-4 py-2 rounded transition-all duration-200 font-semibold tracking-wide flex items-center gap-3 text-sm',
                                        hasActive ? 'text-amber-300' : 'text-white/70 hover:text-white hover:bg-[#222b80]'
                                    ].join(' ')}
                                >
                                    <span className="text-white/60"><NavIcon label={item.icon} /></span>
                                    <span className="flex-1">{item.label}</span>
                                    <ChevronIcon open={isOpen} />
                                </button>
                                <div className={`overflow-hidden transition-all duration-200 ${isOpen ? 'max-h-60 opacity-100' : 'max-h-0 opacity-0'}`}>
                                    <div className="ml-3 pl-3 border-l border-white/20 space-y-0.5 py-1">
                                        {item.children.map(child => {
                                            const hasHash = child.to.includes('#')
                                            const basePath = child.to.split('#')[0]
                                            const hash = child.to.split('#')[1]
                                            // For hash links: match base path + hash
                                            // For non-hash links in a group that has hash siblings: match path + no hash present
                                            const groupHasHashChildren = item.children.some(c => c.to.includes('#'))
                                            const childActive = hasHash
                                                ? pathname.startsWith(basePath) && location.hash === `#${hash}`
                                                : groupHasHashChildren
                                                    ? pathname === child.to && !location.hash
                                                    : pathname.startsWith(child.to)
                                            return (
                                                <NavLink
                                                    key={child.to}
                                                    to={child.to}
                                                    className={[
                                                        'w-full text-left px-3 py-1.5 rounded transition-all duration-200 font-medium tracking-wide flex items-center gap-2.5 text-[13px]',
                                                        childActive ? 'bg-[#27308a] text-amber-300 shadow-inner font-bold' : 'text-white/80 hover:text-white hover:bg-[#222b80]'
                                                    ].join(' ')}
                                                >
                                                    <span className="text-white/70"><NavIcon label={child.label} /></span>
                                                    <span>{child.label}</span>
                                                </NavLink>
                                            )
                                        })}
                                    </div>
                                </div>
                            </div>
                        )
                    })}
                </nav>
            </aside>
            <main className="flex-1 bg-[url('/assets/bg-circuit.png')] bg-cover bg-fixed">
                <div className="p-2">
                    {isDashboard ? (
                        <Outlet />
                    ) : (
                        <div className="bg-white/95 rounded-xl shadow p-4">
                            <div className="h-[calc(100vh-48px)] overflow-auto pr-1 [&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none]">
                                <Outlet />
                            </div>
                        </div>
                    )}
                </div>
            </main>
        </div>
    )
}
