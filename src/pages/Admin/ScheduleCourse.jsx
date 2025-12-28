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
          // Fallback: typical year levels 1-4
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
      const response = await fetch("/api/schedule_course", {
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

  return (
    <div className="schedule-course-form">
      <form onSubmit={handleSubmit} className="form-grid">
        <label>
          Select Course
          <select
            name="course_id"
            value={form.course_id}
            onChange={handleChange}
            required
          >
            <option value="">Choose a course</option>
            {courses.map((course) => (
              <option key={course.id} value={course.id}>
                {course.code || course.name || `Course ${course.id}`}
              </option>
            ))}
          </select>
        </label>

        <label>
          Select Year
          <select
            name="year"
            value={form.year}
            onChange={handleChange}
            required
          >
            <option value="">Choose year level</option>
            {years.map((yearValue) => (
              <option key={yearValue} value={yearValue}>
                Year {yearValue}
              </option>
            ))}
          </select>
        </label>

        <label>
          Number of Blocks
          <select
            name="blocks_count"
            value={form.blocks_count}
            onChange={handleChange}
            required
          >
            <option value="">Choose blocks</option>
            {BLOCK_OPTIONS.map((count) => (
              <option key={count} value={count}>
                {count} block{count > 1 ? "s" : ""}
              </option>
            ))}
          </select>
        </label>

        <label>
          Semester
          <select
            name="semester"
            value={form.semester}
            onChange={handleChange}
            required
          >
            <option value="">Choose semester</option>
            {SEMESTERS.map((sem) => (
              <option key={sem} value={sem}>
                Semester {sem}
              </option>
            ))}
          </select>
        </label>

        <button type="submit" disabled={isSubmitting}>
          {isSubmitting ? "Scheduling..." : "Run Scheduler"}
        </button>
      </form>

      {error && <p className="error">{error}</p>}

      {result && (
        <div className="schedule-results">
          <h3>Status: {result.status}</h3>
          <ul>
            {(result.scheduled || []).map((slot, idx) => (
              <li key={idx}>
                Room {slot.room_id} — Timeslot {slot.timeslot_id} (day {slot.day}) —{" "}
                {slot.start_time || `${slot.start_min}-${slot.end_min}`}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

