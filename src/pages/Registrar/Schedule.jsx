import { useEffect, useMemo, useState } from "react";
import { list } from "../../store/db";
import {
  generateSchedule as generateScheduleApi,
  getScheduleStatus,
  loadSchedule as loadScheduleApi,
  saveSchedule,
  mergeSubjects,
  validateScheduleItem,
  getSchedulingSuggestions,
  checkAvailability
} from "../../services/api";
import SchedulerDiagnostics from "../../components/SchedulerDiagnostics";

const YEARS = [1, 2, 3, 4];
const BLOCK_OPTIONS = [1, 2, 3, 4];
const SEMESTERS = [1, 2];

// Helper to ensure every schedule item has a UI-stable ID
const withUiIds = (items) => {
  if (!Array.isArray(items)) return [];
  return items.map(item => ({
    ...item,
    _uiId: item._uiId || `ui_${Math.random().toString(36).substr(2, 9)}_${Date.now()}`
  }));
};

export default function RegistrarSchedule() {
  const [courses, setCourses] = useState([]);
  const [instructors, setInstructors] = useState([]);
  const [days, setDays] = useState([]);
  const [subjects, setSubjects] = useState([]);
  const [rooms, setRooms] = useState([]);
  const [buildings, setBuildings] = useState([]);
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
  const [diagnostics, setDiagnostics] = useState({});

  // Animation states for progressive subject reveal
  const [revealedCount, setRevealedCount] = useState(0);
  const [isRevealing, setIsRevealing] = useState(false);

  // Edit / Override states
  const [editingItem, setEditingItem] = useState(null);
  const [resolvingItem, setResolvingItem] = useState(null);
  const [availableResources, setAvailableResources] = useState({ rooms: [], instructors: [] });
  const [isCheckingAvailability, setIsCheckingAvailability] = useState(false);
  const [suggestions, setSuggestions] = useState([]);
  const [loadingSuggestions, setLoadingSuggestions] = useState(false);
  const [validationResult, setValidationResult] = useState({ valid: true, messages: [] });
  const [isValidating, setIsValidating] = useState(false);

  // Recommendations modal state
  const [recommendationModalItem, setRecommendationModalItem] = useState(null);

  // Merge modal state (post-scheduling)
  const [mergeModal, setMergeModal] = useState({ open: false, sourceSubjectId: null, targetId: '' });
  const [mergeProcessing, setMergeProcessing] = useState(false);



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
        // Load buildings for shared flag lookup
        let buildingList = [];
        try {
          const bRes = await fetch('http://localhost:8000/api/buildings');
          if (bRes.ok) buildingList = await bRes.json();
        } catch (e) { console.error('Failed to load buildings', e); }
        setCourses(courseList || []);
        setInstructors(instructorList || []);
        setDays(dayList || []);
        setSubjects(subjectList || []);
        setRooms(roomList || []);
        setBuildings(buildingList);
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
          setSchedule(withUiIds(items));
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
    setDiagnostics({});
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
        setSchedule(withUiIds(scheduledItems));
        setDiagnostics(result.diagnostics || {});
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
          // Handle result format where result might be wrapped in another result object
          // status.result from API is typically { items: [], count: N, diagnostics: {} } OR just []
          const finalResult = status.result || [];

          let scheduledItems = [];
          let resultDiagnostics = {};

          if (Array.isArray(finalResult)) {
            scheduledItems = finalResult;
            resultDiagnostics = status.diagnostics || {};
          } else if (typeof finalResult === 'object') {
            scheduledItems = finalResult.items || finalResult.scheduled || [];
            resultDiagnostics = finalResult.diagnostics || status.diagnostics || {};
          }

          setJobStatus("succeeded");
          setSchedule(withUiIds(scheduledItems));
          setDiagnostics(resultDiagnostics);
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

  // --- Manual Override Logic ---

  function openEditModal(slot) {
    // Detect MW/TTH pattern from combined label
    let dayMode = "SINGLE";
    let dayIds = slot._dayIds || [slot.day_id];

    if (slot._combinedDaysLabel === "M-W") {
      dayMode = "MW";
      // Get the day IDs for M and W
      const m = days.find(d => d.label === 'M');
      const w = days.find(d => d.label === 'W');
      if (m && w) {
        dayIds = [m.id, w.id];
      }
    } else if (slot._combinedDaysLabel === "T-TH") {
      dayMode = "TTH";
      const t = days.find(d => d.label === 'T');
      const th = days.find(d => d.label === 'TH');
      if (t && th) {
        dayIds = [t.id, th.id];
      }
    }

    // Parse time from the slot
    let startTime = "07:30";
    let endTime = "09:00";

    if (slot.start_min != null && slot.end_min != null) {
      startTime = formatTo24Hour(slot.start_min);
      endTime = formatTo24Hour(slot.end_min);
    } else if (slot.time && typeof slot.time === 'string') {
      // Parse from time string like "7:00 AM - 8:30 AM"
      const parsed = parseTimeRangeFromItem(slot);
      if (parsed) {
        startTime = minutesToTimeString(parsed.start);
        endTime = minutesToTimeString(parsed.end);
      }
    }

    setEditingItem({
      ...slot,
      _roomId: slot.room_id || "",
      _instructorId: slot.instructor_id || "",
      _dayId: slot.day_id || dayIds[0] || "",
      _dayIds: dayIds,
      _originalDayIds: dayIds,
      _dayMode: dayMode,
      _startTime: startTime,
      _endTime: endTime,
    });
    setValidationResult({ valid: true, messages: [] });
  }

  // Helper to convert minutes to HH:MM string
  function minutesToTimeString(minutes) {
    const h = Math.floor(minutes / 60);
    const m = minutes % 60;
    return `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}`;
  }

  function formatTo24Hour(minutes) {
    const h = Math.floor(minutes / 60);
    const m = minutes % 60;
    return `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}`;
  }

  async function validateInfo(item, isAutoCheck = false) {
    if (!item) return;
    setIsValidating(true);

    const allMessages = [];

    // --- TIME SANITY CHECK ---
    const startMinutes = parseTimeToMinutes(item._startTime);
    const endMinutes = parseTimeToMinutes(item._endTime);

    if (startMinutes != null && endMinutes != null && endMinutes <= startMinutes) {
      allMessages.push("Invalid Time Range: End time must be after start time.");
      setValidationResult({
        valid: false,
        messages: allMessages
      });
      setIsValidating(false);
      return; // Stop validation early
    }

    // --- LOCAL CONFLICT CHECK (against in-memory schedule items) ---
    try {
      const localConflicts = checkLocalConflicts(item);
      allMessages.push(...localConflicts);
    } catch (err) {
      console.error("Local conflict check error:", err);
    }

    // --- BACKEND CONFLICT CHECK (against database records) ---
    try {
      // Prepare day IDs, filtering out invalid values
      let dayIdsToSend = [];
      if (item._dayIds && item._dayIds.length > 0) {
        dayIdsToSend = item._dayIds.filter(d => d != null && !isNaN(d));
      }
      if (dayIdsToSend.length === 0 && item._dayId) {
        const dayIdNum = Number(item._dayId);
        if (!isNaN(dayIdNum)) {
          dayIdsToSend = [dayIdNum];
        }
      }

      // If still no valid days, skip backend validation
      if (dayIdsToSend.length === 0) {
        console.warn("No valid day IDs to validate");
      } else {
        const res = await validateScheduleItem({
          id: item.id || null,
          subject_id: item.subject_id,
          instructor_id: item._instructorId ? Number(item._instructorId) : null,
          room_id: item._roomId ? Number(item._roomId) : null,
          day_id: dayIdsToSend[0] || null, // Primary day
          day_ids: dayIdsToSend,
          start_time: item._startTime,
          end_time: item._endTime,
          course_id: Number(form.course_id),
          year: Number(form.year),
          semester: Number(form.semester),
          block: item._blockLabel || item.block || null
        });

        // Merge backend messages (avoid duplicates)
        if (res.messages && res.messages.length > 0) {
          res.messages.forEach(msg => {
            if (!allMessages.includes(msg)) {
              allMessages.push(msg);
            }
          });
        }
      }
    } catch (err) {
      console.error("Backend validation error:", err);
      if (!isAutoCheck) {
        allMessages.push("Backend validation failed: " + err.message);
      }
    }

    setValidationResult({
      valid: allMessages.length === 0,
      messages: allMessages
    });
    setIsValidating(false);
  }

  // Check for conflicts against in-memory schedule items
  function checkLocalConflicts(editedItem) {
    const conflicts = [];

    // Parse proposed times
    const proposedStart = parseTimeToMinutes(editedItem._startTime);
    const proposedEnd = parseTimeToMinutes(editedItem._endTime);

    if (proposedStart === null || proposedEnd === null) return conflicts;

    // Get days to check
    const daysToCheck = editedItem._dayIds && editedItem._dayIds.length > 0
      ? editedItem._dayIds
      : [Number(editedItem._dayId)];

    // Get the original day IDs to exclude ourselves
    const originalDayIds = editedItem._originalDayIds || [editedItem.day_id];

    // Iterate through all schedule items
    schedule.forEach(item => {
      // Skip the item we're editing (match by subject + original days)
      if (item.subject_id === editedItem.subject_id &&
        originalDayIds.includes(item.day_id)) {
        return; // Skip self
      }

      // Check if this item shares any day with our proposed days
      const itemDayId = item.day_id || item.dayId;
      if (!daysToCheck.includes(itemDayId)) return;

      // Parse existing item's time
      const itemTimes = parseTimeRangeFromItem(item);
      if (!itemTimes) return;

      const { start: itemStart, end: itemEnd } = itemTimes;

      // Check for time overlap
      const overlaps = Math.max(proposedStart, itemStart) < Math.min(proposedEnd, itemEnd);
      if (!overlaps) return;

      // Check specific conflict types
      const proposedRoomId = editedItem._roomId ? Number(editedItem._roomId) : null;
      const proposedInstrId = editedItem._instructorId ? Number(editedItem._instructorId) : null;
      const itemRoomId = item.room_id || item.roomId;
      const itemInstrId = item.instructor_id || item.instructorId;

      // Room conflict
      if (proposedRoomId && itemRoomId && proposedRoomId === itemRoomId) {
        const proposedRoomName = getRoomName(proposedRoomId);
        // Exception: FIELD room allows overlaps (multi-class area)
        if (!proposedRoomName || !proposedRoomName.includes("FIELD")) {
          const subjectCode = getSubjectCode(item.subject_id);
          conflicts.push(`Room Conflict (Local): Room is occupied by ${subjectCode} at this time.`);
        }
      }

      // Instructor conflict
      if (proposedInstrId && itemInstrId && proposedInstrId === itemInstrId) {
        const proposedRoomName = getRoomName(proposedRoomId);
        // Exception: If using FIELD, assume mass supervision is allowed
        if (!proposedRoomName || !proposedRoomName.includes("FIELD")) {
          const subjectCode = getSubjectCode(item.subject_id);
          conflicts.push(`Instructor Conflict (Local): Instructor is teaching ${subjectCode} at this time.`);
        }
      }

      // Student group conflict (same block)
      const itemBlock = item.block || "";
      const editBlock = editedItem.block || editedItem._blockLabel || "";
      if (itemBlock === editBlock) {
        const subjectCode = getSubjectCode(item.subject_id);
        conflicts.push(`Student Group Conflict (Local): Block has ${subjectCode} at this time.`);
      }
    });

    // Deduplicate conflict messages (multi-day subjects like T-TH produce
    // one message per day row, but the messages are identical)
    return [...new Set(conflicts)];
  }

  // Parse "HH:MM" or "H:MM AM/PM" to minutes from midnight
  function parseTimeToMinutes(timeStr) {
    if (!timeStr) return null;

    // Handle 24h format (from input type="time")
    if (timeStr.includes(":") && !timeStr.includes(" ")) {
      const [h, m] = timeStr.split(":").map(Number);
      return h * 60 + m;
    }

    // Handle 12h format
    const match = timeStr.match(/(\d{1,2}):(\d{2})\s*(AM|PM)/i);
    if (match) {
      let h = parseInt(match[1], 10);
      const m = parseInt(match[2], 10);
      const period = match[3].toUpperCase();
      if (period === "PM" && h !== 12) h += 12;
      if (period === "AM" && h === 12) h = 0;
      return h * 60 + m;
    }

    return null;
  }

  // Parse time range from schedule item (handles various formats)
  function parseTimeRangeFromItem(item) {
    // If start_min/end_min are available, use them directly
    if (item.start_min != null && item.end_min != null) {
      return { start: item.start_min, end: item.end_min };
    }

    // Parse from time string
    const timeStr = item.time || item.time_label || "";
    if (!timeStr) return null;

    // Normalize dashes
    const normalized = timeStr.replace(/[â€“—]/g, "-");
    const parts = normalized.split("-");

    if (parts.length >= 2) {
      const start = parseTimeToMinutes(parts[0].trim());
      const end = parseTimeToMinutes(parts[1].trim());
      if (start !== null && end !== null) {
        return { start, end };
      }
    }

    return null;
  }

  // Auto-validation with debounce
  useEffect(() => {
    if (!editingItem) return;

    const timer = setTimeout(() => {
      validateInfo(editingItem, true);
    }, 800);

    return () => clearTimeout(timer);
  }, [
    editingItem?._dayId,
    editingItem?._dayMode,
    editingItem?._startTime,
    editingItem?._endTime,
    editingItem?._roomId,
    editingItem?._instructorId
  ]);

  function handleEditChange(e) {
    const { name, value } = e.target;

    setEditingItem(prev => {
      const next = { ...prev, [name]: value };

      if (name === "_dayId") {
        if (value === "MW") {
          const m = days.find(d => d.label === 'M');
          const w = days.find(d => d.label === 'W');
          if (m && w) {
            next._dayIds = [m.id, w.id];
            next._dayMode = "MW";
            next._dayId = m.id;
          }
        } else if (value === "TTH") {
          const t = days.find(d => d.label === 'T');
          const th = days.find(d => d.label === 'TH');
          if (t && th) {
            next._dayIds = [t.id, th.id];
            next._dayMode = "TTH";
            next._dayId = t.id;
          }
        } else {
          const dayIdNum = Number(value);
          next._dayIds = [dayIdNum];
          next._dayMode = "SINGLE";
          next._dayId = dayIdNum;
        }
      }
      return next;
    });
    setValidationResult({ valid: true, messages: [] });
  }

  // Note: Save override logic is now inlined directly in the Save button onClick handler
  function mergeEdit(original, edited) {
    // Construct new time string "HH:MM-HH:MM"
    const timeStr = `${edited._startTime}-${edited._endTime}`;

    return {
      ...original,
      room_id: edited._roomId ? Number(edited._roomId) : null,
      instructor_id: edited._instructorId ? Number(edited._instructorId) : null,
      day_id: Number(edited._dayId),
      time: timeStr,
      // Clear min/max so UI calculates from string or we update them
      start_min: getMinutes(edited._startTime),
      end_min: getMinutes(edited._endTime),
    };
  }

  function getMinutes(timeStr) {
    if (!timeStr) return null;
    const [h, m] = timeStr.split(':').map(Number);
    return h * 60 + m;
  }

  const formatTo12HourStr = (time24) => {
    if (!time24) return "";
    const [h, m] = time24.split(":").map(Number);
    const suffix = h >= 12 ? "PM" : "AM";
    const h12 = h % 12 || 12;
    return `${h12}:${m.toString().padStart(2, '0')} ${suffix}`;
  };




  function handleEditChange(e) {
    const { name, value } = e.target;
    setEditingItem(prev => ({ ...prev, [name]: value }));
    setValidationResult({ valid: true, messages: [] });
  }

  function handleSaveOverride() {
    setSchedule(prev => prev.map(item => {
      // Use _uiId for robust matching of edited items
      if (editingItem._uiId && item._uiId === editingItem._uiId) {
        return mergeEdit(item, editingItem);
      }
      // Fallback for items without _uiId (should not happen with withUiIds)
      if (item.id && editingItem.id && item.id === editingItem.id) {
        return mergeEdit(item, editingItem);
      }
      return item;
    }));
    setEditingItem(null);
  }

  function mergeEdit(original, edited) {
    const timeStr = `${edited._startTime}-${edited._endTime}`;
    return {
      ...original,
      room_id: edited._roomId ? Number(edited._roomId) : null,
      instructor_id: edited._instructorId ? Number(edited._instructorId) : null,
      day_id: Number(edited._dayId),
      time: timeStr,
      start_min: getMinutes(edited._startTime),
      end_min: getMinutes(edited._endTime),
    };
  }

  function getMinutes(timeStr) {
    if (!timeStr) return null;
    const [h, m] = timeStr.split(':').map(Number);
    return h * 60 + m;
  }

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
    return subject?.description || "\u2014";
  };

  const getSubjectType = (id) => {
    const subject = getSubject(id);
    return subject?.type || "\u2014";
  };

  const getSubjectUnit = (id) => {
    const subject = getSubject(id);
    return subject?.unit ?? "\u2014";
  };

  const getRoomName = (id) => {
    if (!id) return "\u2014";
    const room = rooms.find((r) => r.id === id);
    return room?.name || `ID: ${id}`;
  };

  const getInstructorName = (id) => {
    if (!id) return "\u2014";
    const instructor = instructors.find((i) => i.id === id);
    if (!instructor) return `ID: ${id}`;
    const firstName = instructor.first_name || instructor.firstName || "";
    const lastName = instructor.last_name || instructor.lastName || "";
    const name = `${firstName} ${lastName}`.trim();
    return name || `ID: ${id}`;
  };

  const getDayName = (id) => {
    if (!id) return "\u2014";
    const day = days.find((d) => d.id === id);
    return day?.label || `ID: ${id}`;
  };

  // Convert time to 12-hour format
  const normalizeTimeRangeString = (value) => {
    if (typeof value !== "string") {
      return value;
    }
    // Normalize dashes and strip day prefixes (M, T, W, TH, F, S followed by space)
    let normalized = value.replace(/[\u2013\u2014\u2212]/g, "-");
    // Remove day prefix at the start (e.g., "T 17:30" -> "17:30", "M-W 7:00" -> "7:00")
    normalized = normalized.replace(/^(M|T|W|TH|F|S|M-W|T-TH)\s+/i, "");
    return normalized;
  };

  const formatTime12Hour = (timeStrRaw) => {
    if (!timeStrRaw) return "\u2014";
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

    // Handle format like "7:30-9:00" or "07:30-09:00" or "17:30 - 19:00" (24-hour format)
    if (timeStr.includes("-") && timeStr.includes(":")) {
      const parts = timeStr.split("-").map(p => p.trim());
      if (parts.length === 2) {
        const start12 = convert24To12(parts[0]);
        const end12 = convert24To12(parts[1]);
        return `${start12} - ${end12}`;
      }
    }

    // Handle single time like "7:30" or "07:30" or "17:30"
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
    if (!time24) return "\u2014";
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
        _dayIds: dayIds, // Keep the day IDs for edit modal
        _combinedDaysLabel: combinedDays || (labels[0] || "\u2014"),
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

  // Feature 1: Detect subjects with no eligible active instructor (pre-scheduling)
  const normalizeCode = (str) => str.toUpperCase().replace(/[^A-Z0-9]/g, '');

  const subjectsWithoutInstructor = useMemo(() => {
    const courseId = Number(form.course_id);
    const selectedYear = Number(form.year);
    const selectedSemester = Number(form.semester);
    if (!courseId || !selectedYear || !selectedSemester) return [];

    const plannedSubjects = (subjects || []).filter(s => {
      return Number(s.course_id) === courseId &&
        Number(s.year_level) === selectedYear &&
        Number(s.semester) === selectedSemester;
    });

    const activeInstructors = (instructors || []).filter(i => i.is_active !== false);

    // Deduplicate by subject code (e.g. LEC + LAB variants of same subject)
    const seen = new Set();
    return plannedSubjects.filter(subj => {
      const code = (subj.code || '').trim();
      if (!code) return false;
      const normCode = normalizeCode(code);
      if (seen.has(normCode)) return false; // skip LEC/LAB duplicate

      const hasInstructor = activeInstructors.some(instr => {
        const assignable = (instr.assignable_courses || instr.assignableCourses || '');
        return assignable.split(',').some(c => normalizeCode(c) === normCode);
      });

      if (!hasInstructor) {
        seen.add(normCode);
        return true;
      }
      return false;
    });
  }, [subjects, instructors, form.course_id, form.year, form.semester]);

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

    return "\u2014";
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

    // Check if the assigned instructor is specialized for this subject
    let isSpecialized = true;
    if (instructorId && subjectCode) {
      const assignedInst = instructors.find(i => i.id === instructorId);
      if (assignedInst) {
        const assignable = (assignedInst.assignable_courses || assignedInst.assignableCourses || '').toUpperCase();
        if (assignable.trim().length > 0) {
          // Strip everything except letters and numbers for a bulletproof match
          const normalizeString = (str) => str.toUpperCase().replace(/[^A-Z0-9]/g, '');
          const cleanSubjectCode = normalizeString(subjectCode);

          isSpecialized = assignable.split(',').some(c => normalizeString(c) === cleanSubjectCode);
        }
      }
    }

    // Diagnostics check for unscheduled items
    const isUnscheduled = !dayId && !slot.time && !roomId;




    // Try multiple lookup strategies to handle type mismatches
    // Backend nests per-subject diagnostics inside diagnostics.unscheduled_reasons
    const diagReasons = diagnostics?.unscheduled_reasons || diagnostics?._raw || diagnostics || {};
    const diagEntry = diagReasons[subjectId] ||
      diagReasons[String(subjectId)] ||
      diagReasons[Number(subjectId)];

    let failureReason = null;
    let failureDetail = null;

    if (diagEntry) {
      if (typeof diagEntry === 'string') {
        failureReason = diagEntry;
        failureDetail = "Unscheduled subject";
      } else if (typeof diagEntry === 'object') {
        failureReason = diagEntry.failure_reason;
        failureDetail = diagEntry.detail || JSON.stringify(diagEntry.metrics) || "No details available";
      }
    }

    // Get block label (Block A, Block B, etc.)
    const blockLabel = slot._blockLabel || "";

    // Create unique key that includes block number if applicable
    // Create unique key using _uiId if available
    const key = slot._uiId || `${slot.subject_id || slot.room_id || idx}-${idx}-${blockNum}`;

    // Animation: determine if this row should be visible yet
    const isVisible = !isRevealing || idx < revealedCount;
    const animationDelay = isRevealing ? `${idx * 30}ms` : '0ms';

    return (
      <tr
        key={key}
        onClick={() => openEditModal(slot)}
        title={isUnscheduled ? (failureDetail || "Unscheduled") : "Click to edit schedule"}
        className={`hover:bg-blue-50 transition-all duration-300 ease-out cursor-pointer ${isVisible
          ? 'opacity-100 translate-y-0'
          : 'opacity-0 translate-y-2'
          }`}
        style={{
          transitionDelay: animationDelay,
          transform: isVisible ? 'translateY(0)' : 'translateY(8px)',
        }}

      >
        <td className="px-4 py-2 text-sm text-gray-700">{subjectCode}</td>
        <td className="px-4 py-2 text-sm text-gray-700">{subjectDescription}</td>
        <td className="px-4 py-2 text-sm text-gray-700">{subjectType}</td>
        <td className="px-4 py-2 text-sm text-gray-700">{subjectUnit}</td>
        <td className="px-4 py-2 text-sm text-gray-700">{dayLabel}</td>
        <td className="px-4 py-2 text-sm text-gray-700">
          {isUnscheduled ? (
            <div className="flex flex-col items-start gap-1">
              {failureReason && (
                <span className="text-red-600 font-semibold text-xs bg-red-50 px-2 py-1 rounded border border-red-100">
                  {failureReason}
                </span>
              )}
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  const recs = diagEntry?.recommendations || [];
                  setResolvingItem({ ...slot, failureReason, recommendations: recs });
                }}
                className="text-white text-xs bg-blue-500 hover:bg-blue-600 px-2 py-1 rounded shadow-sm flex items-center gap-1 active:scale-95 transition-transform"
              >
                <svg xmlns="http://www.w3.org/2000/svg" className="h-3 w-3" viewBox="0 0 20 20" fill="currentColor">
                  <path fillRule="evenodd" d="M11.3 1.046A1 1 0 0112 2v5h4a1 1 0 01.82 1.573l-7 10A1 1 0 018 18v-5H4a1 1 0 01-.82-1.573l7-10a1 1 0 011.12-.38z" clipRule="evenodd" />
                </svg>
                Resolve
              </button>
            </div>
          ) : (
            <div className="flex items-center gap-2">
              <span>{timeLabel}</span>
              {slot.is_recommended && (
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    // Get recommendations from slot (auto-applied) or diagnostics (unscheduled)
                    const diagReasonsAlt = diagnostics?.unscheduled_reasons || diagnostics?._raw || diagnostics || {};
                    const diagEntry = diagReasonsAlt[slot.subject_id] || diagReasonsAlt[String(slot.subject_id)];
                    const alternatives = slot.alternatives || diagEntry?.recommendations || [];
                    setRecommendationModalItem({ ...slot, alternatives });
                  }}
                  className="inline-flex items-center gap-1 px-2 py-0.5 text-xs font-medium text-amber-700 bg-amber-100 border border-amber-200 rounded-full hover:bg-amber-200 transition-colors cursor-pointer"
                  title="Click to see alternative scheduling options"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" className="h-3 w-3" viewBox="0 0 20 20" fill="currentColor">
                    <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
                  </svg>
                  Suggested
                </button>
              )}
            </div>
          )}
        </td>
        <td className="px-4 py-2 text-sm text-gray-700">
          <div className="flex items-center gap-2">
            <span>{roomLabel}</span>
            {slot.is_soft_constraint && (
              <span
                className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-bold bg-orange-100 text-orange-700 border border-orange-200 uppercase tracking-wide cursor-help"
                title="Preferred room was unavailable (Simple Fallback applied)"
              >
                Fallback
              </span>
            )}
          </div>
        </td>
        <td className="px-4 py-2 text-sm text-gray-700">
          {instructorId ? (
            <div className="flex flex-col items-start gap-1">
              <span>{instructorLabel}</span>
              {!isSpecialized && (
                <span
                  className="inline-block px-1.5 py-0.5 rounded text-[10px] font-bold bg-amber-100 text-amber-700 border border-amber-200 uppercase tracking-wide cursor-help"
                  title="Instructor does not have this subject in their specialization"
                >
                  Not Specialized
                </span>
              )}
            </div>
          ) : (
            <span className="inline-block px-2 py-0.5 rounded-full text-xs font-semibold bg-red-100 text-red-700 border border-red-200">
              No Instructor
            </span>
          )}
        </td>
        <td className="px-2 py-2 text-sm" onClick={e => e.stopPropagation()}>
          <button
            onClick={(e) => {
              e.stopPropagation();
              setMergeModal({ open: true, sourceSubjectId: subjectId, targetId: '' });
            }}
            className="inline-flex items-center justify-center w-7 h-7 rounded-full bg-indigo-50 hover:bg-indigo-100 text-indigo-600 hover:text-indigo-800 transition-colors"
            title="Merge this subject"
          >
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-3.5 h-3.5">
              <path d="M3.9 12c0-1.71 1.39-3.1 3.1-3.1h4V7H7c-2.76 0-5 2.24-5 5s2.24 5 5 5h4v-1.9H7c-1.71 0-3.1-1.39-3.1-3.1zM8 13h8v-2H8v2zm9-6h-4v1.9h4c1.71 0 3.1 1.39 3.1 3.1s-1.39 3.1-3.1 3.1h-4V17h4c2.76 0 5-2.24 5-5s-2.24-5-5-5z" />
            </svg>
          </button>
        </td>
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

        <div className="sm:col-span-2">
          {subjectsWithoutInstructor.length > 0 && (
            <div className="mb-3 p-3 bg-amber-50 border border-amber-200 rounded-lg text-sm">
              <div className="flex items-center gap-2 text-amber-800 font-semibold mb-1">
                <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
                  <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                </svg>
                {subjectsWithoutInstructor.length} subject{subjectsWithoutInstructor.length > 1 ? 's' : ''} without eligible active instructor
              </div>
              <div className="text-amber-700 flex flex-wrap gap-1">
                {subjectsWithoutInstructor.map(s => (
                  <span key={s.id} className="inline-block px-2 py-0.5 bg-amber-100 border border-amber-300 rounded text-xs font-mono">
                    {s.code}
                  </span>
                ))}
              </div>
            </div>
          )}
          <div className="flex justify-end">
            <button
              type="submit"
              disabled={isSubmitting}
              className={`px-4 py-2 text-white rounded ${isSubmitting ? "bg-gray-400 cursor-not-allowed" : "bg-blue-600 hover:bg-blue-700"
                }`}
            >
              {isSubmitting ? "Scheduling..." : "Generate Schedule"}
            </button>
          </div>
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

      {/* Scheduler Diagnostics Panel */}
      <SchedulerDiagnostics
        diagnostics={diagnostics}
        isVisible={jobStatus === "succeeded" && Object.keys(diagnostics).length > 0}
      />

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
                        <th className="px-2 py-2 text-center text-xs font-medium text-gray-500 uppercase tracking-wider w-10">
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

      {/* Merge Modal (Post-Scheduling) */}
      {mergeModal.open && (() => {
        const sourceSubject = subjects.find(s => s.id === mergeModal.sourceSubjectId);
        if (!sourceSubject) return null;

        const courseName = (cid) => {
          const c = courses.find(co => co.id === cid);
          return c ? (c.code || c.name || `Course ${c.id}`) : '';
        };

        // Target options: same-type subjects from the same course (exclude source)
        const targetOptions = subjects.filter(s => {
          if (s.id === sourceSubject.id) return false;
          return s.course_id === sourceSubject.course_id;
        });

        const handleConfirmMerge = async () => {
          if (!mergeModal.targetId) { alert('Please select a target subject.'); return; }
          if (mergeModal.targetId === mergeModal.sourceSubjectId) { alert('Cannot merge into itself.'); return; }
          setMergeProcessing(true);
          try {
            const res = await mergeSubjects(mergeModal.sourceSubjectId, mergeModal.targetId);
            alert(`Merged successfully! ${res.schedules_moved || 0} schedules moved.`);
            setMergeModal({ open: false, sourceSubjectId: null, targetId: '' });
            // Reload subjects + schedule
            const [subjectList] = await Promise.all([list("subject")]);
            setSubjects(subjectList || []);
          } catch (err) {
            alert(err.message || 'Merge failed');
          } finally {
            setMergeProcessing(false);
          }
        };

        const selectedTarget = subjects.find(s => s.id === mergeModal.targetId);

        return (
          <div className="fixed inset-0 bg-black/40 flex items-center justify-center p-4 z-50">
            <div className="w-full max-w-2xl bg-white rounded-xl shadow-xl overflow-hidden">
              <div className="bg-indigo-600 px-6 py-4 flex items-center justify-between">
                <h3 className="text-xl font-semibold text-white flex items-center gap-2">
                  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5"><path d="M3.9 12c0-1.71 1.39-3.1 3.1-3.1h4V7H7c-2.76 0-5 2.24-5 5s2.24 5 5 5h4v-1.9H7c-1.71 0-3.1-1.39-3.1-3.1zM8 13h8v-2H8v2zm9-6h-4v1.9h4c1.71 0 3.1 1.39 3.1 3.1s-1.39 3.1-3.1 3.1h-4V17h4c2.76 0 5-2.24 5-5s-2.24-5-5-5z" /></svg>
                  Merge Subject
                </h3>
                <button onClick={() => setMergeModal({ open: false, sourceSubjectId: null, targetId: '' })} className="text-white/80 hover:text-white">
                  <svg xmlns="http://www.w3.org/2000/svg" className="w-5 h-5" viewBox="0 0 20 20" fill="currentColor"><path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" /></svg>
                </button>
              </div>

              <div className="p-6 space-y-4">
                <div className="bg-orange-50 text-orange-800 p-3 rounded-lg text-sm border border-orange-200">
                  <strong>Warning:</strong> The source subject will be deleted. Existing schedules will be moved to the target. This cannot be undone.
                </div>

                {/* Source subject */}
                <div>
                  <div className="text-xs font-semibold text-gray-500 uppercase mb-1">Source (Will be deleted)</div>
                  <div className="bg-red-50 border border-red-200 rounded-lg p-3">
                    <div className="font-medium text-gray-900">{sourceSubject.code}</div>
                    <div className="text-sm text-gray-600">{sourceSubject.description} • {sourceSubject.type} • {sourceSubject.unit} Units</div>
                    <div className="text-xs text-gray-500 mt-1">{courseName(sourceSubject.course_id)}</div>
                  </div>
                </div>

                {/* Arrow */}
                <div className="flex justify-center">
                  <svg xmlns="http://www.w3.org/2000/svg" className="w-6 h-6 text-indigo-400" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 13.5L12 21m0 0l-7.5-7.5M12 21V3" />
                  </svg>
                </div>

                {/* Target options — horizontal scrollable cards */}
                <div>
                  <div className="text-xs font-semibold text-indigo-600 uppercase mb-2">Select Target (Will survive)</div>
                  {targetOptions.length === 0 ? (
                    <p className="text-sm text-gray-500">No eligible target subjects found in this course.</p>
                  ) : (
                    <div className="flex gap-2 overflow-x-auto pb-2">
                      {targetOptions.map(opt => (
                        <button
                          key={opt.id}
                          onClick={() => setMergeModal(prev => ({ ...prev, targetId: opt.id }))}
                          className={`flex-shrink-0 rounded-lg border-2 p-3 text-left transition-all min-w-[160px] max-w-[200px] ${
                            mergeModal.targetId === opt.id
                              ? 'border-indigo-500 bg-indigo-50 ring-2 ring-indigo-200'
                              : 'border-gray-200 bg-white hover:border-indigo-300 hover:bg-indigo-50/50'
                          }`}
                        >
                          <div className="font-semibold text-sm text-gray-900">{opt.code}</div>
                          <div className="text-xs text-gray-600 mt-0.5 line-clamp-2">{opt.description}</div>
                          <div className="text-xs text-gray-500 mt-1">{opt.type} • {opt.unit}u</div>
                        </button>
                      ))}
                    </div>
                  )}
                </div>

                {/* Selected target preview */}
                {selectedTarget && (
                  <div className="bg-green-50 border border-green-200 rounded-lg p-3">
                    <div className="text-xs font-semibold text-green-700 uppercase mb-1">Target Selected</div>
                    <div className="font-medium text-gray-900">{selectedTarget.code}</div>
                    <div className="text-sm text-gray-600">{selectedTarget.description} • {selectedTarget.type} • {selectedTarget.unit} Units</div>
                  </div>
                )}
              </div>

              <div className="bg-gray-50 px-6 py-4 flex justify-end gap-3 border-t">
                <button
                  onClick={() => setMergeModal({ open: false, sourceSubjectId: null, targetId: '' })}
                  className="px-4 py-2 rounded text-gray-700 font-medium hover:bg-gray-200 transition-colors"
                  disabled={mergeProcessing}
                >
                  Cancel
                </button>
                <button
                  onClick={handleConfirmMerge}
                  className="px-4 py-2 rounded bg-indigo-600 text-white font-medium hover:bg-indigo-700 transition-colors disabled:opacity-50"
                  disabled={mergeProcessing || !mergeModal.targetId}
                >
                  {mergeProcessing ? 'Merging...' : 'Confirm Merge'}
                </button>
              </div>
            </div>
          </div>
        );
      })()}

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
            ? " \u2014 please keep this page open while we generate the schedule."
            : ""}
        </p>
      )}

      {/* Edit Modal */}
      {editingItem && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center p-4 z-50">
          <div className={`bg-white rounded-2xl shadow-2xl w-full max-w-3xl overflow-hidden transform transition-all ${validationResult.messages.length > 0
            ? 'ring-4 ring-red-500 shadow-[0_0_50px_rgba(239,68,68,0.4)]'
            : 'ring-1 ring-gray-200'
            }`}>

            {/* Availability Effect */}
            <EffectCheckAvailability
              editingItem={editingItem}
              form={form}
              setAvailableResources={setAvailableResources}
              setIsCheckingAvailability={setIsCheckingAvailability}
              parseTimeToMinutes={parseTimeToMinutes}
            />

            {/* Header */}
            <div className={`px-8 py-5 flex justify-between items-center ${validationResult.messages.length > 0
              ? 'bg-gradient-to-r from-red-600 to-red-500'
              : 'bg-gradient-to-r from-indigo-600 via-blue-600 to-blue-500'
              }`}>
              <div>
                <h3 className="font-bold text-xl text-white tracking-wide">
                  {validationResult.messages.length > 0 ? "\u26A0\uFE0F Conflict Detected" : "\uD83D\uDCDD Edit Schedule"}
                </h3>
                {validationResult.messages.length === 0 && (
                  <p className="text-white/70 text-sm mt-0.5">Modify the schedule details below</p>
                )}
              </div>
              <button
                onClick={() => setEditingItem(null)}
                className="text-white/80 hover:text-white hover:bg-white/20 p-2 rounded-lg transition-all"
              >
                <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            <div className="p-8 space-y-6">
              {/* Subject Info Card */}
              <div className="bg-gradient-to-br from-gray-50 to-gray-100 p-5 rounded-xl border border-gray-200 shadow-sm">
                <div className="flex items-center gap-3">
                  <div className="w-12 h-12 bg-indigo-100 rounded-xl flex items-center justify-center">
                    <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6 text-indigo-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
                    </svg>
                  </div>
                  <div>
                    <div className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Subject</div>
                    <div className="font-bold text-gray-900 text-lg">
                      {getSubjectCode(editingItem.subject_id)}
                      <span className="text-gray-300 mx-2">{'\u2022'}</span>
                      <span className="font-medium text-gray-600">{getSubjectDescription(editingItem.subject_id)}</span>
                    </div>
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-12 gap-6">
                <div className="md:col-span-4">
                  <label className="block text-xs font-bold text-gray-500 uppercase mb-1.5">Day</label>
                  <select
                    name="_dayId"
                    value={
                      editingItem._dayMode === "MW" ? "MW"
                        : editingItem._dayMode === "TTH" ? "TTH"
                          : String(editingItem._dayId || "")
                    }
                    onChange={(e) => {
                      const value = e.target.value;
                      console.log("Day dropdown changed to:", value);

                      setEditingItem(prev => {
                        const next = { ...prev };

                        if (value === "MW") {
                          const m = days.find(d => d.label === 'M');
                          const w = days.find(d => d.label === 'W');
                          if (m && w) {
                            next._dayIds = [m.id, w.id];
                            next._dayMode = "MW";
                            next._dayId = m.id;
                            next._originalDayIds = prev._originalDayIds || [m.id, w.id];
                          }
                        } else if (value === "TTH") {
                          const t = days.find(d => d.label === 'T');
                          const th = days.find(d => d.label === 'TH');
                          if (t && th) {
                            next._dayIds = [t.id, th.id];
                            next._dayMode = "TTH";
                            next._dayId = t.id;
                            next._originalDayIds = prev._originalDayIds || [t.id, th.id];
                          }
                        } else if (value) {
                          // Single day
                          const dayIdNum = Number(value);
                          next._dayIds = [dayIdNum];
                          next._dayMode = "SINGLE";
                          next._dayId = dayIdNum;
                        }

                        return next;
                      });
                      setValidationResult({ valid: true, messages: [] });
                    }}
                    className={`w-full p-2.5 border rounded-lg focus:ring-2 outline-none bg-white ${validationResult.messages.length > 0 ? 'border-red-300 focus:ring-red-500 text-red-900' : 'border-gray-300 focus:ring-blue-500'
                      }`}
                  >
                    <option value="">-- Select Day --</option>
                    <optgroup label="Patterns">
                      <option value="MW">Monday - Wednesday</option>
                      <option value="TTH">Tuesday - Thursday</option>
                    </optgroup>
                    <optgroup label="Single Day">
                      {days.map(d => <option key={d.id} value={String(d.id)}>{d.label}</option>)}
                    </optgroup>
                  </select>
                </div>

                <div className="md:col-span-8">
                  <label className="block text-xs font-bold text-gray-500 uppercase mb-1.5">Time Range</label>
                  <div className="flex gap-4 items-center">
                    <div className="relative flex-1">
                      <input
                        type="time"
                        name="_startTime"
                        value={editingItem._startTime}
                        onChange={handleEditChange}
                        className={`w-full p-2.5 border rounded-lg focus:ring-2 outline-none ${validationResult.messages.length > 0 ? 'border-red-300 focus:ring-red-500 text-red-900' : 'border-gray-300 focus:ring-blue-500'
                          }`}
                      />
                    </div>
                    <span className="text-gray-400 font-medium">{'\u2013'}</span>
                    <div className="relative flex-1">
                      <input
                        type="time"
                        name="_endTime"
                        value={editingItem._endTime}
                        onChange={handleEditChange}
                        className={`w-full p-2.5 border rounded-lg focus:ring-2 outline-none ${validationResult.messages.length > 0 ? 'border-red-300 focus:ring-red-500 text-red-900' : 'border-gray-300 focus:ring-blue-500'
                          }`}
                      />
                    </div>
                  </div>
                </div>

                <div className="md:col-span-6">
                  <label className="block text-xs font-bold text-gray-500 uppercase mb-1.5">Room</label>
                  <select
                    name="_roomId"
                    value={editingItem._roomId}
                    onChange={handleEditChange}
                    className={`w-full p-2.5 border rounded-lg focus:ring-2 outline-none bg-white ${validationResult.messages.length > 0 ? 'border-red-300 focus:ring-red-500 text-red-900' : 'border-gray-300 focus:ring-blue-500 focus:border-blue-500'
                      }`}
                  >
                    <option value="">-- No Room --</option>
                    {rooms.map(r => {
                      const isAvail = availableResources.rooms.includes(r.id);

                      // Check for block-shared subject (e.g., NSTP, PE)
                      const subject = getSubject(editingItem.subject_id);
                      const isNSTP = subject && (subject.is_block_shared || subject.code.toUpperCase().startsWith("NSTP"));
                      // Check if room is in a shared building (replaces hardcoded FIELD name check)
                      const roomBuilding = buildings.find(b => b.id === r.building_id);
                      const isField = roomBuilding && roomBuilding.is_shared;

                      // Logic:
                      // 1. If Room is FIELD and Subject is NSTP -> FORCE ENABLE (ignore availability)
                      // 2. If Room is FIELD and Subject is NOT NSTP -> FORCE DISABLE/HIDE
                      // 3. Otherwise -> Use standard availability check

                      let isDisabled = !isAvail;

                      if (isField) {
                        if (isNSTP) isDisabled = false; // Always allow FIELD for NSTP
                        else isDisabled = true;         // Never allow FIELD for non-NSTP
                      }

                      // Always show current selection even if technically "busy" (maybe it's self)
                      // But for override, we usually want to pick a NEW room. 
                      // Let's mark busy ones.
                      return (
                        <option key={r.id} value={r.id} disabled={isDisabled} className={isDisabled ? "text-gray-400 bg-gray-50" : "font-medium"}>
                          {r.name} {r.building_id ? `(Bldg)` : ''} {!isAvail & !isField ? "(Busy)" : ""} {isField && !isAvail ? "(Shared)" : ""}
                        </option>
                      );
                    })}
                  </select>
                </div>

                <div className="md:col-span-6">
                  <label className="block text-xs font-bold text-gray-500 uppercase mb-1.5">Instructor</label>
                  <select
                    name="_instructorId"
                    value={editingItem._instructorId !== null && editingItem._instructorId !== undefined ? String(editingItem._instructorId) : ""}
                    onChange={handleEditChange}
                    className={`w-full p-2.5 border rounded-lg focus:ring-2 outline-none bg-white ${validationResult.messages.length > 0 ? 'border-red-300 focus:ring-red-500 text-red-900' : 'border-gray-300 focus:ring-blue-500 focus:border-blue-500'
                      }`}
                  >
                    <option value="">-- No Instructor --</option>
                    {instructors
                      .filter(i => {
                        // Filter: Only show eligible instructors if a restriction list exists
                        if (availableResources.eligibleInstructors && availableResources.eligibleInstructors.length > 0) {
                          const isEligible = availableResources.eligibleInstructors.includes(i.id);
                          // ALWAYS show the currently assigned instructor so the value bindings work!
                          return isEligible || String(i.id) === String(editingItem._instructorId);
                        }
                        return true;
                      })
                      .map(i => {
                        const isAvail = availableResources.instructors.includes(i.id);
                        return (
                          <option key={i.id} value={String(i.id)} className={!isAvail ? "text-gray-400 bg-gray-50" : "font-medium"}>
                            {i.last_name}, {i.first_name} {!isAvail ? "(Busy)" : ""}
                          </option>
                        );
                      })}
                  </select>
                </div>
              </div>

              {/* Validation Feedback Area */}
              <div className={`transition-all duration-300 ease-in-out ${validationResult.messages.length > 0 ? 'opacity-100 max-h-40' : 'opacity-0 max-h-0 overflow-hidden'
                }`}>
                <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-sm text-red-900 animate-pulse-slow">
                  <div className="font-bold mb-2 flex items-center gap-2 text-red-700">
                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5">
                      <path fillRule="evenodd" d="M9.401 3.003c1.155-2 4.043-2 5.197 0l7.355 12.748c1.154 2-.29 4.5-2.599 4.5H4.645c-2.309 0-3.752-2.5-2.598-4.5L9.4 3.003zM12 8.25a.75.75 0 01.75.75v3.75a.75.75 0 01-1.5 0V9a.75.75 0 01.75-.75zm0 8.25a.75.75 0 100-1.5.75.75 0 000 1.5z" clipRule="evenodd" />
                    </svg>
                    CRITICAL CONFLICTS FOUND
                  </div>
                  <ul className="list-disc pl-5 space-y-1 text-red-800 font-medium">
                    {validationResult.messages.map((m, i) => <li key={i}>{m}</li>)}
                  </ul>
                </div>
              </div>

              <div className="border-t pt-5 flex justify-between items-center">
                <div className="flex items-center gap-2 text-sm text-gray-500 min-h-[1.5rem]">
                  {isValidating && (
                    <>
                      <svg className="animate-spin h-4 w-4 text-blue-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path>
                      </svg>
                      <span>Checking for conflicts...</span>
                    </>
                  )}
                </div>

                <div className="flex gap-3">
                  <button
                    onClick={() => setEditingItem(null)}
                    className="px-5 py-2.5 border border-gray-300 text-gray-700 font-medium rounded-lg hover:bg-gray-50 transition-colors focus:ring-2 focus:ring-gray-200"
                  >
                    Cancel
                  </button>

                  <button
                    onClick={() => {
                      if (!editingItem) return;

                      const targetDayIds = editingItem._dayIds || [Number(editingItem._dayId)];
                      const originalDayIds = editingItem._originalDayIds || [editingItem.day_id];

                      // Create new items for each target day
                      const newItems = targetDayIds.map(dId => {
                        const startStr = formatTo12HourStr(editingItem._startTime);
                        const endStr = formatTo12HourStr(editingItem._endTime);
                        const timeStr = `${startStr} - ${endStr}`;

                        return {
                          ...editingItem,
                          day_id: dId,
                          dayId: dId,
                          time: timeStr,
                          start_time: editingItem._startTime,
                          end_time: editingItem._endTime,
                          start_min: getMinutes(editingItem._startTime),
                          end_min: getMinutes(editingItem._endTime),
                          room_id: Number(editingItem._roomId) || null,
                          roomId: Number(editingItem._roomId) || null,
                          instructor_id: Number(editingItem._instructorId) || null,
                          instructorId: Number(editingItem._instructorId) || null,
                          _uiId: `override-${Date.now()}-${dId}-${Math.random().toString(36).substr(2, 5)}`
                        };
                      });

                      setSchedule(prev => {
                        const filtered = prev.filter(item => {
                          if (item.subject_id !== editingItem.subject_id) return true;
                          // Normalize block comparison
                          // item.block might be "A", "1", etc.
                          // editingItem._blockLabel might be "Block A"
                          const extractBlock = (val) => {
                            if (!val) return "";
                            val = String(val).trim();
                            if (val.startsWith("Block ")) return val.replace("Block ", "");
                            return val;
                          };

                          const itemBlock = extractBlock(item.block || item._blockLabel);
                          const editBlock = extractBlock(editingItem.block || editingItem._blockLabel);

                          // If blocks differ, do not replace/remove (keep checking other items)
                          if (itemBlock !== editBlock) return true;

                          // Debug replacement logic
                          // console.log("Checking item for replacement:", item);
                          // console.log("Original Days:", originalDayIds);

                          const itemDayId = item.day_id || item.dayId;

                          // Logic to detect if we are replacing an "Unscheduled / Resolve" item
                          // Typically such items have NO day_id and NO time/room
                          const isUnscheduledItem = !itemDayId && !item.time && !item.room_id;

                          // If current item is unscheduled, we are replacing it, so remove it.
                          // It's a placeholder, and we now have actual scheduled items for this subject+block.
                          if (isUnscheduledItem) {
                            return false;
                          }

                          if (originalDayIds.includes(itemDayId)) return false;
                          return true;
                        });
                        return [...filtered, ...newItems];
                      });

                      setEditingItem(null);
                      setSaveMessage("Changes applied locally.");
                      setTimeout(() => setSaveMessage(""), 3000);
                    }}
                    disabled={isValidating || validationResult.messages.length > 0}
                    className={`px-5 py-2.5 font-medium rounded-lg shadow-md transition-all focus:ring-2 focus:ring-blue-500 flex items-center gap-2 ${isValidating || validationResult.messages.length > 0
                      ? 'bg-gray-400 cursor-not-allowed text-white shadow-none'
                      : 'bg-blue-600 hover:bg-blue-700 text-white hover:shadow-lg'
                      }`}
                  >
                    {validationResult.messages.length > 0 ? (
                      <>
                        <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                          <path fillRule="evenodd" d="M13.477 14.89A6 6 0 015.11 6.524l8.367 8.368zm1.414-1.414L6.524 5.11a6 6 0 018.367 8.367zM18 10a8 8 0 11-16 0 8 8 0 0116 0z" clipRule="evenodd" />
                        </svg>
                        Cannot Save
                      </>
                    ) : (
                      isValidating ? "Checking..." : "Save Changes"
                    )}
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
      {/* RESOLVE MODAL */}
      {/* RESOLVE MODAL */}
      {resolvingItem && (
        <ResolveModal
          resolvingItem={resolvingItem}
          setResolvingItem={setResolvingItem}
          openEditModal={openEditModal}
          form={form}
        />
      )}


      {/* Recommendations Alternatives Modal */}
      {recommendationModalItem && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl overflow-hidden">
            {/* Header */}
            <div className="px-6 py-4 bg-gradient-to-r from-amber-500 to-orange-500 flex justify-between items-center">
              <div>
                <h3 className="font-bold text-xl text-white tracking-wide">
                  &#x1F4CB; Scheduling Alternatives
                </h3>
                <p className="text-white/80 text-sm mt-0.5">
                  This slot was auto-suggested. Choose a different option if preferred.
                </p>
              </div>
              <button
                onClick={() => setRecommendationModalItem(null)}
                className="text-white/80 hover:text-white hover:bg-white/20 p-2 rounded-lg transition-all"
              >
                <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            <div className="p-6">
              {/* Current Selection */}
              <div className="mb-4 p-4 bg-amber-50 border border-amber-200 rounded-lg">
                <div className="text-xs font-bold text-amber-600 uppercase tracking-wide mb-1">Current (Auto-Selected)</div>
                <div className="flex items-center gap-4 text-sm">
                  <span className="font-semibold text-gray-800">{getSubjectCode(recommendationModalItem.subject_id)}</span>
                  <span className="text-gray-600">{recommendationModalItem.day || getDayName(recommendationModalItem.day_id)}</span>
                  <span className="text-gray-600">{formatTimeRange(recommendationModalItem)}</span>
                  <span className="text-gray-600">{getRoomName(recommendationModalItem.room_id)}</span>
                  <span className="text-gray-600">{getInstructorName(recommendationModalItem.instructor_id)}</span>
                </div>
              </div>

              {/* Alternatives List */}
              <div className="mb-4">
                <h4 className="font-semibold text-gray-700 mb-2 flex items-center gap-2">
                  <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 text-blue-500" viewBox="0 0 20 20" fill="currentColor">
                    <path d="M5 4a1 1 0 00-2 0v7.268a2 2 0 000 3.464V16a1 1 0 102 0v-1.268a2 2 0 000-3.464V4zM11 4a1 1 0 10-2 0v1.268a2 2 0 000 3.464V16a1 1 0 102 0V8.732a2 2 0 000-3.464V4zM16 3a1 1 0 011 1v7.268a2 2 0 010 3.464V16a1 1 0 11-2 0v-1.268a2 2 0 010-3.464V4a1 1 0 011-1z" />
                  </svg>
                  Other Available Options
                </h4>

                {recommendationModalItem.alternatives && recommendationModalItem.alternatives.length > 0 ? (
                  <div className="space-y-2 max-h-60 overflow-y-auto">
                    {recommendationModalItem.alternatives.map((alt, idx) => (
                      <button
                        key={idx}
                        onClick={() => {
                          // Apply this alternative - handle paired days (M-W, T-TH)
                          const altDayIds = alt.day_ids || [alt.day_id];
                          setSchedule(prev => {
                            // Remove existing items for this subject+block
                            const filtered = prev.filter(item => {
                              const matchUi = item._uiId && item._uiId === recommendationModalItem._uiId;
                              const matchSubjBlock = item.subject_id === recommendationModalItem.subject_id && item.block === recommendationModalItem.block;
                              return !(matchUi || matchSubjBlock);
                            });
                            // Add one item per day
                            const newItems = altDayIds.map(dayId => ({
                              ...recommendationModalItem,
                              room_id: alt.room_id,
                              room_name: alt.room_name,
                              instructor_id: alt.instructor_id,
                              instructor_name: alt.instructor_name,
                              day_id: dayId,
                              day: alt.day_label,
                              time: alt.time,
                              start_min: alt.start_min,
                              end_min: alt.end_min,
                              is_recommended: true,
                            }));
                            return [...filtered, ...newItems];
                          });
                          setRecommendationModalItem(null);
                        }}
                        className="w-full text-left p-3 border border-blue-100 bg-blue-50 hover:bg-blue-100 rounded-lg text-sm flex justify-between items-center group transition-colors"
                      >
                        <div className="flex items-center gap-4">
                          <div className="w-8 h-8 bg-blue-200 rounded-full flex items-center justify-center text-blue-700 font-bold text-xs">
                            {idx + 1}
                          </div>
                          <div>
                            <div className="font-semibold text-gray-800">{alt.day_label} @ {alt.time}</div>
                            <div className="text-xs text-gray-600">{alt.room_name} &bull; {alt.instructor_name || 'TBA'}</div>
                          </div>
                        </div>
                        <div className="flex items-center gap-2">
                          <span className="text-xs text-gray-500">Score: {alt.score || '—'}</span>
                          <span className="opacity-0 group-hover:opacity-100 text-blue-600 font-medium text-xs bg-white px-2 py-1 rounded shadow-sm transition-opacity">
                            Apply
                          </span>
                        </div>
                      </button>
                    ))}
                  </div>
                ) : (
                  <div className="bg-gray-50 rounded border border-gray-200 p-4 text-center text-sm text-gray-500">
                    No alternative options available.
                  </div>
                )}
              </div>

              {/* Actions */}
              <div className="flex justify-end gap-3 pt-4 border-t border-gray-200">
                <button
                  onClick={() => setRecommendationModalItem(null)}
                  className="px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 font-medium"
                >
                  Keep Current
                </button>
                <button
                  onClick={() => {
                    setRecommendationModalItem(null);
                    openEditModal(recommendationModalItem);
                  }}
                  className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium shadow-md flex items-center gap-2"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
                    <path d="M13.586 3.586a2 2 0 112.828 2.828l-.793.793-2.828-2.828.793-.793zM11.379 5.793L3 14.172V17h2.828l8.38-8.379-2.83-2.828z" />
                  </svg>
                  Custom Edit
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// Sub-component for Resolve Modal
function ResolveModal({ resolvingItem, setResolvingItem, openEditModal, form }) {
  const [suggestions, setSuggestions] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!resolvingItem) return;

    // Use recommendations passed from parent if available
    if (resolvingItem.recommendations && resolvingItem.recommendations.length > 0) {
      const mappedRecs = resolvingItem.recommendations.map(r => ({
        ...r,
        room: r.room_name,
        day: r.day_label || r.day,
        day_ids: r.day_ids || [r.day_id]
      }));
      setSuggestions(mappedRecs);
      setLoading(false);
      return;
    }

    // Reset
    setSuggestions([]);
    setLoading(true);

    const subjectId = resolvingItem.subject_id;
    const courseId = Number(form.course_id);
    const year = Number(resolvingItem.year || form.year);
    const semester = Number(form.semester);

    getSchedulingSuggestions(subjectId, courseId, year, semester)
      .then(resp => {
        if (resp && resp.suggestions) {
          setSuggestions(resp.suggestions);
        }
      })
      .catch(err => console.error("Failed to fetch suggestions:", err))
      .finally(() => setLoading(false));

  }, [resolvingItem]);

  // Helper inside component to avoid scope issues
  function minutesToTimeString(minutes) {
    const h = Math.floor(minutes / 60);
    const m = minutes % 60;
    return `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}`;
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-lg overflow-hidden animate-in fade-in zoom-in duration-200">
        <div className="bg-gradient-to-r from-blue-600 to-indigo-600 p-4 flex justify-between items-center text-white">
          <h3 className="font-bold text-lg flex items-center gap-2">
            <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
              <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
            </svg>
            Resolve Scheduling Conflict
          </h3>
          <button onClick={() => setResolvingItem(null)} className="hover:bg-white/20 p-1 rounded-full transition-colors">
            <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
              <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
            </svg>
          </button>
        </div>

        <div className="p-6">
          <div className="mb-6">
            <h4 className="text-gray-900 font-semibold text-lg mb-1">
              Subject ID: {resolvingItem.subject_id}
            </h4>
            <div className="flex gap-2 text-sm">
              <span className="bg-gray-100 text-gray-800 px-2 py-0.5 rounded">
                {resolvingItem.year ? `Year ${resolvingItem.year}` : 'Unk Year'}
              </span>
            </div>
          </div>

          <div className="bg-red-50 border border-red-100 rounded-lg p-4 mb-6">
            <div className="text-xs font-bold text-red-500 uppercase tracking-wide mb-1">Diagnosed Issue</div>
            <div className="text-red-800 font-semibold text-lg flex items-center gap-2">
              <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
              </svg>
              {resolvingItem.failureReason || "Unscheduled"}
            </div>
            <p className="text-red-700/80 text-sm mt-1">
              {resolvingItem.failureReason === "Solver Conflict" && "Valid slots exist, but they conflict with other scheduled classes. Try manually placing this subject."}
              {resolvingItem.failureReason === "No Rooms" && "No rooms are available or eligible for this subject type."}
              {resolvingItem.failureReason === "No Instructor" && "No eligible instructor is available."}
              {resolvingItem.failureReason === "Room Conflict" && "All eligible rooms are fully booked during suggested times."}
              {resolvingItem.failureReason === "Instructor Conflict" && "The assigned instructor is fully booked."}
              {resolvingItem.failureReason === "Student Conflict" && "Scheduling this would overlap with another class for this block."}
              {resolvingItem.failureReason === "Unscheduled" && "The scheduler could not find a valid slot."}
            </p>
          </div>

          <div>
            <h5 className="font-semibold text-gray-700 mb-3 flex items-center gap-2">
              <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 text-green-500" viewBox="0 0 20 20" fill="currentColor">
                <path fillRule="evenodd" d="M6.267 3.455a3.066 3.066 0 001.745-.723 3.066 3.066 0 013.976 0 3.066 3.066 0 001.745.723 3.066 3.066 0 012.812 2.812c.051.643.304 1.254.723 1.745a3.066 3.066 0 010 3.976 3.066 3.066 0 00-.723 1.745 3.066 3.066 0 01-2.812 2.812 3.066 3.066 0 00-1.745.723 3.066 3.066 0 01-3.976 0 3.066 3.066 0 00-1.745-.723 3.066 3.066 0 01-2.812-2.812 3.066 3.066 0 00-.723-1.745 3.066 3.066 0 010-3.976 3.066 3.066 0 00.723-1.745 3.066 3.066 0 012.812-2.812zm7.44 5.252a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
              </svg>
              Suggestions
            </h5>

            {loading ? (
              <div className="flex justify-center p-4">
                <svg className="animate-spin h-5 w-5 text-blue-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path>
                </svg>
              </div>
            ) : suggestions.length > 0 ? (
              <div className="space-y-2 max-h-40 overflow-y-auto">
                {suggestions.map((s, idx) => (
                  <button
                    key={idx}
                    onClick={() => {
                      setResolvingItem(null);
                      // Map recommendation fields to what openEditModal reads
                      const overrideItem = {
                        ...resolvingItem,
                        // These are the fields openEditModal uses to detect day pattern:
                        _combinedDaysLabel: s.day_label || s.day,
                        _dayIds: s.day_ids || [s.day_id],
                        // These are read directly by openEditModal as slot.room_id, slot.instructor_id:
                        room_id: s.room_id,
                        instructor_id: s.instructor_id,
                        // Time fields read by openEditModal:
                        start_min: s.start_min,
                        end_min: s.end_min,
                        time: s.time,
                      };
                      openEditModal(overrideItem);
                    }}
                    className="w-full text-left p-2 border border-green-100 bg-green-50 hover:bg-green-100 rounded text-sm text-green-900 flex justify-between items-center group transition-colors"
                  >
                    <div>
                      <div className="font-semibold">{s.day} @ {s.time}</div>
                      <div className="text-xs text-green-700">{s.room || s.room_name} • {s.instructor_name || (s.instructor_id ? `Instructor #${s.instructor_id}` : "No Instructor")}</div>
                    </div>
                    <span className="opacity-0 group-hover:opacity-100 text-green-600 font-medium text-xs bg-white px-2 py-1 rounded shadow-sm">
                      Apply
                    </span>
                  </button>
                ))}
              </div>
            ) : (
              <div className="bg-gray-50 rounded border border-gray-200 p-4 text-center text-sm text-gray-500">
                No automated suggestions found.<br />
                <span className="text-xs">Please use "Manual Override" to force a slot.</span>
              </div>
            )}
          </div>

          <div className="mt-6 flex justify-end gap-3">
            <button
              onClick={() => setResolvingItem(null)}
              className="px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 font-medium"
            >
              Close
            </button>
            <button
              onClick={() => {
                setResolvingItem(null);
                // Pre-fill from first suggestion if available
                const first = suggestions && suggestions.length > 0 ? suggestions[0] : null;
                const overrideItem = first ? {
                  ...resolvingItem,
                  _combinedDaysLabel: first.day_label || first.day,
                  _dayIds: first.day_ids || [first.day_id],
                  room_id: first.room_id,
                  instructor_id: first.instructor_id,
                  start_min: first.start_min,
                  end_min: first.end_min,
                  time: first.time,
                } : resolvingItem;
                openEditModal(overrideItem);
              }}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium shadow-md flex items-center gap-2"
            >
              <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
                <path d="M13.586 3.586a2 2 0 112.828 2.828l-.793.793-2.828-2.828.793-.793zM11.379 5.793L3 14.172V17h2.828l8.38-8.379-2.83-2.828z" />
              </svg>
              Manual Override
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}


