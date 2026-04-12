import { useState, useEffect, useRef } from 'react';

/**
 * Compute the default school year based on the current date.
 * If month >= June (6), current year starts the SY: "2025-2026"
 * If month < June, previous year starts: "2024-2025"
 */
function computeDefaultSY() {
  const now = new Date();
  const year = now.getFullYear();
  const month = now.getMonth() + 1; // 1-indexed
  const startYear = month >= 6 ? year : year - 1;
  return `${startYear}-${startYear + 1}`;
}

/**
 * Generate SY options from 2020-2021 to currentYear+1.
 */
function generateSYOptions() {
  const now = new Date();
  const currentYear = now.getFullYear();
  const futureStart = currentYear + 1;
  const options = [];
  for (let start = futureStart; start >= 2020; start--) {
    options.push(`${start}-${start + 1}`);
  }
  return options;
}

const STORAGE_KEY = 'jrmsu.schoolYear';

export default function SchoolYearSelector({ onChange }) {
  const [schoolYear, setSchoolYear] = useState(() => {
    const saved = localStorage.getItem(STORAGE_KEY);
    return saved || computeDefaultSY();
  });
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  const options = generateSYOptions();

  // Persist and notify parent
  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, schoolYear);
    if (onChange) onChange(schoolYear);
  }, [schoolYear]);

  // Close dropdown on outside click
  useEffect(() => {
    function handleClickOutside(e) {
      if (ref.current && !ref.current.contains(e.target)) {
        setOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-2 px-4 py-2.5 bg-white/90 border border-white/60 rounded-xl shadow hover:shadow-lg transition-all duration-300 text-sm font-semibold text-slate-700"
        title="School Year"
      >
        <svg className="w-4 h-4 text-slate-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
        </svg>
        <span>SY {schoolYear}</span>
        <svg className={`w-3.5 h-3.5 text-slate-400 transition-transform duration-200 ${open ? 'rotate-180' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-1 w-44 bg-white rounded-xl shadow-xl border border-slate-200 py-1 z-50 max-h-64 overflow-y-auto"
          style={{ scrollbarWidth: 'thin' }}
        >
          {options.map(sy => (
            <button
              key={sy}
              onClick={() => { setSchoolYear(sy); setOpen(false); }}
              className={`w-full text-left px-4 py-2 text-sm transition-colors ${
                sy === schoolYear
                  ? 'bg-blue-50 text-blue-700 font-semibold'
                  : 'text-slate-600 hover:bg-slate-50'
              }`}
            >
              SY {sy}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export { computeDefaultSY };
