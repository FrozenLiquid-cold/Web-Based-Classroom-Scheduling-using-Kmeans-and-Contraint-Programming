import { useEffect, useMemo, useState } from "react";
import { list } from "../../store/db";
import {
  generateSchedule as generateScheduleApi,
  getScheduleStatus,
  loadSchedule as loadScheduleApi,
  saveSchedule,
} from "../../services/api";

const YEARS = [1, 2, 3, 4];
const BLOCK_OPTIONS = [1, 2, 3, 4];
const SEMESTERS = [1, 2];

export default function RegistrarSchedule() {
  const [courses, setCourses] = useState([]);
  const [instructors, setInstructors] = useState([]);
  const [days, setDays] = useState([]);
  const [subjects, setSubjects] = useState([]);
  const [rooms, setRooms] = useState([]);
  const [form, setForm] = useState({
    course_id: "",
    year: "",
    blocks_count: "",
    semester: "",
  });
  const [isSubmitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [schedule, setSchedule] = useState([]);
  const [jobId, setJobId] = useState(null);
  const [jobStatus, setJobStatus] = useState("");
  const [statusMessage, setStatusMessage] = useState("");
  const [progress, setProgress] = useState(0);
  const [isSaving, setIsSaving] = useState(false);
  const [saveMessage, setSaveMessage] = useState("");
  const [isLoadingSavedSchedule, setIsLoadingSavedSchedule] = useState(false);
  const [savedScheduleMessage, setSavedScheduleMessage] = useState("");
  const [hasCheckedSavedSchedule, setHasCheckedSavedSchedule] = useState(false);

  // Animation states for progressive subject reveal
  const [revealedCount, setRevealedCount] = useState(0);
  const [isRevealing, setIsRevealing] = useState(false);

  useEffect(() => {
    async function loadData() {
      try {
        const [courseList, instructorList, dayList, subjectList, roomList] = await Promise.all([
          list("course"),
          list("instructor"),
          list("day"),
          list("subject"),
          list("room"),
        ]);
        setCourses(courseList || []);
        setInstructors(instructorList || []);
        setDays(dayList || []);
        setSubjects(subjectList || []);
        setRooms(roomList || []);
      } catch (err) {
        console.error("Failed to load data", err);
      }
    }
    loadData();
  }, []);

  const courseOptions = useMemo(
    () =>
      courses.map((course) => (
        <option key={course.id} value={course.id}>
          {course.code || course.name || `Course ${course.id}`}
        </option>
      )),
    [courses]
  );

  const handleChange = (event) => {
    const { name, value } = event.target;
    setForm((prev) => ({ ...prev, [name]: value }));
  };

  useEffect(() => {
    const courseId = Number(form.course_id);
    const year = Number(form.year);
    const semester = Number(form.semester);

    if (!courseId || !year || !semester) {
      setSavedScheduleMessage("");
      setHasCheckedSavedSchedule(false);
      return;
    }

    if (isSubmitting || jobId) {
      return;
    }

    let cancelled = false;
    setIsLoadingSavedSchedule(true);
    setSavedScheduleMessage("");
    setHasCheckedSavedSchedule(false);

    async function loadSavedSchedule() {
      try {
        const resp = await loadScheduleApi(courseId, semester, year);
        if (cancelled) return;

        if (resp && resp.status === "success") {
          const items = Array.isArray(resp.items) ? resp.items : [];
          setSchedule(items);
          setHasCheckedSavedSchedule(true);
          if (items.length > 0) {
            setSavedScheduleMessage(`Loaded saved schedule (${items.length} entries).`);
          } else {
            setSavedScheduleMessage("No saved schedule found for the selected course, year, and semester.");
          }
          return;
        }

        if (resp && resp.status === "pending") {
          setSchedule([]);
          setHasCheckedSavedSchedule(true);
          setSavedScheduleMessage("Schedule generation is in progress for this selection.");
          return;
        }

        setSchedule([]);
        setHasCheckedSavedSchedule(true);
        setSavedScheduleMessage("No saved schedule found for the selected course, year, and semester.");
      } catch (err) {
        if (cancelled) return;
        setSchedule([]);
        setHasCheckedSavedSchedule(true);
        setSavedScheduleMessage("");
        setError(err.message || "Failed to load saved schedule");
      } finally {
        if (!cancelled) {
          setIsLoadingSavedSchedule(false);
        }
      }
    }

    loadSavedSchedule();
    return () => {
      cancelled = true;
    };
  }, [form.course_id, form.year, form.semester]);

  const handleSubmit = async (event) => {
    event.preventDefault();
    setSubmitting(true);
    setError("");
    setSchedule([]);
    setJobStatus("initializing");
    setStatusMessage("Initializing scheduler...");
    setProgress(10);
    setJobId(null);

    try {
      const courseId = Number(form.course_id);
      const year = Number(form.year);
      const semester = Number(form.semester);
      const blocksCount = Number(form.blocks_count) || 1;

      const result = await generateScheduleApi(
        courseId,
        year,
        semester,
        null,
        { waitSeconds: 1, blocks_count: blocksCount }
      );

      if (result.status === "success") {
        // Use result.items or result.result (array) - NOT subjects
        const scheduledItems = result.items || result.result || [];
        setSchedule(scheduledItems);
        setJobStatus("succeeded");
        setJobId(null);
        setSubmitting(false);
        return;
      }

      if (result.status === "queued") {
        setJobStatus("queued");
        setJobId(result.job_id);
        return;
      }

      if (result.status === "error") {
        throw new Error(result.detail || "Scheduling failed.");
      }

      throw new Error("Unexpected scheduler response. Please try again.");
    } catch (err) {
      setError(err.message || "Unexpected error");
      setJobStatus("failed");
      setSubmitting(false);
    }
  };

  useEffect(() => {
    if (!jobId) {
      return undefined;
    }

    let cancelled = false;
    let pollTimer;

    const pollStatus = async () => {
      try {
        const status = await getScheduleStatus(jobId);
        if (cancelled) {
          return;
        }

        if (status.status === "succeeded" || status.status === "completed") {
          // Use status.result directly (array of scheduled items) - NOT subjects
          // Backend returns: {"status": "completed", "result": [scheduled_items...]}
          const scheduledItems = Array.isArray(status.result)
            ? status.result
            : (status.result?.items || []);
          setSchedule(scheduledItems);
          setJobStatus("succeeded");
          setProgress(100);
          setJobId(null);
          setSubmitting(false);
          return;
        }

        if (status.status === "failed") {
          setError(status.error || "Scheduling job failed.");
          setJobStatus("failed");
          setProgress(0);
          setJobId(null);
          setSubmitting(false);
          return;
        }

        if (status.status === "not_found") {
          setError("Scheduling job not found.");
          setJobStatus("not_found");
          setProgress(0);
          setJobId(null);
          setSubmitting(false);
          return;
        }

        setJobStatus(status.status);
        // Update detailed status message from backend
        if (status.status_message) {
          setStatusMessage(status.status_message);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err.message || "Failed to poll scheduler status.");
          setJobStatus("failed");
          setProgress(0);
          setJobId(null);
          setSubmitting(false);
        }
      }
    };

    pollStatus();
    pollTimer = setInterval(pollStatus, 2000);

    return () => {
      cancelled = true;
      if (pollTimer) {
        clearInterval(pollTimer);
      }
    };
  }, [jobId]);

  useEffect(() => {
    const active = ["initializing", "queued", "running"];
    if (!isSubmitting || !active.includes(jobStatus)) {
      return;
    }

    // Kick the bar off a little above 0 so users see it move immediately
    setProgress((prev) => (prev <= 0 ? 5 : prev));

    // Advance steadily up to 99% while the job is active
    const interval = setInterval(() => {
      setProgress((prev) => {
        if (prev >= 99) return prev;
        return prev + 1; // smooth incremental advance
      });
    }, 400);

    return () => clearInterval(interval);
  }, [jobStatus, isSubmitting]);

  useEffect(() => {
    if (jobStatus === "succeeded" || jobStatus === "completed") {
      setProgress(100);
    } else if (
      jobStatus === "failed" ||
      jobStatus === "not_found" ||
      (!isSubmitting && !jobStatus)
    ) {
      setProgress(0);
    }
  }, [jobStatus, isSubmitting]);

  // Progressive reveal animation - subjects appear one by one
  useEffect(() => {
    if (schedule.length === 0) {
      setRevealedCount(0);
      setIsRevealing(false);
      return;
    }

    // Start revealing animation when new schedule arrives
    if (jobStatus === "succeeded" || jobStatus === "completed") {
      setIsRevealing(true);
      setRevealedCount(0);

      // Reveal subjects one by one with staggered timing
      const totalItems = schedule.length;
      const intervalTime = Math.max(30, Math.min(80, 2000 / totalItems)); // 30-80ms per item
      let currentCount = 0;

      const revealInterval = setInterval(() => {
        currentCount += 1;
        setRevealedCount(currentCount);
        if (currentCount >= totalItems) {
          clearInterval(revealInterval);
          setIsRevealing(false);
        }
      }, intervalTime);

      return () => clearInterval(revealInterval);
    }
  }, [schedule.length, jobStatus]);

  const handleSave = async () => {
    if (schedule.length === 0) {
      setSaveMessage("No schedule to save");
      return;
    }

    setIsSaving(true);
    setSaveMessage("");
    setError("");

    try {
      const courseId = Number(form.course_id);
      const semester = Number(form.semester);

      // Group schedule items by year
      const itemsByYear = {};
      schedule.forEach((item) => {
        const year = item.year || form.year || 1;
        if (!itemsByYear[year]) {
          itemsByYear[year] = [];
        }
        itemsByYear[year].push({
          subject_id: item.subject_id,
          instructor_id: item.instructor_id || null,
          room_id: item.room_id || null,
          day_id: item.day_id || null,
          time: item.time || null,
          block: item.block || null,
        });
      });

      // Save each year separately
      const savePromises = Object.keys(itemsByYear).map((year) => {
        const yearNum = Number(year);
        return saveSchedule(courseId, yearNum, semester, itemsByYear[year]);
      });

      await Promise.all(savePromises);
      setSaveMessage("Schedule saved successfully!");

      // Clear message after 3 seconds
      setTimeout(() => setSaveMessage(""), 3000);
    } catch (err) {
      setError(err.message || "Failed to save schedule");
      setSaveMessage("");
    } finally {
      setIsSaving(false);
    }
  };

  // Helper functions to convert IDs to readable names
  const getSubject = (id) => {
    if (!id) return null;
    return subjects.find((s) => s.id === id) || null;
  };

  const getSubjectCode = (id) => {
    const subject = getSubject(id);
    return subject?.code || `ID: ${id}`;
  };

  const getSubjectDescription = (id) => {
    const subject = getSubject(id);
    return subject?.description || "—";
  };

  const getSubjectType = (id) => {
    const subject = getSubject(id);
    return subject?.type || "—";
  };

  const getSubjectUnit = (id) => {
    const subject = getSubject(id);
    return subject?.unit ?? "—";
  };

  const getRoomName = (id) => {
    if (!id) return "—";
    const room = rooms.find((r) => r.id === id);
    return room?.name || `ID: ${id}`;
  };

  const getInstructorName = (id) => {
    if (!id) return "—";
    const instructor = instructors.find((i) => i.id === id);
    if (!instructor) return `ID: ${id}`;
    const firstName = instructor.first_name || instructor.firstName || "";
    const lastName = instructor.last_name || instructor.lastName || "";
    const name = `${firstName} ${lastName}`.trim();
    return name || `ID: ${id}`;
  };

  const getDayName = (id) => {
    if (!id) return "—";
    const day = days.find((d) => d.id === id);
    return day?.label || `ID: ${id}`;
  };

  // Convert time to 12-hour format
  const normalizeTimeRangeString = (value) => {
    if (typeof value !== "string") {
      return value;
    }
    return value.replace(/[–—−]/g, "-");
  };

  const formatTime12Hour = (timeStrRaw) => {
    if (!timeStrRaw) return "—";
    const timeStr = normalizeTimeRangeString(timeStrRaw);

    // Handle format like "450-570" (minutes from midnight)
    if (timeStr.includes("-") && /^\d+-\d+$/.test(timeStr)) {
      const [startMin, endMin] = timeStr.split("-").map(Number);
      const startHour = Math.floor(startMin / 60);
      const startMinute = startMin % 60;
      const endHour = Math.floor(endMin / 60);
      const endMinute = endMin % 60;

      const start12 = formatTo12Hour(startHour, startMinute);
      const end12 = formatTo12Hour(endHour, endMinute);
      return `${start12} - ${end12}`;
    }

    // Handle format like "7:30-9:00" or "07:30-09:00" (24-hour format)
    if (timeStr.includes("-") && timeStr.includes(":")) {
      const [start, end] = timeStr.split("-");
      const start12 = convert24To12(start.trim());
      const end12 = convert24To12(end.trim());
      return `${start12} - ${end12}`;
    }

    // Handle single time like "7:30" or "07:30"
    if (timeStr.includes(":")) {
      return convert24To12(timeStr.trim());
    }

    // If it's already in a readable format, return as is
    return timeStr;
  };

  const formatTo12Hour = (hour24, minute) => {
    const period = hour24 >= 12 ? "PM" : "AM";
    let hour12 = hour24 % 12;
    if (hour12 === 0) hour12 = 12;
    const minuteStr = minute.toString().padStart(2, "0");
    return `${hour12}:${minuteStr} ${period}`;
  };

  const convert24To12 = (time24) => {
    if (!time24) return "—";
    const match = time24.match(/^(\d{1,2}):(\d{2})/);
    if (!match) return time24;

    const hour24 = parseInt(match[1], 10);
    const minute = parseInt(match[2], 10);
    return formatTo12Hour(hour24, minute);
  };

  // Helper function to get block label (A, B, C, etc.)
  const getBlockLabel = (blockNumber) => {
    if (blockNumber <= 0) return "";
    // Convert 1 -> A, 2 -> B, 3 -> C, etc.
    return String.fromCharCode(64 + blockNumber); // 65 is 'A' in ASCII
  };

  // Filter schedule by selected semester and year
  const filteredSchedule = useMemo(() => {
    if (!schedule || schedule.length === 0) return [];
    const selectedSemester = Number(form.semester);
    const selectedYear = Number(form.year);

    return schedule.filter(item => {
      const itemSemester = Number(item.semester);
      const itemYear = Number(item.year);
      return itemSemester === selectedSemester && itemYear === selectedYear;
    });
  }, [schedule, form.semester, form.year]);

  const expandedSchedule = useMemo(() => {
    const blocksCount = Number(form.blocks_count) || 1;

    // If there is no schedule, don't render any blocks
    if (!filteredSchedule || filteredSchedule.length === 0) {
      return {};
    }

    // Group multi-day classes so they appear once with combined day labels (e.g., MW, TTH)
    const dayLabelById = {};
    days.forEach((d) => {
      if (d && d.id != null) {
        dayLabelById[d.id] = d.label;
      }
    });

    const dayOrder = { M: 0, T: 1, W: 2, TH: 3, F: 4, S: 5 };

    const grouped = {};
    filteredSchedule.forEach((item) => {
      const subjectKey = item.subject_id || item.subjectId || "";
      const instructorKey = item.instructor_id || item.instructorId || "";
      const roomKey = item.room_id || item.roomId || "";
      const rawTimeKey = item.time || item.time_label || item.start_time || "";
      const timeKey = typeof rawTimeKey === "string"
        ? rawTimeKey.replace(/^(M|T|W|TH|F)\s+/, "")
        : rawTimeKey;

      const blockKey = item.block || item._blockLabel || "";
      const groupKey = `${subjectKey}|${instructorKey}|${roomKey}|${timeKey}|${blockKey}`;

      if (!grouped[groupKey]) {
        grouped[groupKey] = {
          ...item,
          _dayIds: [],
        };
      }

      const dayId = item.day_id || item.dayId;
      if (dayId != null && !grouped[groupKey]._dayIds.includes(dayId)) {
        grouped[groupKey]._dayIds.push(dayId);
      }
    });

    const baseRows = Object.values(grouped).map((group) => {
      const dayIds = group._dayIds || [];
      const labels = dayIds
        .map((id) => dayLabelById[id])
        .filter(Boolean)
        .sort((a, b) => {
          const aIdx = dayOrder[a] ?? 99;
          const bIdx = dayOrder[b] ?? 99;
          return aIdx - bIdx;
        });

      let combinedDays = "";
      if (labels.length === 2) {
        const [d1, d2] = labels;
        if ((d1 === "M" && d2 === "W") || (d1 === "W" && d2 === "M")) {
          combinedDays = "M-W";
        } else if (
          (d1 === "T" && d2 === "TH") ||
          (d1 === "TH" && d2 === "T")
        ) {
          combinedDays = "T-TH";
        } else {
          combinedDays = labels.join("-");
        }
      } else {
        combinedDays = labels.join("-");
      }

      const { _dayIds, ...rest } = group;

      return {
        ...rest,
        day_id: dayIds[0] ?? group.day_id ?? group.dayId ?? null,
        _combinedDaysLabel: combinedDays || (labels[0] || "—"),
      };
    });

    const byBlock = {};

    baseRows.forEach((item) => {
      const rawBlock = item.block || item._blockLabel || null;
      let blockLetter = "";
      if (typeof rawBlock === "string" && rawBlock.trim().length > 0) {
        blockLetter = rawBlock.trim();
      } else if (blocksCount === 1) {
        // Single-block schedules default to A for display when no explicit block is set
        blockLetter = getBlockLabel(1);
      }

      const displayLabel =
        blockLetter && blockLetter.length > 0
          ? `Block ${blockLetter}`
          : "Block A";

      let blockNumber = 1;
      if (blockLetter && blockLetter.length === 1) {
        const code = blockLetter.toUpperCase().charCodeAt(0) - 64;
        if (code > 0) blockNumber = code;
      }

      if (!byBlock[displayLabel]) {
        byBlock[displayLabel] = [];
      }

      byBlock[displayLabel].push({
        ...item,
        _blockNumber: blockNumber,
        _blockLabel: displayLabel,
      });
    });

    return byBlock;
  }, [filteredSchedule, form.blocks_count, days]);

  const plannedSubjectCount = useMemo(() => {
    const courseId = Number(form.course_id);
    const selectedYear = Number(form.year);
    const selectedSemester = Number(form.semester);

    if (!courseId || !selectedYear || !selectedSemester) {
      return 0;
    }

    const matches = (subjects || []).filter((s) => {
      const subjCourse = Number(s.course_id);
      const subjYear = Number(s.year_level);
      const subjSem = Number(s.semester);
      return subjCourse === courseId && subjYear === selectedYear && subjSem === selectedSemester;
    });

    if (matches.length > 0) {
      return matches.length;
    }

    const ids = new Set(
      (filteredSchedule || [])
        .map((item) => item.subject_id || item.subjectId)
        .filter(Boolean)
    );
    return ids.size;
  }, [subjects, filteredSchedule, form.course_id, form.year, form.semester]);

  // Format time from start_min and end_min to show start-to-end range
  const formatTimeRange = (slot) => {
    // Priority 1: Use start_min and end_min if available
    if (slot.start_min != null && slot.end_min != null) {
      const startHour = Math.floor(slot.start_min / 60);
      const startMinute = slot.start_min % 60;
      const endHour = Math.floor(slot.end_min / 60);
      const endMinute = slot.end_min % 60;

      const start12 = formatTo12Hour(startHour, startMinute);
      const end12 = formatTo12Hour(endHour, endMinute);
      return `${start12} - ${end12}`;
    }

    // Priority 2: Use time string if it contains a range
    const timeStrRaw = slot.time || slot.time_label || slot.start_time;
    const timeStr = normalizeTimeRangeString(timeStrRaw);
    if (timeStr) {
      return formatTime12Hour(timeStr);
    }

    return "—";
  };

  const renderScheduleRow = (slot, idx) => {
    const subjectId = slot.subject_id || slot.subjectId;
    const subjectCode = getSubjectCode(subjectId);
    const subjectDescription = getSubjectDescription(subjectId);
    const subjectType = getSubjectType(subjectId);
    const subjectUnit = getSubjectUnit(subjectId);

    const dayId = slot.day_id || slot.dayId;
    const dayLabel = slot._combinedDaysLabel || getDayName(dayId);

    // Format time as start-to-end range
    const timeLabel = formatTimeRange(slot);

    const roomId = slot.room_id || slot.roomId;
    const roomLabel = getRoomName(roomId);

    const instructorId = slot.instructor_id || slot.instructorId;
    const instructorLabel = getInstructorName(instructorId);

    // Get block label (Block A, Block B, etc.)
    const blockLabel = slot._blockLabel || "";

    // Create unique key that includes block number if applicable
    const blockNum = slot._blockNumber || 1;
    const uniqueKey = `${slot.subject_id || slot.room_id || idx}-${idx}-${blockNum}`;

    // Animation: determine if this row should be visible yet
    const isVisible = !isRevealing || idx < revealedCount;
    const animationDelay = isRevealing ? `${idx * 30}ms` : '0ms';

    return (
      <tr
        key={uniqueKey}
        className={`transition-all duration-300 ease-out ${isVisible
          ? 'opacity-100 translate-y-0'
          : 'opacity-0 translate-y-2'
          }`}
        style={{
          transitionDelay: animationDelay,
          transform: isVisible ? 'translateY(0)' : 'translateY(8px)'
        }}
      >
        <td className="px-4 py-2 text-sm text-gray-700">{subjectCode}</td>
        <td className="px-4 py-2 text-sm text-gray-700">{subjectDescription}</td>
        <td className="px-4 py-2 text-sm text-gray-700">{subjectType}</td>
        <td className="px-4 py-2 text-sm text-gray-700">{subjectUnit}</td>
        <td className="px-4 py-2 text-sm text-gray-700">{dayLabel}</td>
        <td className="px-4 py-2 text-sm text-gray-700">{timeLabel}</td>
        <td className="px-4 py-2 text-sm text-gray-700">{roomLabel}</td>
        <td className="px-4 py-2 text-sm text-gray-700">{instructorLabel}</td>
      </tr>
    );
  };

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <h1 className="text-2xl font-semibold mb-6">Registrar Scheduling</h1>

      <form onSubmit={handleSubmit} className="grid gap-4 sm:grid-cols-2">
        <label className="flex flex-col gap-1 text-sm">
          Select Course
          <select
            name="course_id"
            value={form.course_id}
            onChange={handleChange}
            className="px-3 py-2 border rounded"
            required
          >
            <option value="">Choose a course</option>
            {courseOptions}
          </select>
        </label>

        <label className="flex flex-col gap-1 text-sm">
          Select Year
          <select
            name="year"
            value={form.year}
            onChange={handleChange}
            className="px-3 py-2 border rounded"
            required
          >
            <option value="">Choose year level</option>
            {YEARS.map((yearValue) => (
              <option key={yearValue} value={yearValue}>
                Year {yearValue}
              </option>
            ))}
          </select>
        </label>

        <label className="flex flex-col gap-1 text-sm">
          Number of Blocks
          <select
            name="blocks_count"
            value={form.blocks_count}
            onChange={handleChange}
            className="px-3 py-2 border rounded"
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

        <label className="flex flex-col gap-1 text-sm">
          Semester
          <select
            name="semester"
            value={form.semester}
            onChange={handleChange}
            className="px-3 py-2 border rounded"
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

        <div className="sm:col-span-2 flex justify-end">
          <button
            type="submit"
            disabled={isSubmitting}
            className={`px-4 py-2 text-white rounded ${isSubmitting ? "bg-gray-400 cursor-not-allowed" : "bg-blue-600 hover:bg-blue-700"
              }`}
          >
            {isSubmitting ? "Scheduling..." : "Generate Schedule"}
          </button>
        </div>
      </form>

      {/* Enhanced Progress Bar with Skeleton Timetable */}
      {(isSubmitting ||
        ["initializing", "queued", "running"].includes(jobStatus)) && (
          <div className="mt-6">
            {/* Modern gradient progress bar with shimmer effect */}
            <div className="relative mb-6">
              <div className="flex justify-between items-center mb-2">
                <div className="flex items-center gap-2">
                  <div className="w-2 h-2 bg-blue-500 rounded-full animate-pulse" />
                  <span className="text-sm font-medium text-gray-700">
                    {statusMessage || (
                      jobStatus === "running" ? "Scheduling subjects..." :
                        jobStatus === "queued" ? "Preparing scheduler..." :
                          "Initializing..."
                    )}
                  </span>
                </div>
                <span className="text-sm font-semibold text-blue-600">
                  {Math.round(progress)}%
                </span>
              </div>
              <div className="w-full h-3 bg-gray-200 rounded-full overflow-hidden shadow-inner">
                <div
                  className="h-full rounded-full transition-all duration-300 ease-out relative"
                  style={{
                    width: `${Math.min(Math.max(progress, 0), 100)}%`,
                    background: 'linear-gradient(90deg, #3b82f6 0%, #8b5cf6 50%, #3b82f6 100%)',
                    backgroundSize: '200% 100%',
                    animation: 'shimmer 1.5s infinite linear'
                  }}
                >
                  <div
                    className="absolute inset-0 rounded-full"
                    style={{
                      background: 'linear-gradient(90deg, transparent 0%, rgba(255,255,255,0.4) 50%, transparent 100%)',
                      animation: 'shimmer-glow 1.5s infinite linear'
                    }}
                  />
                </div>
              </div>
            </div>

            {/* Skeleton timetable preview with blur effect */}
            <div className="relative rounded-lg overflow-hidden border border-gray-200 shadow-sm">
              <div
                className="absolute inset-0 backdrop-blur-sm bg-white/60 z-10 flex items-center justify-center"
                style={{ backdropFilter: 'blur(4px)' }}
              >
                <div className="text-center">
                  <div className="inline-flex items-center gap-2 px-4 py-2 bg-white/90 rounded-full shadow-lg">
                    <svg className="w-5 h-5 text-blue-500 animate-spin" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                    </svg>
                    <span className="text-sm font-medium text-gray-700">Generating timetable...</span>
                  </div>
                </div>
              </div>

              {/* Skeleton table structure */}
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    {["Code", "Description", "Type", "Unit", "Days", "Time", "Room", "Instructor"].map((header) => (
                      <th key={header} className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                        {header}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-100">
                  {[...Array(6)].map((_, idx) => (
                    <tr key={idx} className="animate-pulse">
                      <td className="px-4 py-3"><div className="h-4 bg-gray-200 rounded w-16" /></td>
                      <td className="px-4 py-3"><div className="h-4 bg-gray-200 rounded w-32" /></td>
                      <td className="px-4 py-3"><div className="h-4 bg-gray-200 rounded w-12" /></td>
                      <td className="px-4 py-3"><div className="h-4 bg-gray-200 rounded w-8" /></td>
                      <td className="px-4 py-3"><div className="h-4 bg-gray-200 rounded w-12" /></td>
                      <td className="px-4 py-3"><div className="h-4 bg-gray-200 rounded w-24" /></td>
                      <td className="px-4 py-3"><div className="h-4 bg-gray-200 rounded w-16" /></td>
                      <td className="px-4 py-3"><div className="h-4 bg-gray-200 rounded w-28" /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* CSS for shimmer animation */}
            <style>{`
            @keyframes shimmer {
              0% { background-position: 200% 0; }
              100% { background-position: -200% 0; }
            }
            @keyframes shimmer-glow {
              0% { transform: translateX(-100%); }
              100% { transform: translateX(200%); }
            }
          `}</style>
          </div>
        )}

      {error && (
        <p className="mt-4 text-sm text-red-600 bg-red-50 border border-red-100 rounded px-3 py-2">
          {error}
        </p>
      )}

      {isLoadingSavedSchedule && !error && (
        <p className="mt-4 text-sm text-gray-600 bg-gray-50 border border-gray-100 rounded px-3 py-2">
          Loading saved schedule...
        </p>
      )}

      {!isLoadingSavedSchedule && savedScheduleMessage && !error && (
        <p className="mt-4 text-sm text-gray-600 bg-gray-50 border border-gray-100 rounded px-3 py-2">
          {savedScheduleMessage}
        </p>
      )}

      {Object.keys(expandedSchedule).length > 0 && (
        <div className="mt-6">
          <div className="flex justify-between items-center mb-3">
            <h2 className="text-lg font-semibold">Generated Slots</h2>
            <div className="flex gap-2 items-center">
              {saveMessage && (
                <span className="text-sm text-green-600 font-medium">
                  {saveMessage}
                </span>
              )}
              <button
                type="button"
                onClick={handleSave}
                disabled={isSaving}
                className={`px-4 py-2 text-white rounded ${isSaving
                  ? "bg-gray-400 cursor-not-allowed"
                  : "bg-green-600 hover:bg-green-700"
                  }`}
              >
                {isSaving ? "Saving..." : "Save to Database"}
              </button>
            </div>
          </div>

          {/* Render separate table for each block */}
          {Object.keys(expandedSchedule)
            .sort() // Sort blocks alphabetically (Block A, Block B, etc.)
            .map((blockLabel) => (
              <div key={blockLabel} className="mb-6">
                <div className="flex items-center justify-between mb-2">
                  <h3 className="text-md font-semibold text-gray-700">
                    {blockLabel}
                  </h3>
                  <span className="text-sm text-gray-500">
                    scheduled {expandedSchedule[blockLabel].length}/{plannedSubjectCount || expandedSchedule[blockLabel].length}
                  </span>
                </div>
                <div className="overflow-x-auto border border-gray-200 rounded">
                  <table className="min-w-full divide-y divide-gray-200">
                    <thead className="bg-gray-50">
                      <tr>
                        <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                          Code
                        </th>
                        <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                          Descriptive Title
                        </th>
                        <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                          Type
                        </th>
                        <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                          Unit
                        </th>
                        <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                          Days
                        </th>
                        <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                          Time
                        </th>
                        <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                          Room
                        </th>
                        <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                          Instructor
                        </th>
                      </tr>
                    </thead>
                    <tbody className="bg-white divide-y divide-gray-200">
                      {expandedSchedule[blockLabel].map(renderScheduleRow)}
                    </tbody>
                  </table>
                </div>
              </div>
            ))}
        </div>
      )}

      {!isSubmitting && Object.keys(expandedSchedule).length === 0 && !error && (
        <p className="mt-6 text-sm text-gray-500">
          {hasCheckedSavedSchedule
            ? "No schedule to display for the current selection."
            : "Run the scheduler to see results."}
        </p>
      )}

      {jobStatus && (
        <p className="mt-4 text-sm text-gray-500">
          Scheduler status:{" "}
          <span className="font-semibold capitalize">{jobStatus}</span>
          {jobStatus === "queued" || jobStatus === "running"
            ? " — please keep this page open while we generate the schedule."
            : ""}
        </p>
      )}
    </div>
  );
}
