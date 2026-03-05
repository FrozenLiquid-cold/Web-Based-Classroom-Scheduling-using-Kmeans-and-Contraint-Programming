import React, { useState } from 'react';

/**
 * SchedulerDiagnostics - Visual feedback for scheduler results
 * Shows solver status, scheduled counts, and failure reasons
 */
export default function SchedulerDiagnostics({ diagnostics, isVisible = true }) {
    const [isExpanded, setIsExpanded] = useState(true);

    if (!diagnostics || !isVisible) return null;

    const {
        solver_status = 'UNKNOWN',
        solve_time_seconds = 0,
        subjects_scheduled = 0,
        subjects_total = 0,
        unscheduled_reasons = {},
        error_message = null,
    } = diagnostics;

    // Determine status color and icon
    const getStatusStyle = () => {
        switch (solver_status) {
            case 'OPTIMAL':
                return { color: '#22c55e', bg: '#dcfce7', icon: '✓', label: 'OPTIMAL' };
            case 'FEASIBLE':
                return { color: '#eab308', bg: '#fef9c3', icon: '○', label: 'PARTIAL' };
            case 'INFEASIBLE':
                return { color: '#ef4444', bg: '#fee2e2', icon: '✗', label: 'NO SOLUTION' };
            case 'ERROR':
                return { color: '#ef4444', bg: '#fee2e2', icon: '⚠', label: 'ERROR' };
            default:
                return { color: '#6b7280', bg: '#f3f4f6', icon: '?', label: 'UNKNOWN' };
        }
    };

    const statusStyle = getStatusStyle();
    const unscheduledList = Object.entries(unscheduled_reasons);
    const hasUnscheduled = unscheduledList.length > 0;
    const allScheduled = subjects_scheduled === subjects_total && subjects_total > 0;

    return (
        <div style={{
            margin: '16px 0',
            border: `1px solid ${statusStyle.color}40`,
            borderRadius: '8px',
            backgroundColor: statusStyle.bg,
            overflow: 'hidden',
        }}>
            {/* Header - Always visible */}
            <button
                onClick={() => setIsExpanded(!isExpanded)}
                style={{
                    width: '100%',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '12px 16px',
                    border: 'none',
                    background: 'transparent',
                    cursor: 'pointer',
                    textAlign: 'left',
                }}
            >
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    {/* Status Badge */}
                    <span style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '6px',
                        padding: '4px 12px',
                        backgroundColor: statusStyle.color,
                        color: 'white',
                        borderRadius: '9999px',
                        fontSize: '12px',
                        fontWeight: '600',
                    }}>
                        <span>{statusStyle.icon}</span>
                        <span>{statusStyle.label}</span>
                    </span>

                    {/* Stats */}
                    <span style={{ color: '#374151', fontSize: '14px' }}>
                        <strong>{subjects_scheduled}</strong> / {subjects_total} subjects scheduled
                    </span>

                    {solve_time_seconds > 0 && (
                        <span style={{ color: '#6b7280', fontSize: '13px' }}>
                            • Solved in {solve_time_seconds.toFixed(1)}s
                        </span>
                    )}
                </div>

                {/* Expand/Collapse icon */}
                <span style={{ color: '#6b7280', fontSize: '18px' }}>
                    {isExpanded ? '▼' : '▶'}
                </span>
            </button>

            {/* Expandable Content */}
            {isExpanded && (hasUnscheduled || error_message) && (
                <div style={{
                    padding: '0 16px 16px 16px',
                    borderTop: `1px solid ${statusStyle.color}20`,
                }}>
                    {/* Error Message */}
                    {error_message && (
                        <div style={{
                            marginTop: '12px',
                            padding: '12px',
                            backgroundColor: '#fef2f2',
                            borderRadius: '6px',
                            color: '#b91c1c',
                            fontSize: '13px',
                        }}>
                            <strong>Error:</strong> {error_message}
                        </div>
                    )}

                    {/* Unscheduled Subjects */}
                    {hasUnscheduled && (
                        <div style={{ marginTop: '12px' }}>
                            <div style={{
                                fontSize: '13px',
                                fontWeight: '600',
                                color: '#374151',
                                marginBottom: '8px',
                            }}>
                                ⚠️ {unscheduledList.length} subject{unscheduledList.length > 1 ? 's' : ''} could not be scheduled:
                            </div>

                            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                                {unscheduledList.map(([subjectId, info]) => (
                                    <div
                                        key={subjectId}
                                        style={{
                                            padding: '10px 12px',
                                            backgroundColor: 'white',
                                            borderRadius: '6px',
                                            border: '1px solid #e5e7eb',
                                        }}
                                    >
                                        <div style={{
                                            fontSize: '13px',
                                            fontWeight: '600',
                                            color: '#111827',
                                        }}>
                                            {info.subject_code || `Subject ID: ${subjectId}`}
                                            {info.subject_type && (
                                                <span style={{
                                                    marginLeft: '8px',
                                                    padding: '2px 6px',
                                                    fontSize: '11px',
                                                    backgroundColor: info.subject_type === 'LAB' ? '#dbeafe' : '#f3e8ff',
                                                    color: info.subject_type === 'LAB' ? '#1d4ed8' : '#7c3aed',
                                                    borderRadius: '4px',
                                                }}>
                                                    {info.subject_type}
                                                </span>
                                            )}
                                        </div>

                                        <div style={{
                                            marginTop: '4px',
                                            fontSize: '12px',
                                            color: '#6b7280',
                                        }}>
                                            <strong>Reason:</strong> {info.reason_text || info.reason || 'Unknown'}
                                        </div>

                                        {info.suggestion && (
                                            <div style={{
                                                marginTop: '4px',
                                                fontSize: '12px',
                                                color: '#059669',
                                            }}>
                                                <strong>💡 Suggestion:</strong> {info.suggestion}
                                            </div>
                                        )}
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}

                    {/* Success message when all scheduled */}
                    {allScheduled && !hasUnscheduled && !error_message && (
                        <div style={{
                            marginTop: '12px',
                            padding: '12px',
                            backgroundColor: '#f0fdf4',
                            borderRadius: '6px',
                            color: '#166534',
                            fontSize: '13px',
                            textAlign: 'center',
                        }}>
                            ✓ All subjects successfully scheduled!
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}
