import React, { useMemo } from 'react';

function minutesToLabel(mins) {
  if (mins == null) return '';
  const h = Math.floor(mins / 60);
  const m = mins % 60;
  const h12 = h > 12 ? h - 12 : h === 0 ? 12 : h;
  const ampm = h >= 12 ? 'PM' : 'AM';
  return `${h12}:${String(m).padStart(2, '0')} ${ampm}`;
}

const DAY_MAP = { 1: 'M', 2: 'T', 3: 'W', 4: 'TH', 5: 'F', 6: 'SAT', 7: 'SUN' };

function SkeletonRow({ delay = 0 }) {
  return (
    <tr style={{ animation: `skeletonFade 1.5s ease-in-out infinite`, animationDelay: `${delay}s` }}>
      <td className="px-4 py-3"><div style={{ height: 14, width: 60, borderRadius: 4, background: '#e5e7eb' }} /></td>
      <td className="px-4 py-3"><div style={{ height: 14, width: 140, borderRadius: 4, background: '#e5e7eb' }} /></td>
      <td className="px-4 py-3"><div style={{ height: 14, width: 40, borderRadius: 4, background: '#e5e7eb' }} /></td>
      <td className="px-4 py-3"><div style={{ height: 14, width: 30, borderRadius: 4, background: '#e5e7eb' }} /></td>
      <td className="px-4 py-3"><div style={{ height: 14, width: 40, borderRadius: 4, background: '#e5e7eb' }} /></td>
      <td className="px-4 py-3"><div style={{ height: 14, width: 120, borderRadius: 4, background: '#e5e7eb' }} /></td>
      <td className="px-4 py-3"><div style={{ height: 14, width: 70, borderRadius: 4, background: '#e5e7eb' }} /></td>
      <td className="px-4 py-3"><div style={{ height: 14, width: 100, borderRadius: 4, background: '#e5e7eb' }} /></td>
    </tr>
  );
}

function ScheduledRow({ item, animDelay = 0 }) {
  const code = item.subject_code || item.code || `Subject ${item.subject_id}`;
  const desc = item.descriptive_title || item.subject_name || '';
  const type = item.subject_type || '';
  const units = item.units ?? '';

  let daysStr = '';
  if (item.day_label) {
    daysStr = item.day_label;
  } else if (item.day_id) {
    daysStr = DAY_MAP[item.day_id] || '';
  }

  const timeStr = (item.start_min != null && item.end_min != null)
    ? `${minutesToLabel(item.start_min)} - ${minutesToLabel(item.end_min)}`
    : (item.time || '—');
  const room = item.room_name || '—';
  const instructor = item.instructor_name || '—';

  return (
    <tr style={{
      animation: `rowSlideIn 0.4s ease forwards`,
      animationDelay: `${animDelay}s`,
      opacity: 0,
      borderBottom: '1px solid #f3f4f6',
    }}>
      <td className="px-4 py-3" style={{ fontWeight: 600, fontSize: 13, color: '#1f2937' }}>{code}</td>
      <td className="px-4 py-3" style={{ fontSize: 12, color: '#374151' }}>{desc}</td>
      <td className="px-4 py-3">
        {type && (
          <span style={{
            fontSize: 10, padding: '2px 6px', borderRadius: 4,
            background: '#f3f4f6', color: '#6b7280', fontWeight: 500,
          }}>{type}</span>
        )}
      </td>
      <td className="px-4 py-3" style={{ fontSize: 12, color: '#6b7280' }}>{units}</td>
      <td className="px-4 py-3" style={{ fontSize: 12, fontWeight: 500, color: '#374151' }}>{daysStr}</td>
      <td className="px-4 py-3" style={{ fontSize: 12, color: '#374151' }}>{timeStr}</td>
      <td className="px-4 py-3" style={{ fontSize: 12, color: '#374151' }}>{room}</td>
      <td className="px-4 py-3" style={{ fontSize: 12, color: '#374151' }}>{instructor}</td>
    </tr>
  );
}