// Helper component to run availability check effect
function EffectCheckAvailability({ editingItem, form, setAvailableResources, setIsCheckingAvailability, parseTimeToMinutes }) {
  useEffect(() => {
    if (!editingItem) return;

    const dayId = editingItem._dayId;
    const startMin = parseTimeToMinutes(editingItem._startTime);
    const endMin = parseTimeToMinutes(editingItem._endTime);

    // Only check if we have a valid single day and valid times
    if (!dayId || startMin === null || endMin === null || startMin >= endMin) {
      return;
    }

    let active = true;
    setIsCheckingAvailability(true);

    const year = Number(form.year);
    const semester = Number(form.semester);

    checkAvailability(semester, year, dayId, startMin, endMin, editingItem.subject_id)
      .then(res => {
        if (active && res) {
          console.log("Availability Check Response:", res); // Debug log
          setAvailableResources({
            rooms: res.available_rooms || [],
            instructors: res.available_instructors || [],
            eligibleInstructors: res.eligible_instructors // New field
          });
        }
      })
      .catch(err => console.error("Availability check failed", err))
      .finally(() => {
        if (active) setIsCheckingAvailability(false);
      });

    return () => { active = false; };
  }, [editingItem?._dayId, editingItem?._startTime, editingItem?._endTime]);

  return null;
}
