import { useState, useEffect, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { logout } from '../../store/auth'
import { list } from '../../store/db'
import { updateProfile } from '../../services/api'

export default function InstructorAccount() {
    const navigate = useNavigate()
    const session = (() => {
        try { return JSON.parse(localStorage.getItem('jrmsu.session') || 'null') } catch { return null }
    })()

    const [instructorData, setInstructorData] = useState(null)
    const [specialization, setSpecialization] = useState([])
    const [specializationSearch, setSpecializationSearch] = useState('')
    const [subjects, setSubjects] = useState([])
    const [isDark, setIsDark] = useState(() => {
        const saved = localStorage.getItem('jrmsu.theme')
        return saved ? saved === 'dark' : false
    })

    useEffect(() => {
        localStorage.setItem('jrmsu.theme', isDark ? 'dark' : 'light')
    }, [isDark])

    useEffect(() => {
        async function loadInstructors() {
            if (!session?.instructorId) return

            const [instructorList, subjectList] = await Promise.all([
                list('instructor'),
                list('subject')
            ])
            const found = instructorList.find(i => i.id === session.instructorId)
            if (found) {
                setInstructorData(found)
                const raw = found.assignable_courses || found.assignableCourses || ''
                const parsed = raw.split(',').map(s => s.trim()).filter(Boolean)
                setSpecialization(parsed)
            }
            setSubjects(subjectList || [])
        }
        loadInstructors()
    }, [session?.instructorId])

    const [isEditing, setIsEditing] = useState(false)
    const [formData, setFormData] = useState({
        fullName: instructorData
            ? `${instructorData.first_name || instructorData.firstName || ''} ${instructorData.middle_name || instructorData.middleName || ''} ${instructorData.last_name || instructorData.lastName || ''}`.trim()
            : session?.username || '',
        username: session?.username || 'User',
        email: session?.email || '',
        password: '',
        confirmPassword: '',
        preferredStartTime: '',
        preferredEndTime: '',
        maxUnits: ''
    })

    useEffect(() => {
        if (instructorData) {
            setFormData({
                fullName: `${instructorData.first_name || instructorData.firstName || ''} ${instructorData.middle_name || instructorData.middleName || ''} ${instructorData.last_name || instructorData.lastName || ''}`.trim(),
                username: session?.username || (instructorData.username || `${instructorData.first_name || instructorData.firstName || ''} ${instructorData.last_name || instructorData.lastName || ''}`),
                email: session?.email || '',
                password: '',
                confirmPassword: '',
                preferredStartTime: instructorData.preferred_start_time || instructorData.preferredStartTime || '',
                preferredEndTime: instructorData.preferred_end_time || instructorData.preferredEndTime || '',
                maxUnits: instructorData.max_units !== null && instructorData.max_units !== undefined ? String(instructorData.max_units) : (instructorData.maxUnits !== null && instructorData.maxUnits !== undefined ? String(instructorData.maxUnits) : '')
            })
        }
    }, [instructorData])

    async function handleSave() {
        if (formData.password && formData.password !== formData.confirmPassword) {
            alert('Passwords do not match')
            return
        }
        try {
            const payload = {
                username: formData.username || undefined,
                password: formData.password || undefined,
                assignable_courses: specialization && specialization.length
                    ? specialization.join(',')
                    : undefined,
                preferred_start_time: formData.preferredStartTime || undefined,
                preferred_end_time: formData.preferredEndTime || undefined,
                max_units: formData.maxUnits ? parseInt(formData.maxUnits, 10) : undefined,
            }

            const result = await updateProfile(payload)

            if (!result || !result.ok) {
                alert(result?.detail || 'Failed to update profile')
                return
            }

            if (session?.instructorId) {
                const key = `jrmsu.instructor.mustChange.${session.instructorId}`
                localStorage.removeItem(key)
            }

            const newSession = {
                role: result.role,
                username: result.username,
                instructorId: result.instructor_id,
            }
            localStorage.setItem('jrmsu.session', JSON.stringify(newSession))

            setIsEditing(false)
            alert('Profile updated successfully!')
        } catch (error) {
            alert(error.message || 'Failed to update profile')
        }
    }

    function handleCancel() {
        setFormData({
            fullName: instructorData
                ? `${instructorData.first_name || instructorData.firstName || ''} ${instructorData.middle_name || instructorData.middleName || ''} ${instructorData.last_name || instructorData.lastName || ''}`.trim()
                : session?.username || '',
            username: session?.username || 'User',
            email: session?.email || '',
            password: '',
            confirmPassword: ''
        })
        setIsEditing(false)
    }

    const displayName = formData.fullName || formData.username || 'Instructor'

    const subjectOptions = useMemo(() => {
        const query = specializationSearch.trim().toLowerCase()
        const selectedSet = new Set(specialization)
        return (subjects || [])
            .filter(s => {
                if (!s || !s.code) return false
                if (selectedSet.has(s.code)) return false
                if (!query) return true
                const code = String(s.code || '').toLowerCase()
                const desc = String(s.description || '').toLowerCase()
                return code.includes(query) || desc.includes(query)
            })
            .slice(0, 10)
    }, [subjects, specialization, specializationSearch])

    function addSpecialization(code) {
        if (!code) return
        setSpecialization(prev => {
            if (prev.includes(code)) return prev
            return [...prev, code]
        })
    }

    function removeSpecialization(code) {
        setSpecialization(prev => prev.filter(c => c !== code))
    }

    // Professional university theme
    const theme = {
        bg: isDark ? 'bg-slate-900' : 'bg-gray-50',
        card: isDark ? 'bg-slate-800 border-slate-700' : 'bg-white border-gray-200',
        text: isDark ? 'text-white' : 'text-gray-900',
        textMuted: isDark ? 'text-slate-400' : 'text-gray-600',
        textLight: isDark ? 'text-slate-500' : 'text-gray-500',
        border: isDark ? 'border-slate-700' : 'border-gray-200',
        input: isDark ? 'bg-slate-700 border-slate-600 text-white placeholder-slate-400' : 'bg-white border-gray-300 text-gray-900 placeholder-gray-400',
        inputFocus: 'focus:ring-2 focus:ring-blue-500 focus:border-transparent',
    }

    return (
        <div className={`min-h-screen ${theme.bg} p-6`}>
            <div className="max-w-3xl mx-auto">
                {/* Header */}
                <div className="flex items-start justify-between mb-6">
                    <div>
                        <h1 className={`text-2xl font-semibold ${theme.text}`}>Account Settings</h1>
                        <p className={`${theme.textMuted} mt-1`}>Manage your profile and preferences</p>
                    </div>
                    <button
                        onClick={() => setIsDark(!isDark)}
                        className={`p-2 rounded-lg border ${theme.border} ${isDark ? 'bg-slate-700' : 'bg-white'} transition-colors`}
                        title={isDark ? 'Switch to Light Mode' : 'Switch to Dark Mode'}
                    >
                        {isDark ? (
                            <svg className="w-5 h-5 text-amber-400" fill="currentColor" viewBox="0 0 20 20">
                                <path fillRule="evenodd" d="M10 2a1 1 0 011 1v1a1 1 0 11-2 0V3a1 1 0 011-1zm4 8a4 4 0 11-8 0 4 4 0 018 0zm-.464 4.95l.707.707a1 1 0 001.414-1.414l-.707-.707a1 1 0 00-1.414 1.414zm2.12-10.607a1 1 0 010 1.414l-.706.707a1 1 0 11-1.414-1.414l.707-.707a1 1 0 011.414 0zM17 11a1 1 0 100-2h-1a1 1 0 100 2h1zm-7 4a1 1 0 011 1v1a1 1 0 11-2 0v-1a1 1 0 011-1zM5.05 6.464A1 1 0 106.465 5.05l-.708-.707a1 1 0 00-1.414 1.414l.707.707zm1.414 8.486l-.707.707a1 1 0 01-1.414-1.414l.707-.707a1 1 0 011.414 1.414zM4 11a1 1 0 100-2H3a1 1 0 000 2h1z" clipRule="evenodd" />
                            </svg>
                        ) : (
                            <svg className="w-5 h-5 text-gray-600" fill="currentColor" viewBox="0 0 20 20">
                                <path d="M17.293 13.293A8 8 0 016.707 2.707a8.001 8.001 0 1010.586 10.586z" />
                            </svg>
                        )}
                    </button>
                </div>

                {/* Profile Card */}
                <div className={`rounded-lg border ${theme.card} p-6 mb-6`}>
                    <div className="flex items-center justify-between pb-6 border-b border-inherit">
                        <div className="flex items-center gap-4">
                            <div className={`w-16 h-16 rounded-full flex items-center justify-center text-xl font-semibold ${isDark ? 'bg-blue-900/50 text-blue-300' : 'bg-blue-100 text-blue-700'}`}>
                                {displayName.charAt(0).toUpperCase()}
                            </div>
                            <div>
                                <h2 className={`text-lg font-semibold ${theme.text}`}>{displayName}</h2>
                                <p className={`text-sm ${theme.textMuted}`}>@{formData.username}</p>
                                <span className={`inline-block mt-1 px-2 py-0.5 rounded text-xs font-medium ${isDark ? 'bg-blue-900/50 text-blue-300' : 'bg-blue-100 text-blue-700'}`}>
                                    Faculty
                                </span>
                            </div>
                        </div>
                        {!isEditing && (
                            <button
                                className="px-4 py-2 rounded-lg bg-[#1d4ed8] text-white text-sm font-medium hover:bg-blue-700 transition-colors flex items-center gap-2"
                                onClick={() => setIsEditing(true)}
                            >
                                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                                </svg>
                                Edit
                            </button>
                        )}
                    </div>

                    {/* Form Fields */}
                    <div className="pt-6 space-y-5">
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                            <div>
                                <label className={`block text-xs font-medium ${theme.textMuted} uppercase tracking-wide mb-1`}>Full Name</label>
                                {isEditing ? (
                                    <input
                                        type="text"
                                        className={`w-full px-3 py-2 rounded-lg border ${theme.input} ${theme.inputFocus} text-sm outline-none`}
                                        value={formData.fullName}
                                        onChange={(e) => setFormData({ ...formData, fullName: e.target.value })}
                                        placeholder="Enter full name"
                                    />
                                ) : (
                                    <div className={`text-sm ${theme.text}`}>{formData.fullName || '—'}</div>
                                )}
                            </div>
                            <div>
                                <label className={`block text-xs font-medium ${theme.textMuted} uppercase tracking-wide mb-1`}>Username</label>
                                {isEditing ? (
                                    <input
                                        type="text"
                                        className={`w-full px-3 py-2 rounded-lg border ${theme.input} ${theme.inputFocus} text-sm outline-none`}
                                        value={formData.username}
                                        onChange={(e) => setFormData({ ...formData, username: e.target.value })}
                                        placeholder="Enter username"
                                    />
                                ) : (
                                    <div className={`text-sm ${theme.text}`}>{formData.username}</div>
                                )}
                            </div>
                        </div>

                        <div>
                            <label className={`block text-xs font-medium ${theme.textMuted} uppercase tracking-wide mb-1`}>Email Address</label>
                            {isEditing ? (
                                <input
                                    type="email"
                                    className={`w-full px-3 py-2 rounded-lg border ${theme.input} ${theme.inputFocus} text-sm outline-none`}
                                    value={formData.email}
                                    onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                                    placeholder="Enter email"
                                />
                            ) : (
                                <div className={`text-sm ${theme.text}`}>{formData.email || '—'}</div>
                            )}
                        </div>

                        {isEditing && (
                            <div className={`pt-5 border-t ${theme.border}`}>
                                <h3 className={`text-sm font-medium ${theme.text} mb-4`}>Change Password</h3>
                                <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                                    <div>
                                        <label className={`block text-xs font-medium ${theme.textMuted} uppercase tracking-wide mb-1`}>New Password</label>
                                        <input
                                            type="password"
                                            className={`w-full px-3 py-2 rounded-lg border ${theme.input} ${theme.inputFocus} text-sm outline-none`}
                                            value={formData.password}
                                            onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                                            placeholder="Leave blank to keep current"
                                        />
                                    </div>
                                    <div>
                                        <label className={`block text-xs font-medium ${theme.textMuted} uppercase tracking-wide mb-1`}>Confirm Password</label>
                                        <input
                                            type="password"
                                            className={`w-full px-3 py-2 rounded-lg border ${theme.input} ${theme.inputFocus} text-sm outline-none`}
                                            value={formData.confirmPassword}
                                            onChange={(e) => setFormData({ ...formData, confirmPassword: e.target.value })}
                                            placeholder="Confirm password"
                                        />
                                    </div>
                                </div>
                            </div>
                        )}
                    </div>
                </div>

                {/* Eligible Classes */}
                <div className={`rounded-lg border ${theme.card} p-6 mb-6`}>
                    <h3 className={`text-sm font-medium ${theme.textMuted} uppercase tracking-wide mb-4`}>Eligible Classes</h3>
                    {isEditing ? (
                        <div className="space-y-3">
                            <input
                                className={`w-full px-3 py-2 rounded-lg border ${theme.input} ${theme.inputFocus} text-sm outline-none`}
                                placeholder="Search subject code or description..."
                                value={specializationSearch}
                                onChange={e => setSpecializationSearch(e.target.value)}
                            />
                            {specialization.length > 0 && (
                                <div className="flex flex-wrap gap-2">
                                    {specialization.map(code => (
                                        <button
                                            key={code}
                                            type="button"
                                            className={`px-2 py-1 rounded text-xs font-medium flex items-center gap-1 ${isDark ? 'bg-blue-900/50 text-blue-300' : 'bg-blue-100 text-blue-700'}`}
                                            onClick={() => removeSpecialization(code)}
                                        >
                                            <span>{code}</span>
                                            <span className="opacity-60">×</span>
                                        </button>
                                    ))}
                                </div>
                            )}
                            <div className={`max-h-40 overflow-auto rounded-lg border ${theme.border} ${isDark ? 'bg-slate-700/50' : 'bg-gray-50'}`}>
                                {subjectOptions.length === 0 && (
                                    <div className={`px-3 py-2 text-sm ${theme.textMuted}`}>No matching subjects</div>
                                )}
                                {subjectOptions.map(s => (
                                    <button
                                        key={s.id}
                                        type="button"
                                        className={`w-full text-left px-3 py-2 text-sm ${isDark ? 'hover:bg-slate-600/50' : 'hover:bg-gray-100'} border-b last:border-b-0 ${theme.border} transition-colors`}
                                        onClick={() => addSpecialization(s.code)}
                                    >
                                        <span className={`font-medium ${theme.text}`}>{s.code}</span>
                                        <span className={`ml-2 ${theme.textMuted}`}>{s.description}</span>
                                    </button>
                                ))}
                            </div>
                        </div>
                    ) : (
                        <div className="flex flex-wrap gap-2">
                            {specialization && specialization.length ? (
                                specialization.map(code => (
                                    <span key={code} className={`px-2 py-1 rounded text-xs font-medium ${isDark ? 'bg-slate-600 text-slate-300' : 'bg-gray-100 text-gray-700'}`}>
                                        {code}
                                    </span>
                                ))
                            ) : (
                                <span className={theme.textMuted}>No classes assigned</span>
                            )}
                        </div>
                    )}
                </div>

                {/* Teaching Preferences */}
                <div className={`rounded-lg border ${theme.card} p-6 mb-6`}>
                    <h3 className={`text-sm font-medium ${theme.textMuted} uppercase tracking-wide mb-4`}>Teaching Preferences</h3>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
                        <div>
                            <label className={`block text-xs font-medium ${theme.textMuted} uppercase tracking-wide mb-1`}>Preferred Start Time</label>
                            {isEditing ? (
                                <input
                                    type="time"
                                    className={`w-full px-3 py-2 rounded-lg border ${theme.input} ${theme.inputFocus} text-sm outline-none`}
                                    value={formData.preferredStartTime}
                                    onChange={(e) => setFormData({ ...formData, preferredStartTime: e.target.value })}
                                />
                            ) : (
                                <div className={`text-sm ${theme.text}`}>{formData.preferredStartTime || '—'}</div>
                            )}
                        </div>
                        <div>
                            <label className={`block text-xs font-medium ${theme.textMuted} uppercase tracking-wide mb-1`}>Preferred End Time</label>
                            {isEditing ? (
                                <input
                                    type="time"
                                    className={`w-full px-3 py-2 rounded-lg border ${theme.input} ${theme.inputFocus} text-sm outline-none`}
                                    value={formData.preferredEndTime}
                                    onChange={(e) => setFormData({ ...formData, preferredEndTime: e.target.value })}
                                />
                            ) : (
                                <div className={`text-sm ${theme.text}`}>{formData.preferredEndTime || '—'}</div>
                            )}
                        </div>
                        <div>
                            <label className={`block text-xs font-medium ${theme.textMuted} uppercase tracking-wide mb-1`}>Max Units</label>
                            {isEditing ? (
                                <input
                                    type="number"
                                    min="0"
                                    max="50"
                                    className={`w-full px-3 py-2 rounded-lg border ${theme.input} ${theme.inputFocus} text-sm outline-none`}
                                    value={formData.maxUnits}
                                    onChange={(e) => setFormData({ ...formData, maxUnits: e.target.value })}
                                    placeholder="e.g., 21"
                                />
                            ) : (
                                <div className={`text-sm ${theme.text}`}>{formData.maxUnits || '—'}</div>
                            )}
                        </div>
                    </div>
                </div>

                {/* Action Buttons */}
                {isEditing && (
                    <div className="flex items-center gap-3 mb-6">
                        <button
                            className="px-5 py-2 rounded-lg bg-[#1d4ed8] text-white text-sm font-medium hover:bg-blue-700 transition-colors"
                            onClick={handleSave}
                        >
                            Save Changes
                        </button>
                        <button
                            className={`px-5 py-2 rounded-lg border ${theme.border} ${theme.text} text-sm font-medium hover:bg-gray-100 dark:hover:bg-slate-700 transition-colors`}
                            onClick={handleCancel}
                        >
                            Cancel
                        </button>
                    </div>
                )}

                {/* Logout */}
                <div className={`rounded-lg border border-red-200 ${isDark ? 'bg-red-900/10' : 'bg-red-50'} p-6`}>
                    <h3 className="text-sm font-medium text-red-700 mb-2">Sign Out</h3>
                    <p className={`text-sm ${isDark ? 'text-red-300' : 'text-red-600'} mb-4`}>End your current session and return to the login page.</p>
                    <button
                        className="px-4 py-2 rounded-lg bg-red-600 text-white text-sm font-medium hover:bg-red-700 transition-colors flex items-center gap-2"
                        onClick={() => {
                            if (confirm('Are you sure you want to log out?')) {
                                logout()
                                navigate('/login/instructor')
                            }
                        }}
                    >
                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
                        </svg>
                        Sign Out
                    </button>
                </div>
            </div>
        </div>
    )
}
