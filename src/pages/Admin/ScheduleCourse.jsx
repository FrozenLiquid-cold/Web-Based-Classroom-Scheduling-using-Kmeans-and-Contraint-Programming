import { useEffect, useState } from "react";

const BLOCK_OPTIONS = [1, 2, 3, 4];
const SEMESTERS = [1, 2];

export default function ScheduleCourse() {
  const [courses, setCourses] = useState([]);
  const [years, setYears] = useState([]);
  const [form, setForm] = useState({
    course_id: "",
    year: "",
    blocks_count: "",
    semester: "",
  });
  const [isSubmitting, setSubmitting] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    const loadOptions = async () => {
      try {
        const [coursesRes, yearsRes] = await Promise.all([
          fetch("/api/courses"),
          fetch("/api/years"),
        ]);
        if (coursesRes.ok) {
          setCourses(await coursesRes.json());
        }
        if (yearsRes.ok) {
          setYears(await yearsRes.json());
        } else {
          setYears([1, 2, 3, 4]);
        }
      } catch (err) {
        console.error("Failed to load dropdown options", err);
        setYears([1, 2, 3, 4]);
      }
    };

    loadOptions();
  }, []);

  const handleChange = (event) => {
    const { name, value } = event.target;
    setForm((prev) => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    setSubmitting(true);
    setResult(null);
    setError("");

    try {
      const response = await fetch("/api/schedule/course", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          course_id: Number(form.course_id),
          year: Number(form.year),
          semester: Number(form.semester),
          blocks_count: Number(form.blocks_count),
        }),
      });

      const json = await response.json();
      if (!response.ok) {
        setError(json.detail || json.message || "Failed to schedule course");
      } else {
        setResult(json);
      }
    } catch (err) {
      setError(err.message || "Unexpected error");
    } finally {
      setSubmitting(false);
    }
  };

  const analyzeFailure = (stats) => {
    if (!stats) return { reason: "Unknown error", recommendation: "Check logs" };

    if (stats.eligible_rooms === 0)
      return { reason: "No eligible rooms found", recommendation: "Check if rooms are assigned to this college/course." };
    if (stats.eligible_instrs === 0)
      return { reason: "No eligible instructors found", recommendation: "Assign instructors to this subject." };

    if (stats.windows_student_conflict > 0 && stats.candidates === 0)
      return { reason: "Student time conflict", recommendation: "Students are busy with other subjects in all possible slots. Try reducing block count or checking other subjects." };

    if (stats.room_conflicts > stats.room_checks * 0.8)
      return { reason: "Rooms fully booked", recommendation: "Add more rooms or extend operating hours." };

    if (stats.instr_conflicts > stats.instr_checks * 0.8)
      return { reason: "Instructors fully booked", recommendation: "Instructors are busy. Assign more instructors or free up their schedule." };

    return { reason: "Constraints too tight", recommendation: "Could not find valid slot matching all constraints (Room + Instructor + Time)." };
  };

  return (
    <div className="schedule-course-form max-w-4xl mx-auto p-6">
      <h2 className="text-2xl font-bold mb-6 text-slate-800">Schedule Generator</h2>

      <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-200 mb-8">
        <form onSubmit={handleSubmit} className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <label className="block">
            <span className="text-sm font-bold text-slate-700 mb-1 block">Course</span>
            <select
              name="course_id"
              value={form.course_id}
              onChange={handleChange}
              required
              className="w-full rounded-lg border-slate-300 focus:border-indigo-500 focus:ring-indigo-500"
            >
              <option value="">Choose a course</option>
              {courses.map((course) => (
                <option key={course.id} value={course.id}>
                  {course.code || course.name || `Course ${course.id}`}
                </option>
              ))}
            </select>
          </label>

          <label className="block">
            <span className="text-sm font-bold text-slate-700 mb-1 block">Year Level</span>
            <select
              name="year"
              value={form.year}
              onChange={handleChange}
              required
              className="w-full rounded-lg border-slate-300 focus:border-indigo-500 focus:ring-indigo-500"
            >
              <option value="">Choose year</option>
              {years.map((yearValue) => (
                <option key={yearValue} value={yearValue}>
                  Year {yearValue}
                </option>
              ))}
            </select>
          </label>

          <label className="block">
            <span className="text-sm font-bold text-slate-700 mb-1 block">Number of Blocks</span>
            <select
              name="blocks_count"
              value={form.blocks_count}
              onChange={handleChange}
              required
              className="w-full rounded-lg border-slate-300 focus:border-indigo-500 focus:ring-indigo-500"
            >
              <option value="">Choose blocks</option>
              {BLOCK_OPTIONS.map((count) => (
                <option key={count} value={count}>
                  {count} block{count > 1 ? "s" : ""}
                </option>
              ))}
            </select>
          </label>

          <label className="block">
            <span className="text-sm font-bold text-slate-700 mb-1 block">Semester</span>
            <select
              name="semester"
              value={form.semester}
              onChange={handleChange}
              required
              className="w-full rounded-lg border-slate-300 focus:border-indigo-500 focus:ring-indigo-500"
            >
              <option value="">Choose semester</option>
              {SEMESTERS.map((sem) => (
                <option key={sem} value={sem}>
                  Semester {sem}
                </option>
              ))}
            </select>
          </label>

          <div className="md:col-span-2 mt-2">
            <button
              type="submit"
              disabled={isSubmitting}
              className="w-full py-3 bg-indigo-600 hover:bg-indigo-700 text-white font-bold rounded-xl transition-all shadow-md shadow-indigo-200 disabled:opacity-70 disabled:cursor-not-allowed flex justify-center items-center"
            >
              {isSubmitting ? (
                <>
                  <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  Running Genetic Algorithm...
                </>
              ) : "Run Scheduler"}
            </button>
          </div>
        </form>
      </div>

      {error && (
        <div className="p-4 bg-rose-50 border border-rose-200 rounded-xl text-rose-700 mb-6 flex items-start gap-3">
          <span className="text-xl">⚠️</span>
          <div>
            <h3 className="font-bold">Error</h3>
            <p className="text-sm">{error}</p>
          </div>
        </div>
      )}

      {result && (
        <div className="space-y-8 animate-fade-in">

          {/* Summary Stats */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm text-center">
              <div className="text-2xl font-bold text-slate-800">{result.count}</div>
              <div className="text-xs font-bold text-slate-500 uppercase">Total Items</div>
            </div>
            <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm text-center">
              <div className="text-2xl font-bold text-emerald-600">
                {(result.scheduled || []).filter(i => i.day_id).length}
              </div>
              <div className="text-xs font-bold text-slate-500 uppercase">Scheduled</div>
            </div>
            <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm text-center">
              <div className="text-2xl font-bold text-rose-600">
                {(result.scheduled || []).filter(i => !i.day_id).length}
              </div>
              <div className="text-xs font-bold text-slate-500 uppercase">Unscheduled</div>
            </div>
            <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm text-center">
              <div className="text-2xl font-bold text-blue-600">{result.elapsed_time}s</div>
              <div className="text-xs font-bold text-slate-500 uppercase">Time Taken</div>
            </div>
          </div>

          {/* Unscheduled Issues */}
          {(result.scheduled || []).some(item => !item.day_id) && (
            <div className="bg-rose-50 border border-rose-100 rounded-2xl overflow-hidden shadow-sm">
              <div className="bg-rose-100/50 p-4 border-b border-rose-100">
                <h3 className="text-rose-800 font-bold flex items-center gap-2">
                  🚫 Unscheduled Subjects Analysis
                </h3>
              </div>
              <div className="divide-y divide-rose-100">
                {(result.scheduled || []).filter(item => !item.day_id).map((item, idx) => {
                  const analysis = analyzeFailure(result.diagnostics ? result.diagnostics[item.subject_id] : null);
                  return (
                    <div key={idx} className="p-4 hover:bg-white/50 transition-colors">
                      <div className="flex flex-col md:flex-row md:items-start justify-between gap-4">
                        <div>
                          <div className="font-bold text-slate-800 text-lg">Subject ID: {item.subject_id}</div>
                          <div className="text-sm text-slate-500 mb-2">Block {item.block}</div>
                          <div className="flex items-center gap-2 text-rose-700 font-medium bg-white/60 px-2 py-1 rounded-md inline-flex border border-rose-100">
                            <span>Why:</span>
                            {analysis.reason}
                          </div>
                        </div>
                        <div className="bg-white p-3 rounded-xl border border-rose-100 shadow-sm md:w-1/3">
                          <p className="text-xs font-bold text-slate-400 uppercase mb-1">Recommendation</p>
                          <p className="text-sm text-slate-700 leading-snug">{analysis.recommendation}</p>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Scheduled Results */}
          <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
            <div className="bg-slate-50 p-4 border-b border-slate-200">
              <h3 className="font-bold text-slate-700">Scheduled Classes</h3>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm text-left">
                <thead className="text-xs text-slate-500 uppercase bg-slate-50 border-b border-slate-200">
                  <tr>
                    <th className="px-6 py-3">Block</th>
                    <th className="px-6 py-3">Room</th>
                    <th className="px-6 py-3">Day</th>
                    <th className="px-6 py-3">Time</th>
                    <th className="px-6 py-3">Instructor</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {(result.scheduled || []).filter(i => i.day_id).map((slot, idx) => (
                    <tr key={idx} className="hover:bg-slate-50 transition-colors">
                      <td className="px-6 py-4 font-bold text-indigo-600">{slot.block}</td>
                      <td className="px-6 py-4 font-mono text-slate-600">Room {slot.room_id}</td>
                      <td className="px-6 py-4">
                        <span className="px-2 py-1 bg-slate-100 rounded-md font-bold text-slate-600 text-xs">
                          Day {slot.day_id}
                        </span>
                      </td>
                      <td className="px-6 py-4 font-medium text-slate-800">
                        {slot.time || `${slot.start_min}-${slot.end_min}`}
                      </td>
                      <td className="px-6 py-4 text-slate-500">
                        {slot.instructor_id ? `Instr ${slot.instructor_id}` : 'TBA'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {(result.scheduled || []).filter(i => i.day_id).length === 0 && (
                <div className="p-8 text-center text-slate-400 italic">
                  No classes scheduled.
                </div>
              )}
            </div>
          </div>

        </div>
      )}
    </div>
  );
}
