import { useEffect, useRef } from 'react'

/**
 * Reusable confirmation dialog component.
 *
 * @param {boolean}  open        – whether the dialog is visible
 * @param {string}   title       – heading text
 * @param {string}   message     – body / description text
 * @param {string}   confirmText – confirm button label (default "Confirm")
 * @param {string}   cancelText  – cancel button label  (default "Cancel")
 * @param {'danger'|'warning'} variant – colour scheme (default "danger")
 * @param {() => void} onConfirm
 * @param {() => void} onCancel
 */
export default function ConfirmDialog({
    open,
    title = 'Are you sure?',
    message = '',
    confirmText = 'Confirm',
    cancelText = 'Cancel',
    variant = 'danger',
    onConfirm,
    onCancel,
}) {
    const confirmRef = useRef(null)

    // Focus the confirm button when the dialog opens
    useEffect(() => {
        if (open && confirmRef.current) confirmRef.current.focus()
    }, [open])

    // Close on Escape
    useEffect(() => {
        if (!open) return
        const handler = (e) => { if (e.key === 'Escape') onCancel?.() }
        window.addEventListener('keydown', handler)
        return () => window.removeEventListener('keydown', handler)
    }, [open, onCancel])

    if (!open) return null

    const isDanger = variant === 'danger'

    const iconBg = isDanger ? 'bg-red-100' : 'bg-amber-100'
    const iconColor = isDanger ? 'text-red-600' : 'text-amber-600'
    const btnBg = isDanger
        ? 'bg-red-600 hover:bg-red-700 focus:ring-red-500'
        : 'bg-amber-500 hover:bg-amber-600 focus:ring-amber-400'

    return (
        <div
            className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/40 backdrop-blur-sm animate-[fadeIn_150ms_ease]"
            onClick={onCancel}
        >
            <div
                className="w-full max-w-sm mx-4 bg-white rounded-2xl shadow-2xl overflow-hidden animate-[scaleIn_200ms_ease]"
                onClick={(e) => e.stopPropagation()}
            >
                {/* Icon + Title area */}
                <div className="px-6 pt-6 pb-2 flex flex-col items-center text-center">
                    <div className={`w-14 h-14 rounded-full ${iconBg} flex items-center justify-center mb-4`}>
                        {isDanger ? (
                            /* Trash / delete icon */
                            <svg className={`w-7 h-7 ${iconColor}`} fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0" />
                            </svg>
                        ) : (
                            /* Warning / toggle icon */
                            <svg className={`w-7 h-7 ${iconColor}`} fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
                            </svg>
                        )}
                    </div>

                    <h3 className="text-lg font-bold text-gray-900">{title}</h3>
                    {message && (
                        <p className="mt-2 text-sm text-gray-500 leading-relaxed">{message}</p>
                    )}
                </div>

                {/* Action buttons */}
                <div className="px-6 pb-6 pt-4 flex gap-3">
                    <button
                        type="button"
                        className="flex-1 px-4 py-2.5 rounded-xl border-2 border-gray-200 text-gray-700 font-semibold text-sm
							hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-gray-300 transition-all active:scale-[0.97]"
                        onClick={onCancel}
                    >
                        {cancelText}
                    </button>
                    <button
                        ref={confirmRef}
                        type="button"
                        className={`flex-1 px-4 py-2.5 rounded-xl text-white font-semibold text-sm
							focus:outline-none focus:ring-2 focus:ring-offset-2 transition-all active:scale-[0.97] ${btnBg}`}
                        onClick={onConfirm}
                    >
                        {confirmText}
                    </button>
                </div>
            </div>

            {/* Keyframe animations injected inline */}
            <style>{`
				@keyframes fadeIn { from { opacity: 0 } to { opacity: 1 } }
				@keyframes scaleIn { from { opacity: 0; transform: scale(0.92) } to { opacity: 1; transform: scale(1) } }
			`}</style>
        </div>
    )
}
