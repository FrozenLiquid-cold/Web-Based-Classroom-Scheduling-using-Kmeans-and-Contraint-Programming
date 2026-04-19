import { useEffect, useMemo, useState } from "react";
import { createPortal } from "react-dom";
import { useLocation } from "react-router-dom";
import { list } from "../../store/db";
import {
  generateSchedule as generateScheduleApi,
  getScheduleStatus,
  loadSchedule as loadScheduleApi,
  saveSchedule,
  mergeSubjects,
  mergePreview,
  getScheduledSubjectIds,
  validateScheduleItem,
  getSchedulingSuggestions,
  checkAvailability,
  getRoomUtilizationByDay,
  getInstructorHoursSummary
} from "../../services/api";
import SchedulerDiagnostics from "../../components/SchedulerDiagnostics";
import ScheduleTimetable from "../../components/ScheduleTimetable";
import SchoolYearSelector, { computeDefaultSY } from "../../components/SchoolYearSelector";
import DashboardPanel from "./DashboardPanel";
import RoomSchedulePanel from "./RoomSchedulePanel";

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
  const location = useLocation();
  const [openSection, setOpenSection] = useState('scheduler');

  // Hash-based accordion navigation
  useEffect(() => {
    const hash = location.hash.replace('#', '');
    if (hash === 'dashboard' || hash === 'room-schedule') {
      setOpenSection(hash);
      setTimeout(() => {
        const el = document.getElementById(`section-${hash}`);
        if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }, 100);
    } else {
      setOpenSection('scheduler');
    }
  }, [location.hash]);

  const [schoolYear, setSchoolYear] = useState(() => localStorage.getItem('jrmsu.schoolYear') || computeDefaultSY());
  const [courses, setCourses] = useState([]);
  const [instructors, setInstructors] = useState([]);
  const [days, setDays] = useState([]);
  const [subjects, setSubjects] = useState([]);
  const [rooms, setRooms] = useState([]);
  const [buildings, setBuildings] = useState([]);
  const [globalRoomUtil, setGlobalRoomUtil] = useState([]);
  const [form, setForm] = useState({
    course_id: "",
    year: "",
    blocks_count: "",
    semester: "",
  });
  const [selectedProgramCode, setSelectedProgramCode] = useState("");
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
  // Progressive timetable state
  const [partialItems, setPartialItems] = useState([]);
  const [currentPhase, setCurrentPhase] = useState('');
  const [totalSubjects, setTotalSubjects] = useState(0);

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

  // Warnings modal state
  const [showWarningsModal, setShowWarningsModal] = useState(false);
  const [roomUtilCollapsed, setRoomUtilCollapsed] = useState(false);
  const [instrWorkloadCollapsed, setInstrWorkloadCollapsed] = useState(false);
  const [savedInstructorHours, setSavedInstructorHours] = useState({}); // {instructor_id: minutes}

  // Print modal state
  const [showPrintModal, setShowPrintModal] = useState(false);

  // Merge modal state
  // selectedBlocks: Set of "source_A", "target_B" — only these participate
  // resourcePicks: { instructor: "source_A", room: "target_B", time: "source_A" }
  //   Each value is a block key — the ONE block whose resource survives for that type.
  //   All other selected blocks' resources of that type get freed.
  const defaultMergeState = {
    open: false, sourceSubjectId: null, targetId: null,
    showAllCourses: false, targetSearch: '',
    preview: null, previewLoading: false,
    selectedBlocks: new Set(),
    resourcePicks: { instructor: null, room: null, time: null },
    compatChecked: false, conflicts: [], safe: false,
    scheduledIds: null,
  };
  const [mergeModal, setMergeModal] = useState(defaultMergeState);
  const [mergeProcessing, setMergeProcessing] = useState(false);

  function openMergeModal(sourceSubjectId) {
    setMergeModal({ ...defaultMergeState, open: true, sourceSubjectId });
    const sem = Number(form.semester);
    getScheduledSubjectIds(sem || undefined).then(ids => {
      setMergeModal(prev => ({ ...prev, scheduledIds: new Set(ids) }));
    }).catch(err => console.error('Failed to fetch scheduled IDs:', err));
  }

  function selectMergeTarget(targetId) {
    setMergeModal(prev => ({
      ...prev, targetId,
      compatChecked: false, conflicts: [], safe: false,
      preview: null, selectedBlocks: new Set(),
      resourcePicks: { instructor: null, room: null, time: null },
    }));
    if (mergeModal.sourceSubjectId && targetId) {
      loadMergePreviewData(mergeModal.sourceSubjectId, targetId);
    }
  }

  async function loadMergePreviewData(srcId, tgtId) {
    setMergeModal(prev => ({ ...prev, previewLoading: true }));
    try {
      // On re-check, pass current selections so conflict detection only checks selected blocks
      const isRecheck = mergeModal.preview != null;
      const opts = {};
      if (isRecheck && mergeModal.selectedBlocks.size > 0) {
        opts.selected_blocks = [...mergeModal.selectedBlocks];
        opts.resource_picks = mergeModal.resourcePicks;
      }
      const data = await mergePreview(srcId, tgtId, opts);
      setMergeModal(prev => {
        const wasRecheck = !!prev.preview;
        return {
          ...prev, preview: data, previewLoading: false,
          selectedBlocks: wasRecheck ? prev.selectedBlocks : new Set(),
          resourcePicks: wasRecheck ? prev.resourcePicks : { instructor: null, room: null, time: null },
          conflicts: data.conflicts || [], safe: data.safe, compatChecked: true,
        };
      });
    } catch (err) {
      console.error('Preview failed:', err);
      setMergeModal(prev => ({ ...prev, previewLoading: false }));
    }
  }

  function swapMergeDirection() {
    setMergeModal(prev => {
      if (!prev.targetId) return prev;
      const swapKey = k => {
        if (!k) return null;
        if (k.startsWith('source_')) return k.replace('source_', 'target_');
        if (k.startsWith('target_')) return k.replace('target_', 'source_');
        return k;
      };
      const newSelected = new Set();
      prev.selectedBlocks.forEach(key => newSelected.add(swapKey(key)));
      return {
        ...prev,
        sourceSubjectId: prev.targetId,
        targetId: prev.sourceSubjectId,
        selectedBlocks: newSelected,
        resourcePicks: {
          instructor: swapKey(prev.resourcePicks.instructor),
          room: swapKey(prev.resourcePicks.room),
          time: swapKey(prev.resourcePicks.time),
        },
        compatChecked: false, conflicts: [], safe: false, preview: null,
      };
    });
  }

  function toggleBlockSelection(sideBlockKey) {
    setMergeModal(prev => {
      const next = new Set(prev.selectedBlocks);
      if (next.has(sideBlockKey)) {
        next.delete(sideBlockKey);
        // Clear any resource picks pointing to the deselected block
        const newPicks = { ...prev.resourcePicks };
        if (newPicks.instructor === sideBlockKey) newPicks.instructor = null;
        if (newPicks.room === sideBlockKey) newPicks.room = null;
        if (newPicks.time === sideBlockKey) newPicks.time = null;
        return { ...prev, selectedBlocks: next, resourcePicks: newPicks, compatChecked: false };
      } else {
        next.add(sideBlockKey);
        return { ...prev, selectedBlocks: next, compatChecked: false };
      }
    });
  }

  // Pick a resource: e.g. pickResource('instructor', 'source_A')
  function pickResource(type, blockKey) {
    setMergeModal(prev => ({
      ...prev,
      compatChecked: false,
      resourcePicks: { ...prev.resourcePicks, [type]: blockKey },
    }));
  }

  async function handleConfirmMerge() {
    if (!mergeModal.sourceSubjectId || !mergeModal.targetId) { alert('Please select a target subject.'); return; }
    if (mergeModal.targetId === mergeModal.sourceSubjectId) { alert('Cannot merge into itself.'); return; }
    if (mergeModal.selectedBlocks.size === 0) { alert('Please select at least one block to merge.'); return; }
    const picks = mergeModal.resourcePicks;
    if (!picks.instructor) { alert('Please pick an instructor from one of the selected blocks.'); return; }
    if (!picks.room) { alert('Please pick a room from one of the selected blocks.'); return; }
    if (!picks.time) { alert('Please pick a time from one of the selected blocks.'); return; }
    if (!mergeModal.compatChecked) { alert('Please check compatibility first.'); return; }
    if (!mergeModal.safe) { alert('Cannot merge: conflicts detected.'); return; }
    setMergeProcessing(true);
    try {
      const res = await mergeSubjects(mergeModal.sourceSubjectId, mergeModal.targetId, {
        resource_picks: mergeModal.resourcePicks,
        selected_blocks: [...mergeModal.selectedBlocks],
      });
      alert(`Merged successfully! ${res.schedules_moved || 0} schedules moved.`);
      setMergeModal(defaultMergeState);
      const [subjectList] = await Promise.all([list("subject")]);
      setSubjects(subjectList || []);
      const courseId = Number(form.course_id);
      const year = Number(form.year);
      const semester = Number(form.semester);
      if (courseId && year && semester) {
        const resp = await loadScheduleApi(courseId, semester, year, null, schoolYear);
        if (resp && resp.status === 'success') setSchedule(withUiIds(resp.items || []));
      }
    } catch (err) {
      alert(err.message || 'Merge failed');
    } finally {
      setMergeProcessing(false);
    }
  }



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

  // Build unique program options grouped by code
  const programGroups = useMemo(() => {
    const groups = {};
    courses.forEach((c) => {
      const code = (c.code || '').toUpperCase();
      if (!groups[code]) {
        groups[code] = { code, description: c.description, entries: [] };
      }
      groups[code].entries.push(c);
    });
    return groups;
  }, [courses]);

  const programOptions = useMemo(
    () => {
      const codes = Object.keys(programGroups).sort();
      return codes.map((code) => {
        const g = programGroups[code];
        return (
          <option key={code} value={code}>
            {code}
          </option>
        );
      });
    },
    [programGroups]
  );

  // Majors for the selected program code
  const selectedProgramGroup = programGroups[selectedProgramCode] || null;
  const hasMajors = selectedProgramGroup
    ? selectedProgramGroup.entries.some((e) => e.major)
    : false;
  const majorOptions = useMemo(() => {
    if (!selectedProgramGroup || !hasMajors) return [];
    return selectedProgramGroup.entries
      .filter((e) => e.major)
      .sort((a, b) => (a.major || '').localeCompare(b.major || ''))
      .map((e) => (
        <option key={e.id} value={e.id}>
          {e.major}
        </option>
      ));
  }, [selectedProgramGroup, hasMajors]);

  // Handle program code selection
  const handleProgramCodeChange = (e) => {
    const code = e.target.value;
    setSelectedProgramCode(code);
    const group = programGroups[code];
    if (!group) {
      setForm((prev) => ({ ...prev, course_id: "" }));
      return;
    }
    // If only one entry or no majors, auto-select course_id
    const hasM = group.entries.some((en) => en.major);
    if (!hasM && group.entries.length === 1) {
      setForm((prev) => ({ ...prev, course_id: String(group.entries[0].id) }));
    } else if (!hasM) {
      // Multiple entries without majors — pick first
      setForm((prev) => ({ ...prev, course_id: String(group.entries[0].id) }));
    } else {
      // Has majors — wait for major selection
      setForm((prev) => ({ ...prev, course_id: "" }));
    }
  };

  // Handle major selection
  const handleMajorChange = (e) => {
    const courseId = e.target.value;
    setForm((prev) => ({ ...prev, course_id: courseId }));
  };

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
    // Clear diagnostics from previous generation so OPTIMAL banner doesn't persist
    setDiagnostics({});
    setJobStatus(null);

    async function loadSavedSchedule() {
      try {
        const resp = await loadScheduleApi(courseId, semester, year, null, schoolYear);
        if (cancelled) return;

        if (resp && resp.status === "success") {
          const items = Array.isArray(resp.items) ? resp.items : [];
          setSchedule(withUiIds(items));
          setHasCheckedSavedSchedule(true);
          if (items.length > 0) {
            setSavedScheduleMessage(`Loaded saved schedule (${items.length} entries).`);
          } else {
            setSavedScheduleMessage("No saved schedule found for the selected program, year, and semester.");
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
        setSavedScheduleMessage("No saved schedule found for the selected program, year, and semester.");
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
  }, [form.course_id, form.year, form.semester, schoolYear]);



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
    // Reset progressive timetable
    setPartialItems([]);
    setCurrentPhase('');
    setTotalSubjects(0);

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
        { waitSeconds: 1, blocks_count: blocksCount, schoolYear }
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

          // Progressive reveal: keep the already-enriched partialItems from report_phase,
          // don't overwrite with raw result (which lacks subject_code, room_name etc.)
          setCurrentPhase('Complete');

          // Brief delay to show the progressive reveal animation
          setTimeout(() => {
            if (!cancelled) {
              setJobStatus("succeeded");
              setSchedule(withUiIds(scheduledItems));
              setDiagnostics(resultDiagnostics);
              setProgress(100);
              setJobId(null);
              setSubmitting(false);
            }
          }, 1500);
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
        // Update progressive timetable from partial results
        if (status.partial_items && status.partial_items.length > 0) {
          setPartialItems(status.partial_items);
        }
        if (status.current_phase) {
          setCurrentPhase(status.current_phase);
        }
        if (status.total_subjects) {
          setTotalSubjects(status.total_subjects);
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
    pollTimer = setInterval(pollStatus, 800);

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
        return saveSchedule(courseId, yearNum, semester, itemsByYear[year], schoolYear);
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

  // --- Print Logic ---
  const handlePrint = (blockFilter) => {
    // blockFilter: null/undefined = all blocks, or a specific block label like "Block A"
    if (Object.keys(expandedSchedule).length === 0) return;
    setShowPrintModal(false);

    const selectedCourse = courses.find(c => c.id === Number(form.course_id));
    const courseLabel = selectedCourse
      ? `${selectedCourse.code || ''}${selectedCourse.major ? ' - ' + selectedCourse.major : ''}`
      : '';
    const yearLabel = `Year ${form.year}`;
    const semLabel = `Semester ${form.semester}`;
    const syLabel = schoolYear || '';
    const now = new Date();
    const datePrinted = now.toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' });

    // Determine which blocks to print
    const blockKeys = blockFilter
      ? [blockFilter]
      : Object.keys(expandedSchedule).sort();

    // Helper to get subject lec/lab hours
    const getSubjectLecHours = (id) => {
      const subject = subjects.find(s => s.id === id);
      return subject?.lec_hours ?? '';
    };
    const getSubjectLabHours = (id) => {
      const subject = subjects.find(s => s.id === id);
      return subject?.lab_hours ?? '';
    };

    // Build one page per block
    let pagesHtml = '';
    blockKeys.forEach((blockLabel, pageIdx) => {
      const items = expandedSchedule[blockLabel];
      if (!items) return;

      // Calculate total units for this block
      const seenSubjects = new Set();
      let totalUnits = 0;
      let totalLec = 0;
      let totalLab = 0;
      items.forEach(slot => {
        const subjectId = slot.subject_id || slot.subjectId;
        if (!seenSubjects.has(subjectId)) {
          seenSubjects.add(subjectId);
          const subject = subjects.find(s => s.id === subjectId);
          totalUnits += Number(subject?.unit ?? 0);
          totalLec += Number(subject?.lec_hours ?? 0);
          totalLab += Number(subject?.lab_hours ?? 0);
        }
      });

      // Sort items so same-subject entries (LEC + LAB) appear side by side
      const sortedItems = [...items].sort((a, b) => {
        const codeA = getSubjectCode(a.subject_id || a.subjectId);
        const codeB = getSubjectCode(b.subject_id || b.subjectId);
        if (codeA !== codeB) return codeA.localeCompare(codeB);
        // Within same code, LEC before LAB
        const typeA = getSubjectType(a.subject_id || a.subjectId);
        const typeB = getSubjectType(b.subject_id || b.subjectId);
        return typeA === 'LEC' ? -1 : typeB === 'LEC' ? 1 : 0;
      });

      let rowsHtml = '';
      sortedItems.forEach((slot) => {
        const subjectId = slot.subject_id || slot.subjectId;
        const code = getSubjectCode(subjectId);
        const desc = getSubjectDescription(subjectId);
        const type = getSubjectType(subjectId);
        const unit = getSubjectUnit(subjectId);
        const dayLabel = slot._combinedDaysLabel || getDayName(slot.day_id || slot.dayId);
        const time = formatTimeRange(slot);
        const room = getRoomName(slot.room_id || slot.roomId);
        const instructor = getInstructorName(slot.instructor_id || slot.instructorId);
        rowsHtml += `
              <tr>
                <td class="tc">${code}</td>
                <td>${desc}</td>
                <td class="tc">${type}</td>
                <td class="tc">${unit}</td>
                <td class="tc">${dayLabel}</td>
                <td class="tc">${time}</td>
                <td class="tc">${room}</td>
                <td>${instructor}</td>
              </tr>`;
      });

      // Add totals row
      rowsHtml += `
              <tr class="totals-row">
                <td colspan="2" style="text-align:right;font-weight:700;padding-right:10px;">TOTAL</td>
                <td></td>
                <td class="tc">${totalUnits || ''}</td>
                <td colspan="4"></td>
              </tr>`;

      // Extract block letter from label (e.g. "Block A" -> "A")
      const blockLetter = blockLabel.replace('Block ', '');

      pagesHtml += `
      ${pageIdx > 0 ? '<div class="page-break"></div>' : ''}
      <div class="page">
        <!-- Watermark -->
        <div class="watermark">
          <img src="/assets/jrmsu-logo.png" alt="" />
        </div>

        <!-- Header -->
        <div class="doc-header">
          <div class="doc-code">JRMSU &ndash; REC 001</div>
          <div class="header-center">
            <img src="/assets/jrmsu-logo.png" alt="JRMSU" class="header-logo" />
            <div class="header-text">
              <div class="univ-name">JOSE RIZAL MEMORIAL STATE UNIVERSITY</div>
              <div class="univ-tagline">The Premier University in Zamboanga del Norte</div>
              <div class="univ-campus">Main Campus, Dapitan City</div>
            </div>
          </div>
        </div>

        <!-- Info Section -->
        <div class="info-section">
          <div class="info-row">
            <div class="info-line">
              <span class="info-label">College:</span>
              <span class="info-value underlined">${courseLabel}</span>
            </div>
            <div class="info-line">
              <span class="info-label">S.Y.:</span>
              <span class="info-value underlined">${syLabel}</span>
            </div>
            <div class="info-line">
              <span class="info-label">${semLabel}</span>
            </div>
          </div>
          <div class="info-row">
            <div class="info-line">
              <span class="info-label">Block:</span>
              <span class="info-value underlined">${courseLabel} ${yearLabel} - ${blockLetter}</span>
            </div>
          </div>
        </div>

        <!-- Schedule Table -->
        <table class="schedule-table">
          <thead>
            <tr>
              <th style="width:10%">CODE</th>
              <th style="width:24%">DESCRIPTIVE TITLE</th>
              <th style="width:6%">TYPE</th>
              <th style="width:6%">UNITS</th>
              <th style="width:7%">DAYS</th>
              <th style="width:14%">TIME</th>
              <th style="width:12%">ROOM</th>
              <th style="width:21%">INSTRUCTOR</th>
            </tr>
          </thead>
          <tbody>
            ${rowsHtml}
          </tbody>
        </table>

        <!-- Footer / Signatures -->
        <div class="signatures">
          <div class="sig-block">
            <div class="sig-label">Prepared By:</div>
            <div class="sig-line"></div>
          </div>
          <div class="sig-block">
            <div class="sig-label">Approved By:</div>
            <div class="sig-line"></div>
          </div>
        </div>

        <div class="print-footer">
          <div class="print-footer-inner">
            <span>Printed by: __________________</span>
            <span>Date Printed: ${datePrinted}</span>
          </div>
        </div>
      </div>`;
    });

    const printContent = `
      <!DOCTYPE html>
      <html>
      <head>
        <title>Schedule - ${courseLabel} ${yearLabel} ${semLabel}${blockFilter ? ' - ' + blockFilter : ''}</title>
        <style>
          @page {
            size: landscape;
            margin: 10mm 12mm;
          }
          * { margin: 0; padding: 0; box-sizing: border-box; }
          body {
            font-family: 'Times New Roman', 'Segoe UI', serif;
            color: #000;
            font-size: 11pt;
            -webkit-print-color-adjust: exact;
            print-color-adjust: exact;
          }
          .page {
            position: relative;
            padding: 8px 0;
          }
          .page-break {
            page-break-before: always;
          }

          /* Watermark */
          .watermark {
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            z-index: 0;
            opacity: 0.06;
            pointer-events: none;
          }
          .watermark img {
            width: 420px;
            height: 420px;
          }

          /* Header */
          .doc-header {
            position: relative;
            margin-bottom: 10px;
          }
          .doc-code {
            position: absolute;
            top: 0;
            left: 0;
            font-size: 9pt;
            font-weight: 700;
            font-style: italic;
          }
          .header-center {
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 12px;
          }
          .header-logo {
            width: 50px;
            height: 50px;
          }
          .header-text {
            text-align: center;
          }
          .univ-name {
            font-size: 13pt;
            font-weight: 700;
            letter-spacing: 0.5px;
          }
          .univ-tagline {
            font-size: 10pt;
            font-style: italic;
            color: #c00;
          }
          .univ-campus {
            font-size: 10pt;
          }

          /* Info Section */
          .info-section {
            margin: 8px 0 6px 0;
            position: relative;
            z-index: 1;
          }
          .info-row {
            display: flex;
            gap: 30px;
            margin-bottom: 4px;
            align-items: baseline;
          }
          .info-label {
            font-weight: 700;
            font-size: 10pt;
            white-space: nowrap;
          }
          .info-value {
            font-size: 10pt;
            font-weight: 600;
          }
          .underlined {
            border-bottom: 1px solid #000;
            padding-bottom: 1px;
            min-width: 200px;
            display: inline-block;
          }
          .info-line {
            display: flex;
            gap: 6px;
            align-items: baseline;
          }

          /* Table */
          .schedule-table {
            width: 100%;
            border-collapse: collapse;
            position: relative;
            z-index: 1;
            margin-bottom: 12px;
          }
          .schedule-table th {
            border: 1.5px solid #000;
            padding: 5px 4px;
            text-align: center;
            font-size: 8.5pt;
            font-weight: 700;
            background: #f5f5f5;
            text-transform: uppercase;
            letter-spacing: 0.3px;
          }
          .schedule-table td {
            border: 1px solid #000;
            padding: 4px 5px;
            font-size: 9pt;
            vertical-align: middle;
          }
          .schedule-table .tc {
            text-align: center;
          }
          .totals-row td {
            border-top: 2px solid #000;
            font-weight: 700;
            background: #f9f9f9;
          }

          /* Signatures */
          .signatures {
            display: flex;
            justify-content: space-between;
            margin: 30px 40px 0 40px;
            position: relative;
            z-index: 1;
          }
          .sig-block {
            text-align: center;
            min-width: 200px;
          }
          .sig-label {
            font-size: 10pt;
            font-weight: 700;
            margin-bottom: 30px;
          }
          .sig-line {
            border-top: 1px solid #000;
            width: 220px;
            margin: 0 auto;
          }

          /* Print Footer */
          .print-footer {
            margin-top: 25px;
            border-top: 2px solid #000;
            padding-top: 4px;
            position: relative;
            z-index: 1;
          }
          .print-footer-inner {
            display: flex;
            justify-content: center;
            gap: 60px;
            font-size: 9pt;
            border: 1px solid #000;
            padding: 5px 20px;
          }

          @media print {
            .no-print { display: none !important; }
            body { padding: 0; }
          }
        </style>
      </head>
      <body>
        ${pagesHtml}
        <script>window.onload = function() { window.print(); }</script>
      </body>
      </html>
    `;

    const printWindow = window.open('', '_blank', 'width=1100,height=700');
    if (printWindow) {
      printWindow.document.write(printContent);
      printWindow.document.close();
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
          block: item._blockLabel || item.block || null,
          merge_tag: item.merge_tag || null,
          school_year: schoolYear || null
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

      // Skip items that share the same merge_tag — merged entries are exempt
      const editMergeTag = editedItem.merge_tag || null;
      const itemMergeTag = item.merge_tag || null;
      if (editMergeTag && itemMergeTag && editMergeTag === itemMergeTag) {
        return; // Merged entries don't conflict with each other
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

    // If the string already contains AM/PM, it's already in 12-hour format — return as-is
    const trimmed = time24.trim();
    if (/am|pm/i.test(trimmed)) {
      return trimmed;
    }

    const match = trimmed.match(/^(\d{1,2}):(\d{2})/);
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

  // Fetch room utilization from backend (filtered by course when selected)
  useEffect(() => {
    const sem = Number(form.semester);
    if (!sem) return;
    const courseId = Number(form.course_id) || null;
    getRoomUtilizationByDay(sem, schoolYear, courseId)
      .then(data => setGlobalRoomUtil(Array.isArray(data) ? data : []))
      .catch(err => console.error('Failed to load room utilization', err));
  }, [form.semester, form.course_id, schoolYear]);

  // Fetch saved instructor hours for workload evidence (prior schedules)
  useEffect(() => {
    const sem = Number(form.semester);
    if (!sem || !filteredSchedule || filteredSchedule.length === 0) {
      setSavedInstructorHours({});
      return;
    }
    getInstructorHoursSummary(sem, schoolYear)
      .then(data => setSavedInstructorHours(data?.hours || {}))
      .catch(err => {
        console.error('Failed to load instructor hours summary', err);
        setSavedInstructorHours({});
      });
  }, [form.semester, schoolYear, filteredSchedule.length]);

  // Room saturation analysis — detect when rooms are fully booked
  const roomAnalysis = useMemo(() => {
    if (!filteredSchedule || filteredSchedule.length === 0) return { recommendations: [], utilization: [] };

    const recommendations = [];
    const dayLabelById = {};
    days.forEach(d => {
      if (d?.id != null) {
        dayLabelById[d.id] = d.label;
      }
    });

    const WEEKEND = ['SAT', 'SUN', 'S'];

    // Canonical day ordering for consistent display: M, T, W, TH, F, SAT, SUN
    const DAY_SORT = { M: 1, T: 2, W: 3, TH: 4, F: 5, SAT: 6, SUN: 7, S: 6, HE: 8, SHE: 9 };
    const daySort = (label) => DAY_SORT[(label || '').toUpperCase()] ?? 99;

    // Build room type lookup
    const roomTypeMap = {};     // room_id -> type (ALL rooms, including unavailable)
    const allRoomsOfType = {};  // type -> Set of room ids (only AVAILABLE rooms)
    for (const r of (rooms || [])) {
      const t = (r.type || 'LEC').toUpperCase();
      roomTypeMap[r.id] = t;
      // Only count available rooms for capacity/utilization calculations
      if (r.is_available !== false && r.is_available !== 0) {
        if (!allRoomsOfType[t]) allRoomsOfType[t] = new Set();
        allRoomsOfType[t].add(r.id);
      }
    }

    // Compute course-eligible rooms (rooms whose building belongs to the same
    // college as the selected course, or whose building is shared)
    const eligibleRoomsOfType = {};  // type -> Set of room_ids eligible for this course
    const selectedCourseId = Number(form.course_id);
    const selectedCourse = selectedCourseId
      ? (courses || []).find(c => c.id === selectedCourseId)
      : null;
    const courseCollegeId = selectedCourse?.college_id;
    if (courseCollegeId) {
      const bldgCollegeMap = {};  // building_id -> college_id
      const bldgSharedMap = {};   // building_id -> is_shared
      for (const b of (buildings || [])) {
        bldgCollegeMap[b.id] = b.college_id;
        bldgSharedMap[b.id] = b.is_shared;
      }
      for (const r of (rooms || [])) {
        if (r.is_available === false || r.is_available === 0) continue;
        const t = (r.type || 'LEC').toUpperCase();
        const bCol = bldgCollegeMap[r.building_id];
        const bShared = bldgSharedMap[r.building_id];
        // Eligible if: same college, shared building, or no building assigned
        if (bCol === courseCollegeId || bShared || !r.building_id) {
          if (!eligibleRoomsOfType[t]) eligibleRoomsOfType[t] = new Set();
          eligibleRoomsOfType[t].add(r.id);
        }
      }
    }

    // Use global utilization data from backend (slot-availability-based, all courses)
    // TIME_BLOCKS used for slot availability counting (matching api/scheduler/timeslots.py)
    const TIME_BLOCKS_RANGES = [
      [450, 510],   // 7:30-8:30
      [450, 540],   // 7:30-9:00
      [540, 600],   // 9:00-10:00
      [540, 630],   // 9:00-10:30
      [630, 690],   // 10:30-11:30
      [630, 720],   // 10:30-12:00
      [780, 840],   // 1:00-2:00
      [780, 870],   // 1:00-2:30
      [870, 930],   // 2:30-3:30
      [870, 960],   // 2:30-4:00
      [960, 1020],  // 4:00-5:00
      [960, 1050],  // 4:00-5:30
      [1050, 1140], // 5:30-7:00
    ];
    const TOTAL_SLOTS_PER_ROOM = TIME_BLOCKS_RANGES.length;

    // Parse time ranges from schedule items, group by (roomId, dayId)
    const localRoomDayRanges = {};  // `${roomId}-${dayId}` -> [{start, end}]
    const localRoomsUsed = {};      // `${type}-${dayId}` -> Set of room_ids
    for (const item of filteredSchedule) {
      const dayId = item.day_id || item.dayId;
      const roomId = item.room_id || item.roomId;
      if (!dayId || !roomId) continue;
      const rtype = roomTypeMap[roomId] || 'LEC';
      const tdKey = `${rtype}-${dayId}`;
      if (!localRoomsUsed[tdKey]) localRoomsUsed[tdKey] = new Set();
      localRoomsUsed[tdKey].add(roomId);

      const timeStr = item.time || '';
      const normalized = timeStr.replace(/[\u2013\u2014]/g, '-');
      const matches = normalized.match(/(\d{1,2}):(\d{2})/g);
      if (matches && matches.length >= 2) {
        const [h1, m1] = matches[0].split(':').map(Number);
        const [h2, m2] = matches[1].split(':').map(Number);
        const start = (h1 < 7 ? h1 + 12 : h1) * 60 + m1;
        const end = (h2 < 7 ? h2 + 12 : h2) * 60 + m2;
        const rdKey = `${roomId}-${dayId}`;
        if (!localRoomDayRanges[rdKey]) localRoomDayRanges[rdKey] = [];
        localRoomDayRanges[rdKey].push({ start, end });
      }
    }

    // Count available TIME_BLOCK slots for a room on a day
    const countAvailableSlots = (roomId, dayId) => {
      const booked = localRoomDayRanges[`${roomId}-${dayId}`] || [];
      let available = 0;
      for (const [tbS, tbE] of TIME_BLOCKS_RANGES) {
        const isFree = booked.every(b => tbE <= b.start || b.end <= tbS);
        if (isFree) available++;
      }
      return available;
    };

    // Start from global backend data if available
    let utilization;
    if (globalRoomUtil.length > 0) {
      utilization = globalRoomUtil.map(u => {
        const slotsUsed = u.slotsUsed || 0;
        const maxSlots = u.maxSlots || 0;
        const pct = maxSlots > 0 ? Math.round((slotsUsed / maxSlots) * 100) : 0;
        const localRooms = localRoomsUsed[`${u.type}-${u.dayId}`]?.size || 0;
        const roomsUsed = Math.max(u.roomsUsed || 0, localRooms);
        return {
          ...u,
          slotsUsed,
          roomsUsed,
          percentage: pct,
          bookings: slotsUsed,
          maxCapacity: maxSlots,
        };
      });
    } else {
      // No global data — build utilization from generated schedule using slot availability
      const roomTypesInUse = new Set();
      for (const item of filteredSchedule) {
        const roomId = item.room_id || item.roomId;
        if (roomId) roomTypesInUse.add(roomTypeMap[roomId] || 'LEC');
      }
      utilization = [];
      for (const rtype of roomTypesInUse) {
        const typeLabel = rtype === 'LAB' ? 'Laboratory' : 'Lecture';
        const availRoomIds = allRoomsOfType[rtype] || new Set();
        const totalRoomCount = availRoomIds.size;
        const activeSet = new Set();
        for (const item of filteredSchedule) {
          const roomId = item.room_id || item.roomId;
          if (roomId && (roomTypeMap[roomId] || 'LEC') === rtype && availRoomIds.has(roomId)) {
            activeSet.add(roomId);
          }
        }
        const activeCount = activeSet.size;
        const maxSlotsPerDay = activeCount * TOTAL_SLOTS_PER_ROOM;
        const unusedIds = [...availRoomIds].filter(id => !activeSet.has(id));
        const roomNameMap = {};
        for (const r of (rooms || [])) roomNameMap[r.id] = r.name;
        const unusedRooms = unusedIds.map(id => roomNameMap[id] || `Room ${id}`).sort();

        for (const day of days) {
          if (!day.id) continue;
          const dayLabel = day.label || '';
          const isWeekend = WEEKEND.includes(dayLabel.toUpperCase());
          const roomsUsed = localRoomsUsed[`${rtype}-${day.id}`]?.size || 0;

          // Count available slots across all active rooms for this day
          let totalAvailable = 0;
          for (const rid of activeSet) {
            totalAvailable += countAvailableSlots(rid, day.id);
          }
          const slotsUsed = maxSlotsPerDay - totalAvailable;
          const pct = maxSlotsPerDay > 0 ? Math.round((slotsUsed / maxSlotsPerDay) * 100) : 0;

          utilization.push({
            type: rtype,
            typeLabel,
            day: dayLabel,
            dayId: day.id,
            isWeekend,
            slotsUsed,
            maxSlots: maxSlotsPerDay,
            maxSlotsTotal: totalRoomCount * TOTAL_SLOTS_PER_ROOM,
            slotsAvailable: totalAvailable,
            roomsUsed,
            activeRooms: activeCount,
            totalRooms: totalRoomCount,
            unusedRooms,
            percentage: pct,
            bookings: slotsUsed,
            maxCapacity: maxSlotsPerDay,
          });
        }
      }
    }

    // 1. Detect SAT/SUN usage — sign of weekday saturation
    // Exclude NSTP and shared venue subjects (FIELD, GYM, etc.) which are
    // intentionally scheduled on weekends and should not trigger overflow warnings
    const SHARED_VENUES = ['FIELD', 'GYM', 'INNER QUAD', 'GYMNASIUM'];
    const weekendItems = filteredSchedule.filter(item => {
      const dayId = item.day_id || item.dayId;
      const label = (dayLabelById[dayId] || '').toUpperCase();
      if (!WEEKEND.includes(label)) return false;
      // Exclude NSTP subjects — look up code from subjects array since schedule items only have subject_id
      const subjectId = item.subject_id || item.subjectId;
      const subj = subjectId ? (subjects || []).find(s => s.id === subjectId) : null;
      const code = (subj?.code || item.subject_code || '').toUpperCase();
      if (code.startsWith('NSTP')) return false;
      // Exclude shared venue rooms (these are outdoor/open venues, not real rooms)
      const roomId = item.room_id || item.roomId;
      const room = roomId ? (rooms || []).find(r => r.id === roomId) : null;
      const roomName = (room?.name || item.room_name || '').toUpperCase();
      if (SHARED_VENUES.some(v => roomName.includes(v))) return false;
      return true;
    });

    if (weekendItems.length > 0) {
      // Group by room type
      const weekendTypes = {};
      for (const item of weekendItems) {
        const roomId = item.room_id || item.roomId;
        const rType = roomTypeMap[roomId] || 'LEC';
        if (!weekendTypes[rType]) weekendTypes[rType] = 0;
        weekendTypes[rType]++;
      }

      for (const [rType, count] of Object.entries(weekendTypes)) {
        const typeLabel = rType === 'LAB' ? 'Laboratory' : 'Lecture';
        const totalCount = allRoomsOfType[rType]?.size || 0;

        // Use GLOBAL weekday utilization for this room type
        const weekdayUtils = utilization.filter(u => u.type === rType && !u.isWeekend);
        const avgWeekdayPct = weekdayUtils.length > 0
          ? Math.round(weekdayUtils.reduce((a, u) => a + u.percentage, 0) / weekdayUtils.length)
          : 0;

        // Build a meaningful usage description
        let usageDescription;
        if (avgWeekdayPct >= 80) {
          usageDescription = `full (${avgWeekdayPct}% avg usage)`;
        } else if (avgWeekdayPct >= 50) {
          usageDescription = `heavily booked (${avgWeekdayPct}% avg usage)`;
        } else if (avgWeekdayPct > 0) {
          usageDescription = `at ${avgWeekdayPct}% avg usage`;
        } else {
          usageDescription = `fully unavailable on weekdays (booked by other schedules)`;
        }

        recommendations.push({
          type: 'weekend_overflow',
          severity: 'warning',
          message: `${count} class${count > 1 ? 'es' : ''} on SAT/SUN — weekday ${typeLabel.toLowerCase()} rooms ${avgWeekdayPct > 0 ? `at ${avgWeekdayPct}%` : 'unavailable'}. Add more ${rType === 'LAB' ? 'labs' : 'rooms'} (currently ${totalCount}).`,
        });
      }
    }

    // 2. Near-capacity weekdays (≥80% but not yet in "weekend_overflow")
    const nearCapDays = utilization.filter(u => !u.isWeekend && u.percentage >= 80);
    if (nearCapDays.length > 0 && weekendItems.length === 0) {
      const grouped = {};
      for (const u of nearCapDays) {
        if (!grouped[u.type]) grouped[u.type] = [];
        grouped[u.type].push(u);
      }
      for (const [rType, entries] of Object.entries(grouped)) {
        const typeLabel = rType === 'LAB' ? 'Laboratory' : 'Lecture';
        entries.sort((a, b) => daySort(a.day) - daySort(b.day));
        const daysList = entries.map(e => `${e.day} (${e.percentage}%)`).join(', ');
        const totalCount = allRoomsOfType[rType]?.size || 0;
        recommendations.push({
          type: 'near_capacity',
          severity: 'warning',
          message: `${typeLabel} rooms near capacity: ${daysList}. Only ${totalCount} ${typeLabel.toLowerCase()} room${totalCount > 1 ? 's' : ''} available — more blocks may need weekends.`,
        });
      }
    }

    // 3. All rooms of a type booked on a weekday AND at high capacity — one recommendation per type
    const fullDaysByType = {};  // type -> [day labels]
    for (const u of utilization) {
      if (u.isWeekend) continue;
      if (u.roomsUsed >= u.totalRooms && u.totalRooms > 0) {
        if (!fullDaysByType[u.type]) fullDaysByType[u.type] = { typeLabel: u.typeLabel, totalRooms: u.totalRooms, days: [], avgPct: 0, count: 0 };
        fullDaysByType[u.type].days.push(u.day);
        fullDaysByType[u.type].avgPct += u.percentage;
        fullDaysByType[u.type].count++;
      }
    }
    for (const [rType, info] of Object.entries(fullDaysByType)) {
      const avgPct = Math.round(info.avgPct / info.count);
      // Only recommend adding rooms when capacity is genuinely strained (≥80%)
      // Below 80% there are still plenty of free time slots available
      if (avgPct < 80) continue;
      info.days.sort((a, b) => daySort(a) - daySort(b));
      const daysList = info.days.join(', ');
      recommendations.push({
        type: 'room_full',
        severity: 'warning',
        roomType: rType,
        message: `All ${info.totalRooms} ${info.typeLabel.toLowerCase()} room${info.totalRooms > 1 ? 's' : ''} in use on ${daysList} (${avgPct}% avg). Add a new ${rType === 'LAB' ? 'computer lab' : 'lecture room'}.`,
      });
    }

    // 4. Fallback / suggested slots
    // Distinguish room fallbacks from instructor-constrained suggestions
    const roomFallbackCount = filteredSchedule.filter(s => s.is_soft_constraint).length;
    const suggestedCount = filteredSchedule.filter(s => s.is_recommended && !s.is_soft_constraint).length;

    if (roomFallbackCount > 0) {
      recommendations.push({
        type: 'fallback_used',
        severity: 'info',
        message: `${roomFallbackCount} slot${roomFallbackCount > 1 ? 's' : ''} used fallback rooms — preferred rooms were full.`,
      });
    }
    if (suggestedCount > 0) {
      // Identify which subjects are affected and why
      const suggestedItems = filteredSchedule.filter(s => s.is_recommended && !s.is_soft_constraint);
      const seenCodes = new Set();
      const details = [];
      const activeInstr = (instructors || []).filter(i => i.is_active !== false);
      for (const item of suggestedItems) {
        // Resolve subject code from subjects array
        const subj = (subjects || []).find(s => s.id === item.subject_id || String(s.id) === String(item.subject_id));
        const code = subj?.code || item.subject_code || item.code || '';
        if (!code || seenCodes.has(code)) continue;
        seenCodes.add(code);

        // Resolve assigned instructor name
        const iid = item.instructor_id || item.instructorId;
        const assignedInst = iid ? (instructors || []).find(i => i.id === iid || String(i.id) === String(iid)) : null;
        const instrName = assignedInst ? `${assignedInst.first_name || ''} ${assignedInst.last_name || ''}`.trim() : null;

        const normCode = code.toUpperCase().replace(/[^A-Z0-9]/g, '');
        const eligibleCount = activeInstr.filter(inst => {
          const assignable = (inst.assignable_courses || inst.assignableCourses || '');
          return assignable.split(',').some(c => c.trim().toUpperCase().replace(/[^A-Z0-9]/g, '') === normCode);
        }).length;

        if (eligibleCount <= 1 && instrName) {
          details.push(`${code} — only instructor is ${instrName} (overloaded)`);
        } else if (eligibleCount <= 1) {
          details.push(`${code} — ${eligibleCount === 0 ? 'no' : 'only 1'} eligible instructor`);
        } else {
          details.push(`${code} — all ${eligibleCount} instructors busy`);
        }
      }
      const reason = details.length > 0 ? ` — ${details.join(', ')}.` : ' — instructor overloaded or unavailable.';
      recommendations.push({
        type: 'instructor_constrained',
        severity: 'warning',
        message: `${suggestedCount} slot${suggestedCount > 1 ? 's' : ''} auto-suggested${reason}`,
      });
    }

    // 5. Unscheduled subjects due to room constraints
    const diagReasons = diagnostics?.unscheduled_reasons || diagnostics?._raw || {};
    for (const [sid, entry] of Object.entries(diagReasons)) {
      if (typeof entry === 'object' && entry.failure_reason) {
        const reason = (entry.failure_reason || '').toLowerCase();
        if (reason.includes('room') || reason.includes('no feasible')) {
          const subj = subjects.find(s => String(s.id) === String(sid));
          recommendations.push({
            type: 'unscheduled_room',
            severity: 'critical',
            message: `"${subj?.code || `Subject ${sid}`}" unscheduled — ${entry.failure_reason}.`,
          });
        }
      }
    }

    // 6. Instructor overload detection
    // Compute total weekly minutes per instructor from the schedule
    const instrMinutes = {};   // instructor_id -> total minutes
    const instrNames = {};     // instructor_id -> name
    const instrSubjects = {};  // instructor_id -> Set of subject codes
    for (const item of filteredSchedule) {
      const iid = item.instructor_id || item.instructorId;
      if (!iid || !item.start_min || !item.end_min) continue;
      const mins = Math.max(0, item.end_min - item.start_min);
      instrMinutes[iid] = (instrMinutes[iid] || 0) + mins;

      // Resolve instructor name from the instructors array
      if (!instrNames[iid]) {
        const inst = (instructors || []).find(i => i.id === iid || String(i.id) === String(iid));
        instrNames[iid] = inst
          ? `${inst.first_name || ''} ${inst.last_name || ''}`.trim() || `Instructor #${iid}`
          : (item.instructor_name || item.instructorName || `Instructor #${iid}`);
      }

      // Resolve subject code from the subjects array
      if (!instrSubjects[iid]) instrSubjects[iid] = new Set();
      const subj = (subjects || []).find(s => s.id === item.subject_id || String(s.id) === String(item.subject_id));
      const code = subj?.code || item.subject_code || item.code || '';
      if (code) instrSubjects[iid].add(code);
    }

    // Find overloaded instructors (>24h = 1440min per week)
    const OVERLOAD_THRESHOLD_MIN = 1440; // 24 hours
    const activeInstructors = (instructors || []).filter(i => i.is_active !== false);
    const overloadedIds = new Set(
      Object.entries(instrMinutes)
        .filter(([, m]) => m > OVERLOAD_THRESHOLD_MIN)
        .map(([id]) => id)
    );

    for (const [iid, totalMin] of Object.entries(instrMinutes)) {
      if (totalMin <= OVERLOAD_THRESHOLD_MIN) continue;
      const hours = Math.round((totalMin / 60) * 10) / 10;
      const name = instrNames[iid];
      const subjectCodes = [...(instrSubjects[iid] || [])];

      // Check which subjects have limited instructor options
      const soloSubjects = [];       // only 1 eligible instructor
      const allOverloadedSubjects = []; // 2+ eligible but ALL are overloaded
      for (const code of subjectCodes) {
        const normCode = code.toUpperCase().replace(/[^A-Z0-9]/g, '');
        const eligible = activeInstructors.filter(inst => {
          const assignable = (inst.assignable_courses || inst.assignableCourses || '');
          return assignable.split(',').some(c => c.trim().toUpperCase().replace(/[^A-Z0-9]/g, '') === normCode);
        });
        if (eligible.length <= 1) {
          soloSubjects.push(code);
        } else if (eligible.length >= 2) {
          // Check if ALL eligible instructors are overloaded
          const allOverloaded = eligible.every(inst => overloadedIds.has(String(inst.id)));
          if (allOverloaded) {
            allOverloadedSubjects.push(`${code} (all ${eligible.length} eligible overloaded)`);
          }
        }
      }

      // Build context note
      const notes = [];
      if (soloSubjects.length > 0) notes.push(`Solo instructor for: ${soloSubjects.join(', ')}`);
      if (allOverloadedSubjects.length > 0) notes.push(allOverloadedSubjects.join(', '));
      const contextNote = notes.length > 0 ? ` ${notes.join('. ')}.` : '';

      recommendations.push({
        type: 'instructor_overload',
        severity: 'warning',
        message: `${name} is overloaded at ${hours}h/week (limit: 24h).${contextNote}`,
      });
    }

    // Deduplicate by message
    const seen = new Set();
    const deduped = recommendations.filter(r => {
      if (seen.has(r.message)) return false;
      seen.add(r.message);
      return true;
    });

    // Sort: critical first, then warning, then info
    const severityOrder = { critical: 0, warning: 1, info: 2 };
    deduped.sort((a, b) => (severityOrder[a.severity] ?? 3) - (severityOrder[b.severity] ?? 3));

    // Sort utilization entries by canonical day order (M, T, W, TH, F, SAT, SUN)
    utilization.sort((a, b) => daySort(a.day) - daySort(b.day));

    // Build instructor workload evidence data
    const instructorWorkload = Object.entries(instrMinutes)
      .map(([iid, totalMin]) => {
        const hours = Math.round((totalMin / 60) * 10) / 10;
        const name = instrNames[iid] || `Instructor #${iid}`;
        const subjectCodes = [...(instrSubjects[iid] || [])];

        // Count eligible instructors per subject
        const subjectsDetail = subjectCodes.map(code => {
          const normCode = code.toUpperCase().replace(/[^A-Z0-9]/g, '');
          const eligibleCount = activeInstructors.filter(inst => {
            const assignable = (inst.assignable_courses || inst.assignableCourses || '');
            return assignable.split(',').some(c => c.trim().toUpperCase().replace(/[^A-Z0-9]/g, '') === normCode);
          }).length;
          return { code, eligibleCount };
        });

        return {
          id: iid,
          name,
          hours,
          totalMin,
          savedMin: savedInstructorHours[iid] || 0,
          savedHours: Math.round(((savedInstructorHours[iid] || 0) / 60) * 10) / 10,
          totalHours: Math.round(((totalMin + (savedInstructorHours[iid] || 0)) / 60) * 10) / 10,
          subjectCount: subjectCodes.length,
          subjects: subjectsDetail,
          isOverloaded: totalMin > OVERLOAD_THRESHOLD_MIN,
        };
      })
      .sort((a, b) => b.totalHours - a.totalHours); // highest total hours first

    return { recommendations: deduped, utilization, eligibleRoomsOfType, instructorWorkload };
  }, [filteredSchedule, rooms, days, diagnostics, subjects, globalRoomUtil, buildings, courses, form.course_id, instructors, savedInstructorHours]);

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
          // More aggressive normalization: collapse common abbreviation variants
          // e.g. "Prof.E 7" (PROFE7) and "ProE 7" (PROE7) both mean Professional Elective 7
          const deepNormalize = (str) => normalizeString(str)
            .replace(/PROFE(?=\d)/g, 'PROE')        // Prof.E N → ProE N
            .replace(/CSPROFELECT/g, 'CSPROE');      // CS Prof Elect → CS ProE
          const cleanSubjectCode = normalizeString(subjectCode);
          const deepCleanSubjectCode = deepNormalize(subjectCode);

          isSpecialized = assignable.split(',').some(c => {
            const nc = normalizeString(c);
            if (nc === cleanSubjectCode) return true;
            // Fallback: aggressive normalization for Prof.E/ProE variants
            return deepNormalize(c) === deepCleanSubjectCode;
          });
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
        <td className="px-4 py-2 text-sm text-gray-700">
          {subjectCode}
          {slot.merge_tag && (
            <span className="ml-1 text-[10px] font-semibold text-purple-700 bg-purple-100 border border-purple-200 px-1.5 py-0.5 rounded-full">{slot.merge_tag}</span>
          )}
        </td>
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
                  const diagDetail = typeof diagEntry === 'object' ? diagEntry.detail || diagEntry.reason_text || '' : '';
                  const diagSuggestion = typeof diagEntry === 'object' ? diagEntry.suggestion || '' : '';
                  const diagSubjectCode = typeof diagEntry === 'object' ? diagEntry.subject_code || '' : '';
                  const diagSubjectType = typeof diagEntry === 'object' ? diagEntry.subject_type || '' : '';
                  setResolvingItem({
                    ...slot,
                    failureReason,
                    recommendations: recs,
                    diagDetail,
                    diagSuggestion,
                    diagSubjectCode: diagSubjectCode || subjectCode,
                    diagSubjectType: diagSubjectType || subjectType,
                  });
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
          ) : isUnscheduled ? (
            <span className="inline-block px-2 py-0.5 rounded-full text-xs font-semibold bg-gray-100 text-gray-500 border border-gray-200">
              Unscheduled
            </span>
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
              openMergeModal(subjectId);
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
    <div className="p-2 space-y-4">
      <div className="flex items-center justify-between mb-2">
        <h1 className="text-2xl font-semibold">Schedule</h1>
      </div>

      {/* ──── ACCORDION: Scheduler ──── */}
      <div id="section-scheduler" className="bg-white/60 backdrop-blur rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
        <button
          onClick={() => setOpenSection(prev => prev === 'scheduler' ? null : 'scheduler')}
          className="w-full flex items-center justify-between px-6 py-4 hover:bg-slate-50/80 transition-colors"
        >
          <div className="text-left">
            <h2 className="text-lg font-bold text-slate-800">📅 Scheduler</h2>
            <p className="text-sm text-slate-500">Generate and manage class schedules by program, year, and semester.</p>
          </div>
          <svg className={`w-5 h-5 text-slate-400 transition-transform duration-200 ${openSection === 'scheduler' ? 'rotate-180' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" /></svg>
        </button>
        <div className={`transition-all duration-300 ease-in-out ${openSection === 'scheduler' ? 'max-h-[100000px] opacity-100' : 'max-h-0 opacity-0 overflow-hidden'}`}>
          <div className="px-6 pb-6 pt-2">
            <div className="flex items-center justify-end mb-4">
              <SchoolYearSelector onChange={setSchoolYear} />
            </div>

            <form onSubmit={handleSubmit} className="grid gap-4 sm:grid-cols-2">
              <label className="flex flex-col gap-1 text-sm">
                Select Program
                <select
                  name="program_code"
                  value={selectedProgramCode}
                  onChange={handleProgramCodeChange}
                  className="px-3 py-2 border rounded"
                  required
                >
                  <option value="">Choose a program</option>
                  {programOptions}
                </select>
              </label>

              {hasMajors && (
                <label className="flex flex-col gap-1 text-sm">
                  Select Major
                  <select
                    name="course_id"
                    value={form.course_id}
                    onChange={handleMajorChange}
                    className="px-3 py-2 border rounded"
                    required
                  >
                    <option value="">Choose a major</option>
                    {majorOptions}
                  </select>
                </label>
              )}

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

            {/* Progressive Skeleton Timetable during scheduling */}
            {(isSubmitting ||
              ["initializing", "queued", "running"].includes(jobStatus)) && (
                <div className="mt-6">
                  <ScheduleTimetable
                    partialItems={partialItems}
                    totalSubjects={totalSubjects}
                    currentPhase={currentPhase}
                    statusMessage={statusMessage || (
                      jobStatus === "running" ? "Scheduling subjects..." :
                        jobStatus === "queued" ? "Preparing scheduler..." :
                          "Initializing..."
                    )}
                    isComplete={false}
                    blocksCount={Number(form.blocks_count) || 1}
                    subjectCount={subjects.filter(s =>
                      String(s.course_id) === String(form.course_id) &&
                      String(s.semester) === String(form.semester) &&
                      (!form.year || form.year.toString().split(',').map(Number).includes(Number(s.year_level)))
                    ).length}
                  />
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

            {/* Room Warnings Indicator Button */}
            {roomAnalysis.recommendations.length > 0 && Object.keys(expandedSchedule).length > 0 && (
              <div className="mt-4">
                <button
                  type="button"
                  onClick={() => setShowWarningsModal(true)}
                  className="group flex items-center gap-2.5 px-4 py-2.5 rounded-xl border border-amber-200 bg-gradient-to-r from-amber-50 to-orange-50 hover:from-amber-100 hover:to-orange-100 shadow-sm hover:shadow-md transition-all duration-300 cursor-pointer"
                >
                  <span className="relative flex h-6 w-6 items-center justify-center">
                    <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-amber-400 opacity-30"></span>
                    <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 text-amber-500 relative" viewBox="0 0 20 20" fill="currentColor">
                      <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                    </svg>
                  </span>
                  <span className="text-sm font-semibold text-amber-800">
                    {roomAnalysis.recommendations.length} Scheduling {roomAnalysis.recommendations.length === 1 ? 'Warning' : 'Warnings'}
                  </span>
                  <span className="text-xs text-amber-600 group-hover:text-amber-700 transition-colors">— Click to view details</span>
                  <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 text-amber-400 group-hover:translate-x-0.5 transition-transform" viewBox="0 0 20 20" fill="currentColor">
                    <path fillRule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z" clipRule="evenodd" />
                  </svg>
                </button>
              </div>
            )}

            {/* Warnings Modal */}
            {showWarningsModal && createPortal(
              <div
                style={{ position: 'fixed', inset: 0, zIndex: 9999, display: 'flex', alignItems: 'center', justifyContent: 'center' }}
                onClick={(e) => { if (e.target === e.currentTarget) setShowWarningsModal(false); }}
              >
                {/* Backdrop */}
                <div style={{ position: 'absolute', inset: 0, backgroundColor: 'rgba(0,0,0,0.5)', backdropFilter: 'blur(4px)' }} />
                {/* Modal Container */}
                <div
                  style={{
                    position: 'relative',
                    width: '100%',
                    maxWidth: '720px',
                    maxHeight: '85vh',
                    margin: '1rem',
                    borderRadius: '1rem',
                    overflow: 'hidden',
                    display: 'flex',
                    flexDirection: 'column',
                    boxShadow: '0 25px 50px -12px rgba(0,0,0,0.25)',
                    background: 'linear-gradient(135deg, #fffbeb 0%, #fff7ed 50%, #ffffff 100%)',
                    border: '1px solid #fde68a',
                    animation: 'warningsModalSlideIn 0.3s ease-out',
                  }}
                >
                  {/* Header */}
                  <div style={{
                    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                    padding: '1.25rem 1.5rem',
                    borderBottom: '1px solid #fde68a',
                    background: 'linear-gradient(to right, rgba(251,191,36,0.1), rgba(249,115,22,0.05))',
                  }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                      <div style={{
                        width: '40px', height: '40px', borderRadius: '12px',
                        background: 'linear-gradient(135deg, #f59e0b, #d97706)',
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        boxShadow: '0 4px 6px -1px rgba(245,158,11,0.3)',
                      }}>
                        <svg xmlns="http://www.w3.org/2000/svg" style={{ width: '22px', height: '22px', color: 'white' }} viewBox="0 0 20 20" fill="currentColor">
                          <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                        </svg>
                      </div>
                      <div>
                        <h3 style={{ fontSize: '1.1rem', fontWeight: 700, color: '#92400e', margin: 0 }}>Scheduling Warnings</h3>
                        <p style={{ fontSize: '0.8rem', color: '#b45309', margin: '2px 0 0 0' }}>
                          {roomAnalysis.recommendations.length} issue{roomAnalysis.recommendations.length !== 1 ? 's' : ''} detected — review before finalizing
                        </p>
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={() => setShowWarningsModal(false)}
                      style={{
                        width: '36px', height: '36px', borderRadius: '10px', border: '1px solid #e5e7eb',
                        background: 'white', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center',
                        transition: 'all 0.2s',
                      }}
                      onMouseEnter={(e) => { e.currentTarget.style.background = '#fef3c7'; e.currentTarget.style.borderColor = '#fbbf24'; }}
                      onMouseLeave={(e) => { e.currentTarget.style.background = 'white'; e.currentTarget.style.borderColor = '#e5e7eb'; }}
                    >
                      <svg xmlns="http://www.w3.org/2000/svg" style={{ width: '18px', height: '18px', color: '#6b7280' }} viewBox="0 0 20 20" fill="currentColor">
                        <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
                      </svg>
                    </button>
                  </div>

                  {/* Scrollable Body */}
                  <div style={{ overflowY: 'auto', padding: '1.25rem 1.5rem', flex: 1 }}>
                    {/* Warnings List */}
                    <div style={{ marginBottom: '1.5rem' }}>
                      <div style={{ fontSize: '0.7rem', fontWeight: 700, color: '#9ca3af', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '0.75rem' }}>⚠ Active Warnings</div>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                        {roomAnalysis.recommendations.map((rec, i) => {
                          const styleMap = {
                            critical: { bg: '#fef2f2', border: '#fecaca', text: '#991b1b', iconColor: '#ef4444', iconPath: 'M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z' },
                            warning: { bg: '#fffbeb', border: '#fde68a', text: '#92400e', iconColor: '#f59e0b', iconPath: 'M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z' },
                            info: { bg: '#eff6ff', border: '#bfdbfe', text: '#1e40af', iconColor: '#3b82f6', iconPath: 'M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z' },
                          };
                          const s = styleMap[rec.severity] || styleMap.info;
                          const badgeMap = {
                            weekend_overflow: { label: 'Weekend Overflow', bg: '#fdba74', text: '#9a3412' },
                            near_capacity: { label: 'Near Capacity', bg: '#fde68a', text: '#92400e' },
                            room_full: { label: 'Room Capacity', bg: '#fde68a', text: '#92400e' },
                            unscheduled_room: { label: 'No Room Available', bg: '#fecaca', text: '#991b1b' },
                            fallback_used: { label: 'Fallback Used', bg: '#bfdbfe', text: '#1e40af' },
                            instructor_overload: { label: 'Instructor Overload', bg: '#e9d5ff', text: '#6b21a8' },
                            instructor_constrained: { label: 'Instructor Constrained', bg: '#fce7f3', text: '#9d174d' },
                          };
                          const badge = badgeMap[rec.type];
                          return (
                            <div key={i} style={{
                              display: 'flex', alignItems: 'flex-start', gap: '0.75rem',
                              padding: '0.875rem 1rem', borderRadius: '0.75rem',
                              border: `1px solid ${s.border}`, backgroundColor: s.bg,
                            }}>
                              <svg xmlns="http://www.w3.org/2000/svg" style={{ width: '20px', height: '20px', color: s.iconColor, flexShrink: 0, marginTop: '1px' }} viewBox="0 0 20 20" fill="currentColor">
                                <path fillRule="evenodd" d={s.iconPath} clipRule="evenodd" />
                              </svg>
                              <div style={{ fontSize: '0.875rem', fontWeight: 500, color: s.text, lineHeight: 1.5 }}>
                                {badge && (
                                  <span style={{
                                    display: 'inline-block', padding: '1px 6px', fontSize: '0.625rem',
                                    fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em',
                                    borderRadius: '4px', marginRight: '0.5rem', verticalAlign: 'middle',
                                    backgroundColor: badge.bg, color: badge.text,
                                  }}>
                                    {badge.label}
                                  </span>
                                )}
                                {rec.message}
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </div>

                    {/* Room Utilization Evidence */}
                    {roomAnalysis.utilization.some(u => (u.slotsUsed || u.bookings) > 0) && (
                      <div>
                        <div
                          onClick={() => setRoomUtilCollapsed(p => !p)}
                          style={{
                            fontSize: '0.7rem', fontWeight: 700, color: '#9ca3af', textTransform: 'uppercase',
                            letterSpacing: '0.05em', marginBottom: roomUtilCollapsed ? 0 : '0.75rem',
                            display: 'flex', alignItems: 'center', gap: '0.5rem',
                            cursor: 'pointer', userSelect: 'none',
                          }}
                        >
                          <svg xmlns="http://www.w3.org/2000/svg" style={{ width: '14px', height: '14px', transition: 'transform 0.2s', transform: roomUtilCollapsed ? 'rotate(-90deg)' : 'rotate(0deg)' }} viewBox="0 0 20 20" fill="currentColor">
                            <path fillRule="evenodd" d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" clipRule="evenodd" />
                          </svg>
                          📊 Room Utilization Evidence
                        </div>
                        {!roomUtilCollapsed && <div style={{
                          borderRadius: '0.75rem', border: '1px solid #e5e7eb',
                          backgroundColor: 'white', padding: '1rem 1.25rem',
                        }}>
                          {Object.entries(
                            roomAnalysis.utilization
                              .filter(u => (u.slotsUsed || u.bookings) > 0 || !u.isWeekend)
                              .reduce((acc, u) => {
                                if (!acc[u.type]) acc[u.type] = {
                                  label: u.typeLabel,
                                  totalRooms: u.totalRooms,
                                  activeRooms: u.activeRooms ?? u.totalRooms,
                                  unusedRooms: u.unusedRooms || [],
                                  days: []
                                };
                                acc[u.type].days.push(u);
                                return acc;
                              }, {})
                          ).map(([type, data]) => {
                            const selectedCourse = courses?.find(c => c.id === Number(form.course_id));
                            const courseLabel = selectedCourse?.code || null;
                            return (
                              <div key={type} style={{ marginBottom: '1.25rem' }}>
                                <div style={{
                                  fontSize: '0.75rem', fontWeight: 700, color: '#6b7280', textTransform: 'uppercase',
                                  letterSpacing: '0.05em', marginBottom: '0.5rem',
                                  display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '0.5rem',
                                }}>
                                  {type === 'LAB' ? '🖥' : '📖'} {data.label} Rooms
                                  <span style={{ fontSize: '0.625rem', fontWeight: 400, textTransform: 'none', color: '#9ca3af' }}>
                                    ({data.activeRooms}/{data.totalRooms} active{courseLabel ? ` for ${courseLabel}` : ''})
                                  </span>
                                </div>
                                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(120px, 1fr))', gap: '0.5rem' }}>
                                  {data.days.filter(d => !d.isWeekend || (d.slotsUsed || d.bookings) > 0).map((d) => {
                                    const barColor = d.isWeekend
                                      ? '#fb923c'
                                      : d.percentage >= 80
                                        ? '#f87171'
                                        : d.percentage >= 50
                                          ? '#fbbf24'
                                          : '#34d399';
                                    const cardBg = d.isWeekend ? '#fff7ed' : d.percentage >= 100 ? '#fef2f2' : '#f9fafb';
                                    const cardBorder = d.isWeekend ? '#fed7aa' : d.percentage >= 100 ? '#fecaca' : '#e5e7eb';
                                    const dayColor = d.isWeekend ? '#c2410c' : d.percentage >= 100 ? '#b91c1c' : '#374151';
                                    const free = d.slotsAvailable ?? Math.max(0, (d.maxSlots || 0) - (d.slotsUsed || 0));
                                    return (
                                      <div key={`${type}-${d.dayId}`} style={{
                                        borderRadius: '0.5rem', border: `1px solid ${cardBorder}`,
                                        padding: '0.5rem 0.625rem', backgroundColor: cardBg,
                                      }}>
                                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '4px' }}>
                                          <span style={{ fontSize: '0.75rem', fontWeight: 700, color: dayColor }}>
                                            {d.day}{d.isWeekend ? ' ⚠' : ''}
                                          </span>
                                          <span style={{ fontSize: '0.625rem', color: '#6b7280' }}>
                                            {d.slotsUsed ?? d.bookings ?? 0}/{d.maxSlots ?? d.maxCapacity ?? 0}
                                          </span>
                                        </div>
                                        <div style={{ height: '6px', backgroundColor: '#e5e7eb', borderRadius: '9999px', overflow: 'hidden' }}>
                                          <div style={{
                                            height: '100%', borderRadius: '9999px',
                                            backgroundColor: barColor,
                                            width: `${Math.min(100, d.percentage)}%`,
                                            transition: 'width 0.5s ease',
                                          }} />
                                        </div>
                                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: '2px' }}>
                                          <span style={{
                                            fontSize: '0.625rem', fontWeight: 600,
                                            color: free <= 0 ? '#dc2626' : '#059669',
                                          }}>
                                            {free <= 0 ? 'FULL' : `${free} free`}
                                          </span>
                                          <span style={{ fontSize: '0.625rem', color: '#6b7280' }}>{d.percentage}%</span>
                                        </div>
                                      </div>
                                    );
                                  })}
                                </div>
                                {data.unusedRooms.length > 0 && (
                                  <div style={{
                                    marginTop: '0.5rem', fontSize: '0.6875rem', color: '#9ca3af',
                                    fontStyle: 'italic', display: 'flex', alignItems: 'center', gap: '0.25rem',
                                  }}>
                                    <svg xmlns="http://www.w3.org/2000/svg" style={{ width: '12px', height: '12px' }} viewBox="0 0 20 20" fill="currentColor">
                                      <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
                                    </svg>
                                    {data.unusedRooms.length} unused: {data.unusedRooms.join(', ')}
                                  </div>
                                )}
                              </div>
                            );
                          })}
                        </div>}
                      </div>
                    )}

                    {/* Instructor Workload Evidence */}
                    {roomAnalysis.instructorWorkload && roomAnalysis.instructorWorkload.length > 0 && (
                      <div style={{ marginTop: '1.5rem' }}>
                        <div
                          onClick={() => setInstrWorkloadCollapsed(p => !p)}
                          style={{
                            fontSize: '0.7rem', fontWeight: 700, color: '#9ca3af', textTransform: 'uppercase',
                            letterSpacing: '0.05em', marginBottom: instrWorkloadCollapsed ? 0 : '0.75rem',
                            display: 'flex', alignItems: 'center', gap: '0.5rem',
                            cursor: 'pointer', userSelect: 'none',
                          }}
                        >
                          <svg xmlns="http://www.w3.org/2000/svg" style={{ width: '14px', height: '14px', transition: 'transform 0.2s', transform: instrWorkloadCollapsed ? 'rotate(-90deg)' : 'rotate(0deg)' }} viewBox="0 0 20 20" fill="currentColor">
                            <path fillRule="evenodd" d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" clipRule="evenodd" />
                          </svg>
                          👨‍🏫 Instructor Workload Evidence
                          <span style={{ fontSize: '0.625rem', fontWeight: 400, textTransform: 'none', color: '#9ca3af' }}>
                            ({roomAnalysis.instructorWorkload.length} instructor{roomAnalysis.instructorWorkload.length !== 1 ? 's' : ''} — hours in this schedule only)
                          </span>
                        </div>
                        {!instrWorkloadCollapsed && <div style={{
                          borderRadius: '0.75rem', border: '1px solid #e5e7eb',
                          backgroundColor: 'white', padding: '1rem 1.25rem',
                        }}>
                          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: '0.5rem' }}>
                            {roomAnalysis.instructorWorkload.map((instr) => {
                              // Color by total load (saved + this schedule): >24h red, >18h amber, else neutral
                              const isOver = instr.totalHours >= 24;
                              const isWarn = instr.totalHours >= 18;
                              const barColorHere = '#60a5fa';
                              const barColorSaved = '#94a3b8';
                              const cardBg = isOver ? '#fef2f2' : isWarn ? '#fffbeb' : '#f9fafb';
                              const cardBorder = isOver ? '#fecaca' : isWarn ? '#fde68a' : '#e5e7eb';
                              const nameColor = isOver ? '#b91c1c' : '#374151';
                              const hasSolo = instr.subjects.some(s => s.eligibleCount <= 1);

                              // Stacked bar: saved + here, relative to 24h
                              const savedPct = Math.min(100, Math.round((instr.savedHours / 24) * 100));
                              const herePct = Math.min(100 - savedPct, Math.round((instr.hours / 24) * 100));

                              return (
                                <div key={instr.id} style={{
                                  borderRadius: '0.5rem', border: `1px solid ${cardBorder}`,
                                  padding: '0.625rem 0.75rem', backgroundColor: cardBg,
                                }}>
                                  {/* Name & total hours */}
                                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '4px' }}>
                                    <span style={{
                                      fontSize: '0.75rem', fontWeight: 700, color: nameColor,
                                      overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '120px',
                                    }} title={instr.name}>
                                      {instr.name}
                                    </span>
                                    <span style={{ fontSize: '0.625rem', fontWeight: 600, color: isOver ? '#dc2626' : '#6b7280' }}>
                                      {instr.totalHours}h / 24h
                                    </span>
                                  </div>
                                  {/* Stacked progress bar */}
                                  <div style={{ height: '6px', backgroundColor: '#e5e7eb', borderRadius: '9999px', overflow: 'hidden', display: 'flex' }}>
                                    {savedPct > 0 && <div style={{
                                      height: '100%',
                                      backgroundColor: barColorSaved,
                                      width: `${savedPct}%`,
                                      transition: 'width 0.5s ease',
                                    }} />}
                                    <div style={{
                                      height: '100%',
                                      backgroundColor: barColorHere,
                                      width: `${herePct}%`,
                                      transition: 'width 0.5s ease',
                                    }} />
                                  </div>
                                  {/* Breakdown label */}
                                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.375rem', marginTop: '3px', fontSize: '0.5625rem', color: '#9ca3af' }}>
                                    {instr.savedHours > 0 && (
                                      <>
                                        <span style={{ display: 'inline-flex', alignItems: 'center', gap: '2px' }}>
                                          <span style={{ width: '6px', height: '6px', borderRadius: '50%', backgroundColor: barColorSaved, display: 'inline-block' }} />
                                          {instr.savedHours}h other
                                        </span>
                                        <span>+</span>
                                      </>
                                    )}
                                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: '2px' }}>
                                      <span style={{ width: '6px', height: '6px', borderRadius: '50%', backgroundColor: barColorHere, display: 'inline-block' }} />
                                      {instr.hours}h here
                                    </span>
                                  </div>
                                  {/* Subject count & solo flag */}
                                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: '4px' }}>
                                    <span style={{ fontSize: '0.625rem', color: '#6b7280' }}>
                                      {instr.subjects.map(s => s.code).join(', ') || 'No subjects'}
                                    </span>
                                    {hasSolo && (
                                      <span style={{
                                        fontSize: '0.5625rem', fontWeight: 700, color: '#9333ea',
                                        backgroundColor: '#f3e8ff', padding: '1px 5px', borderRadius: '3px',
                                      }} title={`Solo for: ${instr.subjects.filter(s => s.eligibleCount <= 1).map(s => s.code).join(', ')}`}>
                                        SOLO
                                      </span>
                                    )}
                                  </div>
                                  {/* Solo subjects detail */}
                                  {hasSolo && (
                                    <div style={{ marginTop: '3px', fontSize: '0.5625rem', color: '#7c3aed', lineHeight: 1.4 }}>
                                      Only instructor for: {instr.subjects.filter(s => s.eligibleCount <= 1).map(s => s.code).join(', ')}
                                    </div>
                                  )}
                                </div>
                              );
                            })}
                          </div>
                        </div>}
                      </div>
                    )}
                  </div>

                  {/* Footer */}
                  <div style={{
                    padding: '0.875rem 1.5rem',
                    borderTop: '1px solid #f3f4f6',
                    backgroundColor: 'rgba(255,255,255,0.8)',
                    display: 'flex', justifyContent: 'flex-end',
                  }}>
                    <button
                      type="button"
                      onClick={() => setShowWarningsModal(false)}
                      style={{
                        padding: '0.5rem 1.5rem', borderRadius: '0.5rem',
                        border: '1px solid #d1d5db', backgroundColor: 'white',
                        fontSize: '0.875rem', fontWeight: 600, color: '#374151',
                        cursor: 'pointer', transition: 'all 0.2s',
                      }}
                      onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = '#f9fafb'; e.currentTarget.style.borderColor = '#9ca3af'; }}
                      onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = 'white'; e.currentTarget.style.borderColor = '#d1d5db'; }}
                    >
                      Close
                    </button>
                  </div>
                </div>

                {/* Keyframe animation */}
                <style>{`
            @keyframes warningsModalSlideIn {
              from { opacity: 0; transform: translateY(20px) scale(0.98); }
              to { opacity: 1; transform: translateY(0) scale(1); }
            }
          `}</style>
              </div>,
              document.body
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
                    <div className="relative">
                      <button
                        type="button"
                        onClick={() => setShowPrintModal(prev => !prev)}
                        className="px-4 py-2 text-gray-700 bg-white border border-gray-300 rounded hover:bg-gray-50 flex items-center gap-1.5"
                        title="Print Schedule"
                      >
                        <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
                          <path fillRule="evenodd" d="M5 4v3H4a2 2 0 00-2 2v3a2 2 0 002 2h1v2a2 2 0 002 2h6a2 2 0 002-2v-2h1a2 2 0 002-2V9a2 2 0 00-2-2h-1V4a2 2 0 00-2-2H7a2 2 0 00-2 2zm8 0H7v3h6V4zm0 8H7v4h6v-4z" clipRule="evenodd" />
                        </svg>
                        Print
                        <svg xmlns="http://www.w3.org/2000/svg" className={`h-3.5 w-3.5 ml-0.5 transition-transform ${showPrintModal ? 'rotate-180' : ''}`} viewBox="0 0 20 20" fill="currentColor">
                          <path fillRule="evenodd" d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" clipRule="evenodd" />
                        </svg>
                      </button>

                      {/* Print block selection dropdown */}
                      {showPrintModal && (
                        <>
                          {/* Invisible backdrop to close on outside click */}
                          <div
                            className="fixed inset-0 z-40"
                            onClick={() => setShowPrintModal(false)}
                          />
                          <div className="absolute right-0 top-full mt-1 z-50 bg-white border border-gray-200 rounded-lg shadow-lg py-1 min-w-[180px] animate-in fade-in slide-in-from-top-1">
                            <div className="px-3 py-1.5 text-xs font-semibold text-gray-400 uppercase tracking-wider">Select Block</div>
                            {Object.keys(expandedSchedule).sort().map(blockLabel => (
                              <button
                                key={blockLabel}
                                onClick={() => handlePrint(blockLabel)}
                                className="w-full text-left px-3 py-2 text-sm text-gray-700 hover:bg-blue-50 hover:text-blue-700 flex items-center gap-2 transition-colors"
                              >
                                <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 text-gray-400" viewBox="0 0 20 20" fill="currentColor">
                                  <path d="M9 2a1 1 0 000 2h2a1 1 0 100-2H9z" />
                                  <path fillRule="evenodd" d="M4 5a2 2 0 012-2 3 3 0 003 3h2a3 3 0 003-3 2 2 0 012 2v11a2 2 0 01-2 2H6a2 2 0 01-2-2V5zm3 4a1 1 0 000 2h.01a1 1 0 100-2H7zm3 0a1 1 0 000 2h3a1 1 0 100-2h-3zm-3 4a1 1 0 100 2h.01a1 1 0 100-2H7zm3 0a1 1 0 100 2h3a1 1 0 100-2h-3z" clipRule="evenodd" />
                                </svg>
                                {blockLabel}
                              </button>
                            ))}
                            {Object.keys(expandedSchedule).length > 1 && (
                              <>
                                <div className="border-t border-gray-100 my-1" />
                                <button
                                  onClick={() => handlePrint(null)}
                                  className="w-full text-left px-3 py-2 text-sm font-medium text-blue-600 hover:bg-blue-50 flex items-center gap-2 transition-colors"
                                >
                                  <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 text-blue-500" viewBox="0 0 20 20" fill="currentColor">
                                    <path d="M5 4v3H4a2 2 0 00-2 2v3a2 2 0 002 2h1v2a2 2 0 002 2h6a2 2 0 002-2v-2h1a2 2 0 002-2V9a2 2 0 00-2-2h-1V4a2 2 0 00-2-2H7a2 2 0 00-2 2zm8 0H7v3h6V4zm0 8H7v4h6v-4z" clipRule="evenodd" />
                                  </svg>
                                  All Blocks
                                </button>
                              </>
                            )}
                          </div>
                        </>
                      )}
                    </div>
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
                          {(() => {
                            const blockItems = expandedSchedule[blockLabel];
                            const total = plannedSubjectCount || blockItems.length;
                            const actuallyScheduled = blockItems.filter(s => s.day_id && s.time && s.room_id).length;
                            // Deduplicate by subject_id to count unique subjects (not per-day rows)
                            const scheduledSubjects = new Set(blockItems.filter(s => s.day_id && s.time && s.room_id).map(s => s.subject_id));
                            const totalSubjects = new Set(blockItems.map(s => s.subject_id));
                            return `scheduled ${scheduledSubjects.size}/${totalSubjects.size}`;
                          })()}
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

              const mergeCourseName = (cid) => {
                const c = courses.find(co => co.id === cid);
                return c ? (c.code || c.name || `Course ${c.id}`) : '';
              };

              // Target options: filter by search, course, same semester, and scheduled-only
              const currentSemester = Number(form.semester);
              const tSearch = (mergeModal.targetSearch || '').toLowerCase();
              const targetOptions = subjects.filter(s => {
                if (s.id === sourceSubject.id) return false;
                // Only subjects that have schedule entries
                if (mergeModal.scheduledIds && !mergeModal.scheduledIds.has(s.id)) return false;
                // Only subjects in the same semester
                const subSem = Number(s.semester ?? s.sem);
                if (currentSemester && subSem && subSem !== currentSemester) return false;
                if (!mergeModal.showAllCourses && s.course_id !== sourceSubject.course_id) return false;
                if (tSearch && !(s.code + ' ' + s.description).toLowerCase().includes(tSearch)) return false;
                return true;
              }).sort((a, b) => (a.code || '').localeCompare(b.code || ''));

              // Schedule resource card — block selection + clickable cross-block resource picks
              const ScheduleResCard = ({ scheduleList, side }) => {
                if (!scheduleList || scheduleList.length === 0) return <div className="text-xs text-gray-400 italic py-2">No schedule entries</div>;

                const grouped = {};
                scheduleList.forEach(s => {
                  const key = s.block || '_none';
                  if (!grouped[key]) grouped[key] = { block: s.block, instructor: s.instructor, room: s.room, days: [] };
                  grouped[key].days.push({ day: s.day, time: s.time });
                });

                const picks = mergeModal.resourcePicks;

                return (
                  <div className="space-y-2">
                    {Object.entries(grouped).map(([blockKey, g]) => {
                      const decKey = `${side}_${blockKey}`;
                      const isSelected = mergeModal.selectedBlocks.has(decKey);
                      // For each resource type: is THIS block the picked one?
                      const isPicked = (type) => picks[type] === decKey;
                      // Another block is picked for this type (so this one will be freed)
                      const isFreed = (type) => isSelected && picks[type] && picks[type] !== decKey;

                      const resStyle = (type) => {
                        if (!isSelected) return '';
                        if (isPicked(type)) return 'bg-green-100 border-green-400 ring-1 ring-green-300 font-semibold cursor-pointer';
                        if (isFreed(type)) return 'bg-red-50 line-through opacity-50 cursor-pointer';
                        return 'bg-gray-50 hover:bg-blue-50 cursor-pointer border-dashed border-gray-300';
                      };

                      return (
                        <div key={blockKey} className={`text-xs rounded-lg p-2 border transition-all ${isSelected ? 'bg-white border-indigo-300 ring-1 ring-indigo-200' : 'bg-gray-100 border-gray-200 opacity-60'}`}>
                          <label className="flex items-center gap-2 cursor-pointer mb-1">
                            <input type="checkbox" checked={isSelected} onChange={() => toggleBlockSelection(decKey)} className="w-4 h-4 accent-indigo-600" />
                            <span className={`font-semibold ${isSelected ? 'text-indigo-700' : 'text-gray-500'}`}>
                              {g.block ? `Block ${g.block}` : 'Schedule'}
                              {!isSelected && <span className="ml-2 text-[10px] font-normal text-gray-400">(will not be affected)</span>}
                            </span>
                          </label>
                          <div className={`pl-6 space-y-1 mt-1 ${!isSelected ? 'text-gray-400 text-[10px]' : ''}`}>
                            <div
                              className={`rounded px-2 py-1 border transition-all ${resStyle('instructor')}`}
                              onClick={() => isSelected && pickResource('instructor', decKey)}
                            >
                              {isPicked('instructor') && <span className="text-green-600 mr-1">✓</span>}
                              {"\uD83D\uDC68\u200D\uD83C\uDFEB"} {g.instructor ? g.instructor.name : '(none)'}
                            </div>
                            <div
                              className={`rounded px-2 py-1 border transition-all ${resStyle('room')}`}
                              onClick={() => isSelected && pickResource('room', decKey)}
                            >
                              {isPicked('room') && <span className="text-green-600 mr-1">✓</span>}
                              {"\uD83C\uDFE2"} {g.room ? g.room.name : '(none)'}
                            </div>
                            <div
                              className={`rounded px-2 py-1 border transition-all ${resStyle('time')}`}
                              onClick={() => isSelected && pickResource('time', decKey)}
                            >
                              {isPicked('time') && <span className="text-green-600 mr-1">✓</span>}
                              {"\uD83D\uDD50"} {g.days.map(d => `${d.day ? d.day.label : '?'}`).join('-')} {g.days[0]?.time || '(none)'}
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                );
              };

              return createPortal(
                <div className="fixed inset-0 bg-black/40 flex items-center justify-center p-4 z-50">
                  <div className="w-full max-w-4xl bg-white rounded-xl shadow-xl overflow-hidden">
                    {/* Header */}
                    <div className="bg-indigo-600 px-6 py-4 flex items-center justify-between">
                      <h3 className="text-xl font-semibold text-white flex items-center gap-2">
                        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5"><path d="M3.9 12c0-1.71 1.39-3.1 3.1-3.1h4V7H7c-2.76 0-5 2.24-5 5s2.24 5 5 5h4v-1.9H7c-1.71 0-3.1-1.39-3.1-3.1zM8 13h8v-2H8v2zm9-6h-4v1.9h4c1.71 0 3.1 1.39 3.1 3.1s-1.39 3.1-3.1 3.1h-4V17h4c2.76 0 5-2.24 5-5s-2.24-5-5-5z" /></svg>
                        Merge Subjects
                      </h3>
                      <button onClick={() => setMergeModal(defaultMergeState)} className="text-white/80 hover:text-white text-xl">{"\u2715"}</button>
                    </div>

                    {/* Info */}
                    <div className="px-6 pt-4">
                      <div className="bg-orange-50 text-orange-800 p-3 rounded-lg text-sm border border-orange-200">
                        <strong>How to merge:</strong> Select blocks to include, then <strong>click one resource per type</strong> (instructor, room, time) across all selected blocks. The clicked resource is <strong>copied to all selected blocks</strong>. Merged entries are tagged <code className="bg-orange-100 px-1 rounded">[M]</code>.
                      </div>
                    </div>

                    {/* Horizontal layout: Source \u2192 Target */}
                    <div className="p-6 overflow-y-auto max-h-[60vh]">
                      <div className="flex gap-4 items-stretch">

                        {/* SOURCE (left) */}
                        <div className="flex-1 border rounded-xl overflow-hidden bg-gray-50">
                          <div className="bg-gray-200 px-4 py-2">
                            <div className="text-xs font-bold text-gray-600 uppercase">Source (Schedules move to target)</div>
                          </div>
                          <div className="p-4 space-y-2">
                            <div className="font-semibold text-gray-900">{sourceSubject.code}</div>
                            <div className="text-sm text-gray-600">{sourceSubject.description}</div>
                            <div className="text-xs text-gray-500">{sourceSubject.type} {"\u2022"} {sourceSubject.unit} Units</div>
                            <div className="text-xs text-gray-400">{mergeCourseName(sourceSubject.course_id)}</div>
                            {mergeModal.preview && (
                              <div className="mt-3 pt-3 border-t">
                                <div className="text-xs font-semibold text-gray-500 mb-2">Schedule Resources {"\u2014"} check to keep:</div>
                                <ScheduleResCard scheduleList={mergeModal.preview.source.schedules} side="source" />
                              </div>
                            )}
                            {mergeModal.previewLoading && <div className="text-xs text-gray-400 mt-2">Loading schedules...</div>}
                          </div>
                        </div>

                        {/* Arrow + Swap */}
                        <div className="flex flex-col items-center justify-center gap-2 px-2">
                          <div className="text-2xl text-gray-400">{"\u2192"}</div>
                          <button onClick={swapMergeDirection} className="bg-white border shadow-sm rounded-full p-2 hover:bg-gray-50 hover:text-indigo-600 transition-colors" title="Swap source and target">
                            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-5 h-5">
                              <path strokeLinecap="round" strokeLinejoin="round" d="M7.5 21L3 16.5m0 0L7.5 12M3 16.5h13.5m0-13.5L21 7.5m0 0L16.5 12M21 7.5H7.5" />
                            </svg>
                          </button>
                        </div>

                        {/* TARGET (right) */}
                        <div className="flex-1 border rounded-xl overflow-hidden border-indigo-200">
                          <div className="bg-indigo-50 px-4 py-2 flex items-center justify-between">
                            <div className="text-xs font-bold text-indigo-700 uppercase">Target (Will survive)</div>
                            <button
                              onClick={() => setMergeModal(prev => ({ ...prev, showAllCourses: !prev.showAllCourses }))}
                              className="text-[10px] bg-indigo-100 text-indigo-700 px-2 py-0.5 rounded-full hover:bg-indigo-200 transition-colors"
                            >
                              {mergeModal.showAllCourses ? 'All programs' : 'Same program'}
                            </button>
                          </div>
                          <div className="p-4 space-y-3">
                            {/* Search input */}
                            <input
                              className="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm focus:ring-2 focus:ring-indigo-500 outline-none"
                              placeholder="Search target subject..."
                              value={mergeModal.targetSearch}
                              onChange={e => setMergeModal(prev => ({ ...prev, targetSearch: e.target.value }))}
                            />

                            {/* Scrollable subject list */}
                            <div className="max-h-36 overflow-y-auto space-y-1 border rounded-lg p-2 bg-gray-50">
                              {targetOptions.length === 0 && (
                                <div className="text-xs text-gray-400 text-center py-3">No matching subjects</div>
                              )}
                              {targetOptions.map(opt => (
                                <div
                                  key={opt.id}
                                  onClick={() => selectMergeTarget(opt.id)}
                                  className={`px-3 py-2 rounded-lg cursor-pointer text-sm transition-colors ${mergeModal.targetId === opt.id
                                    ? 'bg-indigo-100 border-indigo-300 border text-indigo-900 font-semibold'
                                    : 'hover:bg-white border border-transparent'
                                    }`}
                                >
                                  <div className="font-medium">{opt.code}</div>
                                  <div className="text-xs text-gray-500">{opt.description} {"\u2022"} {opt.type} {"\u2022"} {opt.unit} Units {mergeModal.showAllCourses ? `[${mergeCourseName(opt.course_id)}]` : ''}</div>
                                </div>
                              ))}
                            </div>

                            {/* Target schedule resources */}
                            {mergeModal.preview && mergeModal.targetId && (
                              <div className="mt-2 pt-2 border-t">
                                <div className="text-xs font-semibold text-gray-500 mb-2">Schedule Resources {"\u2014"} check to keep:</div>
                                <ScheduleResCard scheduleList={mergeModal.preview.target.schedules} side="target" />
                              </div>
                            )}
                            {mergeModal.previewLoading && <div className="text-xs text-gray-400 mt-2">Loading schedules...</div>}
                          </div>
                        </div>

                      </div>

                      {/* Compatibility status */}
                      {mergeModal.compatChecked && mergeModal.targetId && (
                        <div className={`mt-4 p-3 rounded-lg border text-sm ${mergeModal.safe ? 'bg-green-50 border-green-200 text-green-800' : 'bg-red-50 border-red-200 text-red-800'}`}>
                          {mergeModal.safe ? (
                            <div className="flex items-center gap-2">{"\u2705"} <strong>Compatible</strong> {"\u2014"} No instructor or room conflicts detected.</div>
                          ) : (
                            <div>
                              <div className="flex items-center gap-2 mb-2">{"\u26A0\uFE0F"} <strong>Conflicts detected {"\u2014"} merge blocked</strong></div>
                              <ul className="list-disc list-inside space-y-1 text-xs">
                                {mergeModal.conflicts.map((c, i) => <li key={i}>{c.message || c}</li>)}
                              </ul>
                            </div>
                          )}
                        </div>
                      )}
                    </div>

                    {/* Footer */}
                    <div className="bg-gray-50 px-6 py-4 flex items-center justify-between border-t">
                      <button
                        onClick={() => mergeModal.sourceSubjectId && mergeModal.targetId && loadMergePreviewData(mergeModal.sourceSubjectId, mergeModal.targetId)}
                        className="px-4 py-2 rounded bg-gray-200 text-gray-700 font-medium hover:bg-gray-300 transition-colors disabled:opacity-50"
                        disabled={!mergeModal.targetId || mergeModal.previewLoading}
                      >
                        {mergeModal.previewLoading ? 'Checking...' : '\uD83D\uDD0D Re-check Compatibility'}
                      </button>
                      <div className="flex gap-3">
                        <button
                          onClick={() => setMergeModal(defaultMergeState)}
                          className="px-4 py-2 rounded text-gray-700 font-medium hover:bg-gray-200 transition-colors"
                          disabled={mergeProcessing}
                        >
                          Cancel
                        </button>
                        <button
                          onClick={handleConfirmMerge}
                          className="px-4 py-2 rounded bg-indigo-600 text-white font-medium hover:bg-indigo-700 transition-colors disabled:opacity-50"
                          disabled={mergeProcessing || !mergeModal.targetId || !mergeModal.safe || mergeModal.selectedBlocks.size === 0 || !mergeModal.resourcePicks.instructor || !mergeModal.resourcePicks.room || !mergeModal.resourcePicks.time}
                        >
                          {mergeProcessing ? 'Merging...' : 'Confirm Merge'}
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
                , document.body);
            })()}

            {!isSubmitting && Object.keys(expandedSchedule).length === 0 && !error && (
              <p className="mt-6 text-sm text-gray-500">
                {hasCheckedSavedSchedule
                  ? "No schedule to display for the current selection."
                  : "Run the scheduler to see results."}
              </p>
            )}

            {/* Edit Modal */}
            {editingItem && createPortal(
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
              , document.body)}
            {/* RESOLVE MODAL */}
            {resolvingItem && createPortal(
              <ResolveModal
                resolvingItem={resolvingItem}
                setResolvingItem={setResolvingItem}
                openEditModal={openEditModal}
                form={form}
              />
              , document.body)}


            {recommendationModalItem && createPortal(
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
              , document.body)}
          </div>{/* end px-6 content */}
        </div>{/* end transition wrapper */}
      </div>{/* end scheduler accordion */}

      {/* ──── ACCORDION: Dashboard Analytics ──── */}
      <div id="section-dashboard" className="bg-white/60 backdrop-blur rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
        <button
          onClick={() => setOpenSection(prev => prev === 'dashboard' ? null : 'dashboard')}
          className="w-full flex items-center justify-between px-6 py-4 hover:bg-slate-50/80 transition-colors"
        >
          <div className="text-left">
            <h2 className="text-lg font-bold text-slate-800">📊 Dashboard Analytics</h2>
            <p className="text-sm text-slate-500">Room utilization, instructor loads, conflicts, staffing gaps, and recommendations.</p>
          </div>
          <svg className={`w-5 h-5 text-slate-400 transition-transform duration-200 ${openSection === 'dashboard' ? 'rotate-180' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" /></svg>
        </button>
        <div className={`transition-all duration-300 ease-in-out ${openSection === 'dashboard' ? 'max-h-[100000px] opacity-100' : 'max-h-0 opacity-0 overflow-hidden'}`}>
          <div className="px-6 pb-6 pt-2">
            <DashboardPanel />
          </div>
        </div>
      </div>

      {/* ──── ACCORDION: Room Schedule ──── */}
      <div id="section-room-schedule" className="bg-white/60 backdrop-blur rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
        <button
          onClick={() => setOpenSection(prev => prev === 'room-schedule' ? null : 'room-schedule')}
          className="w-full flex items-center justify-between px-6 py-4 hover:bg-slate-50/80 transition-colors"
        >
          <div className="text-left">
            <h2 className="text-lg font-bold text-slate-800">🏢 Room Schedule</h2>
            <p className="text-sm text-slate-500">Full day view of room utilization and vacancies.</p>
          </div>
          <svg className={`w-5 h-5 text-slate-400 transition-transform duration-200 ${openSection === 'room-schedule' ? 'rotate-180' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" /></svg>
        </button>
        <div className={`transition-all duration-300 ease-in-out ${openSection === 'room-schedule' ? 'max-h-[100000px] opacity-100' : 'max-h-0 opacity-0 overflow-hidden'}`}>
          <div className="px-6 pb-6 pt-2">
            <RoomSchedulePanel />
          </div>
        </div>
      </div>

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
        room: r.room_name || r.room,
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

  // Derive bottleneck chips from failure reason
  const reason = resolvingItem?.failureReason || "Unscheduled";
  const bottlenecks = [];
  if (reason === "Room Conflict" || reason === "No Rooms") {
    bottlenecks.push({ label: "Room", color: "bg-orange-100 text-orange-700 border-orange-200", icon: "🏫" });
  }
  if (reason === "Instructor Conflict" || reason === "No Instructor") {
    bottlenecks.push({ label: "Instructor", color: "bg-purple-100 text-purple-700 border-purple-200", icon: "👤" });
  }
  if (reason === "Student Conflict") {
    bottlenecks.push({ label: "Student Schedule", color: "bg-yellow-100 text-yellow-700 border-yellow-200", icon: "🎓" });
  }
  if (reason === "Solver Conflict" || reason === "All Slots Booked") {
    bottlenecks.push({ label: "Room", color: "bg-orange-100 text-orange-700 border-orange-200", icon: "🏫" });
    bottlenecks.push({ label: "Instructor", color: "bg-purple-100 text-purple-700 border-purple-200", icon: "👤" });
  }
  if (reason === "Cross-Block Conflict") {
    bottlenecks.push({ label: "Need more instructors for this subject", color: "bg-purple-100 text-purple-700 border-purple-200", icon: "👤" });
  }
  if (reason === "No Valid Time") {
    bottlenecks.push({ label: "Time", color: "bg-cyan-100 text-cyan-700 border-cyan-200", icon: "⏰" });
  }
  if (bottlenecks.length === 0) {
    bottlenecks.push({ label: "Unknown", color: "bg-gray-100 text-gray-600 border-gray-200", icon: "❓" });
  }

  // Detail / suggestion from diagnostics
  const diagDetail = resolvingItem?.diagDetail || "";
  const diagSuggestion = resolvingItem?.diagSuggestion || "";
  const subjectCode = resolvingItem?.diagSubjectCode || `Subject #${resolvingItem?.subject_id}`;
  const subjectType = resolvingItem?.diagSubjectType || "";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-lg overflow-hidden animate-in fade-in zoom-in duration-200">
        {/* Header */}
        <div className="bg-gradient-to-r from-blue-600 to-indigo-600 p-4 flex justify-between items-center text-white">
          <div>
            <h3 className="font-bold text-lg flex items-center gap-2">
              <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
              </svg>
              Resolve: {subjectCode}
            </h3>
            {subjectType && (
              <span className="text-xs text-white/70 ml-7">{subjectType} • Block {resolvingItem?.block || "?"}</span>
            )}
          </div>
          <button onClick={() => setResolvingItem(null)} className="hover:bg-white/20 p-1 rounded-full transition-colors">
            <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
              <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
            </svg>
          </button>
        </div>

        <div className="p-6">
          {/* Bottleneck chips */}
          <div className="flex flex-wrap gap-2 mb-4">
            <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide self-center mr-1">Bottleneck:</span>
            {bottlenecks.map((b, i) => (
              <span
                key={i}
                className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold border ${b.color}`}
              >
                <span>{b.icon}</span> {b.label}
              </span>
            ))}
          </div>

          {/* Diagnosed Issue */}
          <div className="bg-red-50 border border-red-100 rounded-lg p-4 mb-4">
            <div className="text-xs font-bold text-red-500 uppercase tracking-wide mb-1">Diagnosed Issue</div>
            <div className="text-red-800 font-semibold text-base flex items-center gap-2">
              <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 flex-shrink-0" viewBox="0 0 20 20" fill="currentColor">
                <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
              </svg>
              {reason}
            </div>
            {diagDetail && (
              <p className="text-red-700/80 text-sm mt-1">{diagDetail}</p>
            )}
            {!diagDetail && (
              <p className="text-red-700/80 text-sm mt-1">
                {reason === "Solver Conflict" && "Valid slots exist, but they conflict with other scheduled classes."}
                {reason === "No Rooms" && "No rooms are available or eligible for this subject type."}
                {reason === "No Instructor" && "No eligible instructor is available."}
                {reason === "Room Conflict" && "All eligible rooms are fully booked during suggested times."}
                {reason === "Instructor Conflict" && "The assigned instructor is fully booked."}
                {reason === "Student Conflict" && "Scheduling this would overlap with another class for this block."}
                {reason === "Unscheduled" && "The scheduler could not find a valid slot."}
              </p>
            )}
          </div>

          {/* Actionable Suggestion */}
          {diagSuggestion && (
            <div className="bg-blue-50 border border-blue-100 rounded-lg p-3 mb-4">
              <div className="flex items-start gap-2">
                <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 text-blue-500 flex-shrink-0 mt-0.5" viewBox="0 0 20 20" fill="currentColor">
                  <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
                </svg>
                <p className="text-blue-800 text-sm">{diagSuggestion}</p>
              </div>
            </div>
          )}

          {/* Suggestions */}
          <div>
            <h5 className="font-semibold text-gray-700 mb-3 flex items-center gap-2">
              <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 text-green-500" viewBox="0 0 20 20" fill="currentColor">
                <path fillRule="evenodd" d="M6.267 3.455a3.066 3.066 0 001.745-.723 3.066 3.066 0 013.976 0 3.066 3.066 0 001.745.723 3.066 3.066 0 012.812 2.812c.051.643.304 1.254.723 1.745a3.066 3.066 0 010 3.976 3.066 3.066 0 00-.723 1.745 3.066 3.066 0 01-2.812 2.812 3.066 3.066 0 00-1.745.723 3.066 3.066 0 01-3.976 0 3.066 3.066 0 00-1.745-.723 3.066 3.066 0 01-2.812-2.812 3.066 3.066 0 00-.723-1.745 3.066 3.066 0 010-3.976 3.066 3.066 0 00.723-1.745 3.066 3.066 0 012.812-2.812zm7.44 5.252a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
              </svg>
              Available Slots ({suggestions.length})
            </h5>

            {loading ? (
              <div className="flex justify-center p-4">
                <svg className="animate-spin h-5 w-5 text-blue-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path>
                </svg>
              </div>
            ) : suggestions.length > 0 ? (
              <div className="space-y-2 max-h-48 overflow-y-auto">
                {suggestions.map((s, idx) => (
                  <button
                    key={idx}
                    onClick={() => {
                      setResolvingItem(null);
                      const overrideItem = {
                        ...resolvingItem,
                        _combinedDaysLabel: s.day_label || s.day,
                        _dayIds: s.day_ids || [s.day_id],
                        room_id: s.room_id,
                        instructor_id: s.instructor_id,
                        start_min: s.start_min,
                        end_min: s.end_min,
                        time: s.time,
                      };
                      openEditModal(overrideItem);
                    }}
                    className="w-full text-left p-3 border border-green-100 bg-green-50 hover:bg-green-100 rounded-lg text-sm text-green-900 flex justify-between items-center group transition-colors"
                  >
                    <div className="flex items-center gap-3">
                      <div className="w-7 h-7 bg-green-200 rounded-full flex items-center justify-center text-green-700 font-bold text-xs flex-shrink-0">
                        {idx + 1}
                      </div>
                      <div>
                        <div className="font-semibold text-gray-800">{s.day_label || s.day} @ {s.time}</div>
                        <div className="text-xs text-green-700">
                          {s.room || s.room_name}
                          {" • "}
                          {s.instructor_name || (s.instructor_id ? `Instructor #${s.instructor_id}` : "No Instructor")}
                        </div>
                      </div>
                    </div>
                    <span className="opacity-0 group-hover:opacity-100 text-green-600 font-medium text-xs bg-white px-2 py-1 rounded shadow-sm transition-opacity">
                      Apply
                    </span>
                  </button>
                ))}
              </div>
            ) : (
              <div className="bg-gray-50 rounded border border-gray-200 p-4 text-center text-sm text-gray-500">
                No automated suggestions found.<br />
                <span className="text-xs">Use "Manual Override" below to assign this subject manually.</span>
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