function BlockSection({ label, items, skeletonCount, isComplete, uniqueCount, totalForBlock }) {
  return (
    <div style={{
      borderRadius: 8,
      overflow: 'hidden',
      border: '1px solid #e5e7eb',
      background: '#fff',
      boxShadow: '0 1px 3px rgba(0,0,0,0.08)',
    }}>
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '8px 16px',
        background: '#f9fafb',
        borderBottom: '1px solid #e5e7eb',
      }}>
        <span style={{ fontSize: 13, fontWeight: 600, color: '#374151' }}>
          Block {label}
        </span>
        <span style={{ fontSize: 11, color: '#9ca3af' }}>
          {`scheduled ${uniqueCount}/${totalForBlock}`}
        </span>
      </div>

      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr style={{ background: '#f9fafb', borderBottom: '1px solid #e5e7eb' }}>
            {['Code', 'Descriptive Title', 'Type', 'Unit', 'Days', 'Time', 'Room', 'Instructor'].map(h => (
              <th key={h} className="px-4 py-2" style={{
                textAlign: 'left', fontSize: 10, fontWeight: 600,
                color: '#9ca3af', textTransform: 'uppercase', letterSpacing: 0.5,
              }}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {items.map((item, idx) => (
            <ScheduledRow key={`${item.subject_id}-${item.day_id}-${idx}`} item={item} animDelay={idx * 0.05} />
          ))}
          {skeletonCount > 0 && !isComplete && (
            Array.from({ length: skeletonCount }).map((_, i) => (
              <SkeletonRow key={`skel-${i}`} delay={i * 0.12} />
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}

export default function ScheduleTimetable({
  partialItems = [],
  totalSubjects = 0,
  currentPhase = '',
  statusMessage = '',
  isComplete = false,
  subjectCount = 0,
  blocksCount = 1,
}) {
  const blockLabels = useMemo(() => {
    const count = Math.max(1, blocksCount);
    return Array.from({ length: count }, (_, i) => String.fromCharCode(65 + i));
  }, [blocksCount]);

  const effectiveTotal = totalSubjects > 0 ? totalSubjects : (subjectCount > 0 ? subjectCount : 8);

  // Group items by block
  const itemsByBlock = useMemo(() => {
    const map = {};
    blockLabels.forEach(l => { map[l] = []; });
    partialItems.forEach(item => {
      if (!item.day_id && !item.start_min) return;
      const b = (item.block || 'A').toString().trim().toUpperCase();
      if (map[b]) map[b].push(item);
    });
    return map;
  }, [partialItems, blockLabels]);

  // Count unique scheduled subject_ids per block (not rows, since MW = 2 rows per subject)
  const uniqueByBlock = useMemo(() => {
    const map = {};
    blockLabels.forEach(l => {
      const ids = new Set();
      (itemsByBlock[l] || []).forEach(item => {
        if (item.subject_id != null) ids.add(item.subject_id);
      });
      map[l] = ids.size;
    });
    return map;
  }, [itemsByBlock, blockLabels]);

  const totalUniqueScheduled = Object.values(uniqueByBlock).reduce((sum, n) => sum + n, 0);

  return (
    <div>
      {/* Overall progress header with status message */}
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        marginBottom: 12,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          {!isComplete && (
            <svg style={{ width: 16, height: 16, animation: 'spin 0.8s linear infinite' }} viewBox="0 0 24 24" fill="none">
              <circle cx="12" cy="12" r="10" stroke="#e5e7eb" strokeWidth="3" />
              <path d="M4 12a8 8 0 018-8" stroke="#3b82f6" strokeWidth="3" strokeLinecap="round" />
            </svg>
          )}
          <span style={{ fontSize: 13, fontWeight: 600, color: '#374151' }}>
            {statusMessage || 'Initializing...'}
          </span>
        </div>
        <span style={{ fontSize: 12, color: '#9ca3af', fontWeight: 500 }}>
          {totalUniqueScheduled} / {effectiveTotal * blocksCount} subjects
        </span>
      </div>

      {/* Progress bar */}
      <div style={{ height: 3, background: '#f3f4f6', borderRadius: 2, marginBottom: 16 }}>
        <div style={{
          height: '100%',
          width: (effectiveTotal * blocksCount) > 0 ? `${(totalUniqueScheduled / (effectiveTotal * blocksCount)) * 100}%` : '0%',
          background: 'linear-gradient(90deg, #3b82f6, #8b5cf6)',
          transition: 'width 0.6s ease',
          borderRadius: 2,
        }} />
      </div>

      {/* Stacked block sections */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
        {blockLabels.map(label => (
          <BlockSection
            key={label}
            label={label}
            items={itemsByBlock[label] || []}
            skeletonCount={Math.max(0, effectiveTotal - (uniqueByBlock[label] || 0))}
            isComplete={isComplete}
            uniqueCount={uniqueByBlock[label] || 0}
            totalForBlock={effectiveTotal}
          />
        ))}
      </div>

      <style>{`
        @keyframes spin {
          to { transform: rotate(360deg); }
        }
        @keyframes skeletonFade {
          0%, 100% { opacity: 0.4; }
          50% { opacity: 1; }
        }
        @keyframes rowSlideIn {
          from { opacity: 0; transform: translateX(-8px); }
          to { opacity: 1; transform: translateX(0); }
        }
      `}</style>
    </div>
  );
}
