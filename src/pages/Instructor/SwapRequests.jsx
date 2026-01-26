import { useEffect, useState } from 'react'
import { useOutletContext } from 'react-router-dom'
import {
    getIncomingSwapRequests,
    getOutgoingSwapRequests,
    acceptSwapRequest,
    rejectSwapRequest
} from '../../services/api'

export default function SwapRequests() {
    const { isDark } = useOutletContext() || { isDark: false }
    const [activeTab, setActiveTab] = useState('incoming')
    const [incoming, setIncoming] = useState([])
    const [outgoing, setOutgoing] = useState([])
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState('')
    const [actionMessage, setActionMessage] = useState('')
    const [showRejectModal, setShowRejectModal] = useState(false)
    const [rejectingId, setRejectingId] = useState(null)
    const [rejectReason, setRejectReason] = useState('')

    // Theme configuration
    const theme = {
        bg: isDark ? 'bg-slate-900' : 'bg-white', // Main background handled by layout usually, but for safe measure
        text: isDark ? 'text-white' : 'text-gray-900',
        textMuted: isDark ? 'text-slate-400' : 'text-gray-500',
        card: isDark ? 'bg-slate-800 border-slate-700' : 'bg-white border-gray-200',
        border: isDark ? 'border-slate-700' : 'border-gray-200',
        input: isDark ? 'bg-slate-700 border-slate-600 text-white placeholder-slate-400' : 'bg-white border-gray-300 text-gray-900 placeholder-gray-400',
        hover: isDark ? 'hover:bg-slate-700' : 'hover:bg-gray-50',
        tabActive: isDark ? 'border-blue-500 text-blue-400' : 'border-blue-500 text-blue-600',
        tabInactive: isDark ? 'border-transparent text-slate-400 hover:text-slate-200' : 'border-transparent text-gray-500 hover:text-gray-700',
        badge: {
            pending: isDark ? 'bg-yellow-900/30 text-yellow-300' : 'bg-yellow-100 text-yellow-800',
            accepted: isDark ? 'bg-green-900/30 text-green-300' : 'bg-green-100 text-green-800',
            rejected: isDark ? 'bg-red-900/30 text-red-300' : 'bg-red-100 text-red-800'
        },
        scheduleOffer: isDark ? 'bg-blue-900/20' : 'bg-blue-50',
        scheduleRequest: isDark ? 'bg-orange-900/20' : 'bg-orange-50'
    }

    // Get instructor ID from session
    const getInstructorId = () => {
        try {
            const session = JSON.parse(localStorage.getItem('jrmsu.session') || '{}')
            return session.instructorId
        } catch {
            return null
        }
    }

    const instructorId = getInstructorId()

    const loadRequests = async () => {
        if (!instructorId) {
            setError('No instructor ID found')
            setLoading(false)
            return
        }

        setLoading(true)
        setError('')

        try {
            const [incomingData, outgoingData] = await Promise.all([
                getIncomingSwapRequests(instructorId),
                getOutgoingSwapRequests(instructorId)
            ])
            setIncoming(incomingData.requests || [])
            setOutgoing(outgoingData.requests || [])
        } catch (err) {
            setError(err.message || 'Failed to load swap requests')
        } finally {
            setLoading(false)
        }
    }

    useEffect(() => {
        loadRequests()
    }, [instructorId])

    const handleAccept = async (requestId) => {
        try {
            await acceptSwapRequest(requestId)
            setActionMessage('Swap accepted successfully! Schedules have been exchanged.')
            loadRequests()
            setTimeout(() => setActionMessage(''), 5000)
        } catch (err) {
            setError(err.message || 'Failed to accept swap')
        }
    }

    const openRejectModal = (requestId) => {
        setRejectingId(requestId)
        setRejectReason('')
        setShowRejectModal(true)
    }

    const handleReject = async () => {
        if (!rejectingId) return

        try {
            await rejectSwapRequest(rejectingId, rejectReason)
            setActionMessage('Swap request rejected.')
            setShowRejectModal(false)
            setRejectingId(null)
            loadRequests()
            setTimeout(() => setActionMessage(''), 5000)
        } catch (err) {
            setError(err.message || 'Failed to reject swap')
        }
    }

    const formatDate = (dateStr) => {
        if (!dateStr) return '—'
        return new Date(dateStr).toLocaleString()
    }

    // Convert 24-hour time to 12-hour format
    const formatTime12Hour = (timeStr) => {
        if (!timeStr) return '—'

        // Handle time ranges like "16:00:00–19:00:00" or "15:00–17:00"
        const parts = timeStr.split(/[–-]/).map(t => t.trim())

        const convertSingle = (t) => {
            // Extract hours and minutes from formats like "16:00:00", "16:00", "M 15:00"
            const cleaned = t.replace(/^[MTWTHFSAT]+\s*/i, '') // Remove day prefix
            const match = cleaned.match(/(\d{1,2}):(\d{2})/)
            if (!match) return t

            let hours = parseInt(match[1], 10)
            const minutes = match[2]
            const period = hours >= 12 ? 'PM' : 'AM'

            if (hours === 0) hours = 12
            else if (hours > 12) hours -= 12

            return `${hours}:${minutes} ${period}`
        }

        if (parts.length === 2) {
            return `${convertSingle(parts[0])} - ${convertSingle(parts[1])}`
        }
        return convertSingle(timeStr)
    }

    const getStatusBadge = (status) => {
        return (
            <span className={`px-2 py-1 rounded-full text-xs font-medium ${theme.badge[status] || 'bg-gray-100 text-gray-800'}`}>
                {status.charAt(0).toUpperCase() + status.slice(1)}
            </span>
        )
    }

    const renderScheduleInfo = (schedule, label) => {
        if (!schedule) return <span className={theme.textMuted}>No data</span>
        return (
            <div className="text-sm">
                <div className={`font-medium ${theme.text}`}>{label}</div>
                <div className={theme.textMuted}>
                    {schedule.subject_code} - {schedule.subject_description}
                </div>
                <div className={isDark ? 'text-slate-500' : 'text-gray-500'}>
                    {schedule.day_label} • {formatTime12Hour(schedule.time)} • {schedule.room_name}
                </div>
            </div>
        )
    }

    const pendingIncoming = incoming.filter(r => r.status === 'pending')

    return (
        <div className={`p-6 max-w-5xl mx-auto min-h-screen ${isDark ? 'bg-transparent' : 'bg-transparent'}`}>
            <h1 className={`text-2xl font-semibold mb-6 ${theme.text}`}>Schedule Swap Requests</h1>

            {error && (
                <div className={`mb-4 p-3 border rounded ${isDark ? 'bg-red-900/20 border-red-800 text-red-300' : 'bg-red-50 border-red-200 text-red-700'}`}>
                    {error}
                </div>
            )}

            {actionMessage && (
                <div className={`mb-4 p-3 border rounded ${isDark ? 'bg-green-900/20 border-green-800 text-green-300' : 'bg-green-50 border-green-200 text-green-700'}`}>
                    {actionMessage}
                </div>
            )}

            {/* Tabs */}
            <div className={`flex border-b mb-6 ${theme.border}`}>
                <button
                    onClick={() => setActiveTab('incoming')}
                    className={`px-4 py-2 font-medium border-b-2 transition-colors ${activeTab === 'incoming'
                        ? theme.tabActive
                        : theme.tabInactive
                        }`}
                >
                    Incoming
                    {pendingIncoming.length > 0 && (
                        <span className="ml-2 bg-red-500 text-white text-xs px-2 py-0.5 rounded-full">
                            {pendingIncoming.length}
                        </span>
                    )}
                </button>
                <button
                    onClick={() => setActiveTab('outgoing')}
                    className={`px-4 py-2 font-medium border-b-2 transition-colors ${activeTab === 'outgoing'
                        ? theme.tabActive
                        : theme.tabInactive
                        }`}
                >
                    Outgoing
                </button>
            </div>

            {loading ? (
                <div className={`text-center py-8 ${theme.textMuted}`}>Loading...</div>
            ) : (
                <div className="space-y-4">
                    {activeTab === 'incoming' ? (
                        incoming.length === 0 ? (
                            <div className={`text-center py-8 ${theme.textMuted}`}>
                                No incoming swap requests
                            </div>
                        ) : (
                            incoming.map(req => (
                                <div
                                    key={req.id}
                                    className={`border rounded-lg p-4 shadow-sm ${theme.card}`}
                                >
                                    <div className="flex justify-between items-start mb-3">
                                        <div>
                                            <span className={`font-medium ${theme.text}`}>
                                                From: {req.requester_name || 'Unknown'}
                                            </span>
                                            <div className={`text-xs mt-1 ${theme.textMuted}`}>
                                                {formatDate(req.created_at)}
                                            </div>
                                        </div>
                                        {getStatusBadge(req.status)}
                                    </div>

                                    <div className="grid grid-cols-2 gap-4 mb-3">
                                        <div className={`p-3 rounded ${theme.scheduleOffer}`}>
                                            {renderScheduleInfo(req.requester_schedule, "They're offering:")}
                                        </div>
                                        <div className={`p-3 rounded ${theme.scheduleRequest}`}>
                                            {renderScheduleInfo(req.target_schedule, "For your:")}
                                        </div>
                                    </div>

                                    {req.reason && (
                                        <div className={`text-sm mb-3 ${theme.textMuted}`}>
                                            <span className="font-medium">Reason:</span> {req.reason}
                                        </div>
                                    )}

                                    {req.status === 'pending' && (
                                        <div className="flex gap-2">
                                            <button
                                                onClick={() => handleAccept(req.id)}
                                                className="px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700 transition-colors"
                                            >
                                                Accept Swap
                                            </button>
                                            <button
                                                onClick={() => openRejectModal(req.id)}
                                                className="px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700 transition-colors"
                                            >
                                                Reject
                                            </button>
                                        </div>
                                    )}

                                    {req.status === 'rejected' && req.rejection_reason && (
                                        <div className="text-sm text-red-600">
                                            <span className="font-medium">Rejection reason:</span> {req.rejection_reason}
                                        </div>
                                    )}
                                </div>
                            ))
                        )
                    ) : (
                        outgoing.length === 0 ? (
                            <div className={`text-center py-8 ${theme.textMuted}`}>
                                No outgoing swap requests. Go to your Schedule page to request a swap.
                            </div>
                        ) : (
                            outgoing.map(req => (
                                <div
                                    key={req.id}
                                    className={`border rounded-lg p-4 shadow-sm ${theme.card}`}
                                >
                                    <div className="flex justify-between items-start mb-3">
                                        <div>
                                            <span className={`font-medium ${theme.text}`}>
                                                To: {req.target_name || 'Unknown'}
                                            </span>
                                            <div className={`text-xs mt-1 ${theme.textMuted}`}>
                                                {formatDate(req.created_at)}
                                            </div>
                                        </div>
                                        {getStatusBadge(req.status)}
                                    </div>

                                    <div className="grid grid-cols-2 gap-4 mb-3">
                                        <div className={`p-3 rounded ${theme.scheduleRequest}`}>
                                            {renderScheduleInfo(req.requester_schedule, "Your schedule:")}
                                        </div>
                                        <div className={`p-3 rounded ${theme.scheduleOffer}`}>
                                            {renderScheduleInfo(req.target_schedule, "Requested:")}
                                        </div>
                                    </div>

                                    {req.reason && (
                                        <div className={`text-sm mb-3 ${theme.textMuted}`}>
                                            <span className="font-medium">Your reason:</span> {req.reason}
                                        </div>
                                    )}

                                    {req.status === 'rejected' && req.rejection_reason && (
                                        <div className="text-sm text-red-600">
                                            <span className="font-medium">Rejection reason:</span> {req.rejection_reason}
                                        </div>
                                    )}

                                    {req.status === 'accepted' && (
                                        <div className="text-sm text-green-600 font-medium">
                                            ✓ Swap completed! Your schedules have been exchanged.
                                        </div>
                                    )}
                                </div>
                            ))
                        )
                    )}
                </div>
            )}

            {/* Reject Modal */}
            {showRejectModal && (
                <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
                    <div className={`rounded-lg p-6 w-full max-w-md ${isDark ? 'bg-slate-800' : 'bg-white'}`}>
                        <h3 className={`text-lg font-semibold mb-4 ${theme.text}`}>Reject Swap Request</h3>
                        <label className={`block text-sm font-medium mb-2 ${theme.textMuted}`}>
                            Reason (optional):
                        </label>
                        <textarea
                            value={rejectReason}
                            onChange={(e) => setRejectReason(e.target.value)}
                            className={`w-full border rounded px-3 py-2 mb-4 ${theme.input} ${theme.border}`}
                            rows={3}
                            placeholder="Enter a reason for rejection..."
                        />
                        <div className="flex justify-end gap-2">
                            <button
                                onClick={() => setShowRejectModal(false)}
                                className={`px-4 py-2 border rounded transition-colors ${theme.border} ${theme.text} ${theme.hover}`}
                            >
                                Cancel
                            </button>
                            <button
                                onClick={handleReject}
                                className="px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700"
                            >
                                Reject
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    )
}
