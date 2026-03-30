import React, { useState } from 'react';

/**
 * SchedulerDiagnostics - Visual feedback for scheduler results
 * Shows solver status, scheduled counts, failure reasons, and specific recommendations
 */
export default function SchedulerDiagnostics({ diagnostics, isVisible = true }) {
    const [isExpanded, setIsExpanded] = useState(true);
    const [expandedSubjects, setExpandedSubjects] = useState(new Set());

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

    const toggleSubjectExpanded = (subjectId) => {
        setExpandedSubjects(prev => {
            const next = new Set(prev);
            if (next.has(subjectId)) next.delete(subjectId);
            else next.add(subjectId);
            return next;
        });
    };

    // Get reason-specific icon
    const getReasonIcon = (reason) => {
        switch (reason) {
            case 'No Instructor': return '👨‍🏫';
            case 'No Rooms': return '🏢';
            case 'No Instructor & No Rooms': return '🚫';
            case 'Solver Conflict': return '⚡';
            case 'Room Conflict': return '🏢';
            case 'Instructor Conflict': return '👨‍🏫';
            case 'Student Conflict': return '👥';
            case 'All Slots Booked': return '📅';
            case 'No Valid Time': return '🕐';
            default: return '❓';
        }
    };

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
                                {unscheduledList.map(([subjectId, info]) => {
                                    const recs = info.recommendations || [];
                                    const hasRecs = recs.length > 0;
                                    const isSubjExpanded = expandedSubjects.has(subjectId);

                                    return (
                                        <div
                                            key={subjectId}
                                            style={{
                                                padding: '10px 12px',
                                                backgroundColor: 'white',
                                                borderRadius: '6px',
                                                border: '1px solid #e5e7eb',
                                            }}
                                        >
                                            {/* Subject header */}
                                            <div style={{
                                                display: 'flex',
                                                alignItems: 'center',
                                                justifyContent: 'space-between',
                                            }}>
                                                <div style={{
                                                    fontSize: '13px',
                                                    fontWeight: '600',
                                                    color: '#111827',
                                                    display: 'flex',
                                                    alignItems: 'center',
                                                    gap: '6px',
                                                }}>
                                                    <span>{getReasonIcon(info.reason)}</span>
                                                    {info.subject_code || `Subject ID: ${subjectId}`}
                                                    {info.subject_type && (
                                                        <span style={{
                                                            padding: '2px 6px',
                                                            fontSize: '11px',
                                                            backgroundColor: info.subject_type === 'LAB' ? '#dbeafe' : '#f3e8ff',
                                                            color: info.subject_type === 'LAB' ? '#1d4ed8' : '#7c3aed',
                                                            borderRadius: '4px',
                                                        }}>
                                                            {info.subject_type}
                                                        </span>
                                                    )}
                                                    {info.reason && (
                                                        <span style={{
                                                            padding: '2px 8px',
                                                            fontSize: '10px',
                                                            backgroundColor: '#fef2f2',
                                                            color: '#dc2626',
                                                            borderRadius: '9999px',
                                                            fontWeight: '500',
                                                        }}>
                                                            {info.reason}
                                                        </span>
                                                    )}
                                                </div>
                                                {hasRecs && (
                                                    <button
                                                        onClick={() => toggleSubjectExpanded(subjectId)}
                                                        style={{
                                                            background: 'none',
                                                            border: '1px solid #d1d5db',
                                                            borderRadius: '4px',
                                                            padding: '2px 8px',
                                                            fontSize: '11px',
                                                            color: '#4b5563',
                                                            cursor: 'pointer',
                                                        }}
                                                    >
                                                        {isSubjExpanded ? '▼ Hide' : `▶ ${recs.length} suggestion${recs.length > 1 ? 's' : ''}`}
                                                    </button>
                                                )}
                                            </div>

                                            {/* Reason text */}
                                            <div style={{
                                                marginTop: '4px',
                                                fontSize: '12px',
                                                color: '#6b7280',
                                            }}>
                                                <strong>Reason:</strong> {info.reason_text || info.reason || 'Unknown'}
                                            </div>

                                            {/* Static suggestion */}
                                            {info.suggestion && (
                                                <div style={{
                                                    marginTop: '4px',
                                                    fontSize: '12px',
                                                    color: '#059669',
                                                }}>
                                                    <strong>💡 Suggestion:</strong> {info.suggestion}
                                                </div>
                                            )}

                                            {/* Specific Recommendations (expandable) */}
                                            {isSubjExpanded && hasRecs && (
                                                <div style={{
                                                    marginTop: '8px',
                                                    borderTop: '1px solid #e5e7eb',
                                                    paddingTop: '8px',
                                                }}>
                                                    <div style={{
                                                        fontSize: '11px',
                                                        fontWeight: '600',
                                                        color: '#374151',
                                                        marginBottom: '6px',
                                                    }}>
                                                        📋 Available slot suggestions:
                                                    </div>
                                                    <div style={{
                                                        display: 'grid',
                                                        gap: '4px',
                                                        maxHeight: '200px',
                                                        overflowY: 'auto',
                                                    }}>
                                                        {recs.slice(0, 5).map((rec, idx) => (
                                                            <div
                                                                key={idx}
                                                                style={{
                                                                    display: 'flex',
                                                                    alignItems: 'center',
                                                                    gap: '8px',
                                                                    padding: '6px 8px',
                                                                    backgroundColor: idx === 0 ? '#f0fdf4' : '#f9fafb',
                                                                    borderRadius: '4px',
                                                                    border: idx === 0 ? '1px solid #86efac' : '1px solid #e5e7eb',
                                                                    fontSize: '12px',
                                                                }}
                                                            >
                                                                <span style={{
                                                                    width: '20px',
                                                                    height: '20px',
                                                                    borderRadius: '50%',
                                                                    backgroundColor: idx === 0 ? '#22c55e' : '#d1d5db',
                                                                    color: 'white',
                                                                    display: 'flex',
                                                                    alignItems: 'center',
                                                                    justifyContent: 'center',
                                                                    fontSize: '10px',
                                                                    fontWeight: '700',
                                                                    flexShrink: 0,
                                                                }}>
                                                                    {idx + 1}
                                                                </span>
                                                                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px', alignItems: 'center' }}>
                                                                    <span style={{
                                                                        padding: '1px 6px',
                                                                        backgroundColor: '#dbeafe',
                                                                        color: '#1d4ed8',
                                                                        borderRadius: '3px',
                                                                        fontSize: '11px',
                                                                        fontWeight: '500',
                                                                    }}>
                                                                        🏢 {rec.room_name || `Room ${rec.room_id}`}
                                                                    </span>
                                                                    <span style={{
                                                                        padding: '1px 6px',
                                                                        backgroundColor: '#fef3c7',
                                                                        color: '#92400e',
                                                                        borderRadius: '3px',
                                                                        fontSize: '11px',
                                                                        fontWeight: '500',
                                                                    }}>
                                                                        👨‍🏫 {rec.instructor_name || `Instr ${rec.instructor_id}`}
                                                                    </span>
                                                                    <span style={{
                                                                        padding: '1px 6px',
                                                                        backgroundColor: '#ede9fe',
                                                                        color: '#5b21b6',
                                                                        borderRadius: '3px',
                                                                        fontSize: '11px',
                                                                        fontWeight: '500',
                                                                    }}>
                                                                        🕐 {rec.day_label || ''} {rec.time || ''}
                                                                    </span>
                                                                    {idx === 0 && (
                                                                        <span style={{
                                                                            padding: '1px 6px',
                                                                            backgroundColor: '#dcfce7',
                                                                            color: '#166534',
                                                                            borderRadius: '3px',
                                                                            fontSize: '10px',
                                                                            fontWeight: '600',
                                                                        }}>
                                                                            ★ Best match
                                                                        </span>
                                                                    )}
                                                                </div>
                                                            </div>
                                                        ))}
                                                    </div>
                                                </div>
                                            )}
                                        </div>
                                    );
                                })}
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
