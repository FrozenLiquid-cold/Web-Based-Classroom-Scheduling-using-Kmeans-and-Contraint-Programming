import { useEffect, useMemo, useState, useRef } from 'react'
import { list, upsert, remove } from '../../store/db'
import ConfirmDialog from '../../components/ConfirmDialog'

// Subjects that are cross-program / government-mandated.
// Exempt from mismatch warnings and staffing coverage recommendations.
const EXEMPT_SUBJECT_PREFIXES = ['NSTP', 'ROTC', 'CWTS', 'LTS']
function isExemptSubject(normCode) {
	return EXEMPT_SUBJECT_PREFIXES.some(pfx =>
		normCode === pfx ||
		normCode.startsWith(pfx + ' ') ||
		normCode.startsWith(pfx + '-') ||
		normCode.startsWith(pfx + '_')
	)
}

export default function Instructor() {
	const [items, setItems] = useState([])
	const [colleges, setColleges] = useState([])
	const [courses, setCourses] = useState([])
	const [subjects, setSubjects] = useState([])
	const [designations, setDesignations] = useState([])
	const [q, setQ] = useState('')
	const [show, setShow] = useState(false)
	const [editing, setEditing] = useState(null)
	const [firstName, setFirstName] = useState('')
	const [middleName, setMiddleName] = useState('')
	const [lastName, setLastName] = useState('')
	const [collegeId, setCollegeId] = useState('')
	const [employmentType, setEmploymentType] = useState('regular')
	const [designation, setDesignation] = useState('')
	const [specialization, setSpecialization] = useState([])
	const [specializationSearch, setSpecializationSearch] = useState('')
	// Program assignment
	const [homeCourseId, setHomeCourseId] = useState('')
	const [linkedCourses, setLinkedCourses] = useState([])  // array of course objects {id, code, description}
	const [linkedCourseSearch, setLinkedCourseSearch] = useState('')
	const [error, setError] = useState('')
	const [entries, setEntries] = useState(50)
	const [processing, setProcessing] = useState(false)
	const [confirmDialog, setConfirmDialog] = useState({ open: false })
	const [coveragePanelCollapsed, setCoveragePanelCollapsed] = useState(false)
	// Collapse state for the grouped table — start fully collapsed (empty Set = all collapsed)
	const [expandedColleges, setExpandedColleges] = useState(new Set())
	const [expandedPrograms, setExpandedPrograms] = useState(new Set())
	function toggleCollege(key) {
		setExpandedColleges(prev => { const n = new Set(prev); n.has(key) ? n.delete(key) : n.add(key); return n })
	}
	function toggleProgram(key) {
		setExpandedPrograms(prev => { const n = new Set(prev); n.has(key) ? n.delete(key) : n.add(key); return n })
	}

	// Prevent duplicate loads from React StrictMode
	const dataLoadingRef = useRef(false);
	const dataLoadedRef = useRef(false);

	async function load(force = false) {
		// Skip if already loaded or currently loading (unless forced)
		if (!force && (dataLoadedRef.current || dataLoadingRef.current)) {
			return;
		}

		dataLoadingRef.current = true;
		try {
			const [instructorsData, collegesData, subjectsData, coursesData] = await Promise.all([
				list('instructor'),
				list('college'),
				list('subject'),
				list('course'),
			])
			setItems(instructorsData)
			setColleges(collegesData)
			setSubjects(subjectsData || [])
			setCourses(coursesData || [])
			// Load designations from settings
			try {
				const dRes = await fetch('http://localhost:8000/api/designation-deductions')
				if (dRes.ok) setDesignations(await dRes.json())
			} catch (e) { console.error('Failed to load designations', e) }
			dataLoadedRef.current = true;
		} catch (error) {
			console.error('Error loading data:', error);
		} finally {
			dataLoadingRef.current = false;
		}
	}
	useEffect(() => { load() }, [])

	const filtered = useMemo(() => {
		return items.filter(i => {
			const firstName = i.first_name || i.firstName || ''
			const middleName = i.middle_name || i.middleName || ''
			const lastName = i.last_name || i.lastName || ''
			return (`${firstName} ${middleName} ${lastName}`).toLowerCase().includes(q.toLowerCase())
		})
	}, [items, q])

	const shown = useMemo(() => {
		const n = Math.max(0, Number(entries) || 0)
		return filtered.slice(0, n || filtered.length)
	}, [filtered, entries])

	function openAdd() {
		setEditing(null)
		setFirstName('')
		setMiddleName('')
		setLastName('')
		setCollegeId('')
		setEmploymentType('regular')
		setDesignation('')
		setSpecialization([])
		setSpecializationSearch('')
		setHomeCourseId('')
		setLinkedCourses([])
		setLinkedCourseSearch('')
		setError('')
		setShow(true)
	}

	function openEdit(it) {
		setEditing(it)
		setFirstName(it.first_name || it.firstName || '')
		setMiddleName(it.middle_name || it.middleName || '')
		setLastName(it.last_name || it.lastName || '')
		setCollegeId(it.college_id || it.collegeId || '')
		setEmploymentType(it.employment_type || it.employmentType || 'regular')
		setDesignation(it.designation || '')
		{
			const raw = it.assignable_courses || it.assignableCourses || ''
			const parsed = raw
				.split(',')
				.map(s => s.trim())
				.filter(Boolean)
			setSpecialization(parsed)
		}
		setSpecializationSearch('')
		// Program assignment
		setHomeCourseId(it.home_course_id != null ? String(it.home_course_id) : '')
		{
			const linkedRaw = (it.linked_course_ids || '').trim()
			if (linkedRaw) {
				const ids = linkedRaw.split(',').map(s => s.trim()).filter(Boolean)
				const resolved = ids
					.map(id => (courses || []).find(c => String(c.id) === id))
					.filter(Boolean)
				setLinkedCourses(resolved)
			} else {
				setLinkedCourses([])
			}
		}
		setLinkedCourseSearch('')
		setError('')
		setShow(true)
	}

	async function onSave(e) {
		e.preventDefault()
		if (processing) return
		if (!firstName.trim() || !lastName.trim()) { setError('First and Last name are required'); return }
		try {
			setProcessing(true)
			const payload = {
				id: editing?.id,
				first_name: firstName.trim(),
				middle_name: middleName.trim() || null,
				last_name: lastName.trim(),
				college_id: collegeId ? parseInt(collegeId) : null,
				employment_type: employmentType || null,
				designation: designation.trim() || null,
				assignable_courses: specialization && specialization.length
					? specialization.join(',')
					: null,
				// Program assignment
				home_course_id: homeCourseId ? parseInt(homeCourseId) : null,
				linked_course_ids: linkedCourses.length
					? linkedCourses.map(c => c.id).join(',')
					: null,
			}
			await upsert('instructor', payload)
			setShow(false)
			await load(true)
		} catch (error) {
			setError(error.message || 'Failed to save')
		} finally {
			setProcessing(false)
		}
	}

	const collegeName = (id) => {
		if (!id) return ''
		const college = colleges.find(c => c.id === id)
		return college?.code || ''
	}

	// Helper: resolve course by ID — must be declared before memos that depend on it
	const courseById = useMemo(() => {
		const map = {}
		for (const c of (courses || [])) map[c.id] = c
		return map
	}, [courses])

	// Build a map of code → all variant subjects (for showing descriptions)
	const subjectVariantsMap = useMemo(() => {
		const map = {} // normalised code → [{ code, description, type, unit, semester, id }]
		for (const s of (subjects || [])) {
			if (!s || !s.code) continue
			const norm = s.code.trim().toUpperCase().replace(/\s+/g, ' ')
			if (!map[norm]) map[norm] = { code: s.code, variants: [], semesters: new Set() }
			// Avoid duplicate description+type combos
			const key = `${(s.description || '').toLowerCase()}|${s.type}`
			if (!map[norm].variants.find(v => `${(v.description || '').toLowerCase()}|${v.type}` === key)) {
				map[norm].variants.push({ id: s.id, code: s.code, description: s.description, type: s.type, unit: s.unit, semester: s.semester })
			}
			if (s.semester) map[norm].semesters.add(s.semester)
		}
		return map
	}, [subjects])

	const subjectOptions = useMemo(() => {
		const query = specializationSearch.trim().toLowerCase()
		const selectedSet = new Set(specialization)
		// Group subjects by normalised code and return one entry per code
		const seen = new Set()
		return (subjects || [])
			.filter(s => {
				if (!s || !s.code) return false
				const norm = s.code.trim().toUpperCase().replace(/\s+/g, ' ')
				if (seen.has(norm)) return false
				if (selectedSet.has(s.code)) return false
				if (selectedSet.has(norm)) return false
				// Also check if any variant's code is already selected
				if ([...selectedSet].some(sel => sel.trim().toUpperCase().replace(/\s+/g, ' ') === norm)) return false
				if (!query) { seen.add(norm); return true }
				// Search across ALL variants of this code
				const group = subjectVariantsMap[norm]
				if (!group) return false
				const matchesCode = norm.toLowerCase().includes(query) || s.code.toLowerCase().includes(query)
				const matchesDesc = group.variants.some(v => (v.description || '').toLowerCase().includes(query))
				if (matchesCode || matchesDesc) { seen.add(norm); return true }
				return false
			})
			.slice(0, 10)
	}, [subjects, specialization, specializationSearch, subjectVariantsMap])

	// Map subject codes to their semester(s) for display
	const subjectSemMap = useMemo(() => {
		const map = {} // normalised code -> Set of semesters
		for (const s of (subjects || [])) {
			if (!s || !s.code) continue
			const norm = s.code.trim().toUpperCase().replace(/\s+/g, ' ')
			if (!map[norm]) map[norm] = new Set()
			if (s.semester) map[norm].add(s.semester)
		}
		return map
	}, [subjects])

	// Build a map of normalised course CODE → Set<normalizedSubjectCode>.
	// Keyed by CODE (not ID) so that all majors of the same program (e.g.
	// BSIS/Network-Tech and BSIS/Business-Analytics) share a single pool.
	// Subjects with null course_id (shared GEs) are injected into every pool.
	const courseSubjectCodeSet = useMemo(() => {
		const map = {} // courseCode (string, upper) → Set<normalised subject code>
		const sharedCodes = new Set() // course_id = null → belongs to all
		for (const s of (subjects || [])) {
			if (!s || !s.code) continue
			const norm = s.code.trim().toUpperCase().replace(/\s+/g, ' ')
			if (s.course_id == null) {
				sharedCodes.add(norm)
			} else {
				// Look up the parent course to get its base code
				const parentCourse = courseById[s.course_id]
				const courseKey = parentCourse
					? parentCourse.code.trim().toUpperCase()
					: String(s.course_id) // fallback to id string if course unknown
				if (!map[courseKey]) map[courseKey] = new Set()
				map[courseKey].add(norm)
			}
		}
		// Inject shared codes (GEs) into every program pool
		for (const ck of Object.keys(map)) {
			for (const sc of sharedCodes) map[ck].add(sc)
		}
		map.__shared = sharedCodes
		return map
	}, [subjects, courseById])

	// Specialization codes NOT found in the selected home program's subject pool
	// AND not covered by any linked program.
	// Uses the base course CODE so all majors (BSIS/NetworkTech, BSIS/Bus, etc.) share one pool.
	// Codes that don't exist in the DB at all are skipped (already warned by '?' badge).
	const mismatchedSpecs = useMemo(() => {
		if (!homeCourseId || !specialization.length) return new Set()
		const homeId = parseInt(homeCourseId)
		const homeCourse = courseById[homeId]
		if (!homeCourse) return new Set()
		// Key is the base program code (e.g. 'BSIS') — covers all majors
		const homeKey = homeCourse.code.trim().toUpperCase()
		const homeCodes = courseSubjectCodeSet[homeKey]
		if (!homeCodes) return new Set() // no subjects mapped yet — can't judge

		// Build a union of all codes allowed by linked programs (so those are NOT flagged)
		const linkedAllowedCodes = new Set()
		for (const lc of linkedCourses) {
			const lcKey = (lc.code || '').trim().toUpperCase()
			if (!lcKey) continue
			const lcCodes = courseSubjectCodeSet[lcKey]
			if (lcCodes) for (const c of lcCodes) linkedAllowedCodes.add(c)
		}

		const mismatched = new Set()
		for (const code of specialization) {
			const norm = code.trim().toUpperCase().replace(/\s+/g, ' ')
			if (isExemptSubject(norm)) continue  // NSTP, ROTC, etc. are cross-program — never a mismatch
			// Only flag if it exists in the DB (any program or a shared GE)
			const existsAnywhere =
				(courseSubjectCodeSet.__shared && courseSubjectCodeSet.__shared.has(norm)) ||
				Object.values(courseSubjectCodeSet).some(cset => cset instanceof Set && cset.has(norm))
			// Not a mismatch if it's covered by the home program OR any linked program
			if (existsAnywhere && !homeCodes.has(norm) && !linkedAllowedCodes.has(norm)) {
				mismatched.add(code)
			}
		}
		return mismatched
	}, [homeCourseId, specialization, courseSubjectCodeSet, courseById, linkedCourses])

	// Recommended subjects for a given course CODE (sorted year → semester → code).
	// Returns [{code, description, year_level, semester}], one entry per unique code.
	const programRecommendedSubjects = useMemo(() => {
		// Map: normalised course CODE → sorted unique subject list
		const result = {} // courseCode → [{code, description, year_level, semester}]
		const seen = {} // courseCode → Set<normSubjCode>
		const sorted = [...(subjects || [])].sort((a, b) => {
			const ya = a.year_level || 99, yb = b.year_level || 99
			if (ya !== yb) return ya - yb
			const sa = a.semester || 99, sb = b.semester || 99
			if (sa !== sb) return sa - sb
			return (a.code || '').localeCompare(b.code || '')
		})
		for (const s of sorted) {
			if (!s || !s.code || s.course_id == null) continue
			const parent = courseById[s.course_id]
			if (!parent) continue
			const ck = parent.code.trim().toUpperCase()
			const norm = s.code.trim().toUpperCase().replace(/\s+/g, ' ')
			if (!seen[ck]) { seen[ck] = new Set(); result[ck] = [] }
			if (!seen[ck].has(norm)) {
				seen[ck].add(norm)
				result[ck].push({ code: s.code, description: s.description, year_level: s.year_level, semester: s.semester })
			}
		}
		return result
	}, [subjects, courseById])

	// Count how many ACTIVE instructors currently cover each subject code.
	// Used to score subjects: 0 = critical (no coverage), 1 = solo risk, 2+ = ok.
	// Program-scoped coverage: programCode → normSubjCode → count.
	// An instructor is counted for a program only if that program is their home
	// or one of their linked programs — preventing cross-program over-counting.
	const subjectCoverageMap = useMemo(() => {
		const map = {} // programCode -> normSubjCode -> count
		for (const instr of (items || [])) {
			if (instr.is_active === false) continue
			// Collect program codes this instructor is eligible for
			const eligiblePrograms = new Set()
			if (instr.home_course_id && courseById[instr.home_course_id]) {
				eligiblePrograms.add(courseById[instr.home_course_id].code.trim().toUpperCase())
			}
			const linkedIds = (instr.linked_course_ids || '').split(',').map(s => s.trim()).filter(Boolean)
			for (const lid of linkedIds) {
				const lc = courseById[parseInt(lid)]
				if (lc) eligiblePrograms.add(lc.code.trim().toUpperCase())
			}
			if (!eligiblePrograms.size) continue
			// Credit this instructor's subjects to each eligible program
			const raw = instr.assignable_courses || instr.assignableCourses || ''
			for (const c of raw.split(',')) {
				const norm = c.trim().toUpperCase().replace(/\s+/g, ' ')
				if (!norm) continue
				for (const pk of eligiblePrograms) {
					if (!map[pk]) map[pk] = {}
					map[pk][norm] = (map[pk][norm] || 0) + 1
				}
			}
		}
		return map
	}, [items, courseById])

	function getSubjectSem(code) {
		const norm = (code || '').trim().toUpperCase().replace(/\s+/g, ' ')
		const sems = subjectSemMap[norm]
		if (!sems || sems.size === 0) return { label: '?', color: 'bg-slate-200 text-slate-600' }
		if (sems.has(1) && sems.has(2)) return { label: 'S1+S2', color: 'bg-emerald-100 text-emerald-700' }
		if (sems.has(1)) return { label: 'S1', color: 'bg-indigo-100 text-indigo-700' }
		if (sems.has(2)) return { label: 'S2', color: 'bg-teal-100 text-teal-700' }
		return { label: '?', color: 'bg-slate-200 text-slate-600' }
	}

	function getVariantCount(code) {
		const norm = (code || '').trim().toUpperCase().replace(/\s+/g, ' ')
		return subjectVariantsMap[norm]?.variants?.length || 0
	}

	function addSpecialization(code) {
		if (!code) return
		setSpecialization(prev => {
			if (prev.includes(code)) return prev
			return [...prev, code]
		})
	}

	function removeSpecialization(code) {
		setSpecialization(prev => prev.filter(c => c !== code))
	}

	// Linked course helpers
	const linkedCourseOptions = useMemo(() => {
		const query = linkedCourseSearch.trim().toLowerCase()
		const selectedIds = new Set(linkedCourses.map(c => c.id))
		const homeId = homeCourseId ? parseInt(homeCourseId) : null
		return (courses || [])
			.filter(c => {
				if (selectedIds.has(c.id)) return false
				if (homeId && c.id === homeId) return false  // don't link own home
				if (!query) return true
				return (c.code || '').toLowerCase().includes(query) ||
					(c.description || '').toLowerCase().includes(query) ||
					(c.major || '').toLowerCase().includes(query)
			})
			.slice(0, 8)
	}, [courses, linkedCourses, linkedCourseSearch, homeCourseId])

	function addLinkedCourse(course) {
		if (!course) return
		setLinkedCourses(prev => prev.find(c => c.id === course.id) ? prev : [...prev, course])
		setLinkedCourseSearch('')
	}

	function removeLinkedCourse(id) {
		setLinkedCourses(prev => prev.filter(c => c.id !== id))
	}

	function onDelete(id) {
		if (processing) return
		setConfirmDialog({
			open: true,
			title: 'Delete Instructor',
			message: 'Are you sure you want to delete this instructor? This action cannot be undone.',
			confirmText: 'Delete',
			variant: 'danger',
			onConfirm: async () => {
				setConfirmDialog({ open: false })
				try {
					setProcessing(true)
					await remove('instructor', id)
					await load(true)
				} catch (error) {
					alert(error.message || 'Failed to delete')
				} finally {
					setProcessing(false)
				}
			},
		})
	}

	// Group instructors by college for display
	const grouped = useMemo(() => {
		const collegeMap = {}
		colleges.forEach(c => { collegeMap[c.id] = c })

		// Each instructor appears once per program they can teach:
		//   their home program + each linked program.
		const allEntries = []
		shown.forEach(it => {
			const cid = String(it.college_id || it.collegeId || '__none')
			const homeId = it.home_course_id ? String(it.home_course_id) : '__none'
			allEntries.push({ it, programId: homeId, isLinked: false, cid })
			const linkedIds = (it.linked_course_ids || '').split(',').map(s => s.trim()).filter(Boolean)
			for (const lid of linkedIds) {
				allEntries.push({ it, programId: lid, isLinked: true, cid })
			}
		})

		// Group: college -> program -> [entries]
		const collegeProgMap = {}
		allEntries.forEach(e => {
			if (!collegeProgMap[e.cid]) collegeProgMap[e.cid] = {}
			const pm = collegeProgMap[e.cid]
			if (!pm[e.programId]) pm[e.programId] = []
			pm[e.programId].push(e)
		})

		const sortedCollegeIds = Object.keys(collegeProgMap).sort((a, b) => {
			if (a === '__none') return 1
			if (b === '__none') return -1
			return (collegeMap[a]?.code || '').localeCompare(collegeMap[b]?.code || '')
		})

		return sortedCollegeIds.map(cid => {
			const pm = collegeProgMap[cid]
			const sortedProgIds = Object.keys(pm).sort((a, b) => {
				if (a === '__none') return 1
				if (b === '__none') return -1
				return (courseById[parseInt(a)]?.code || '').localeCompare(courseById[parseInt(b)]?.code || '')
			})
			const programs = sortedProgIds.map(pid => ({
				program: pid !== '__none' ? courseById[parseInt(pid)] : null,
				entries: pm[pid].slice().sort((a, b) => {
					const na = `${a.it.last_name || ''} ${a.it.first_name || ''}`.toLowerCase()
					const nb = `${b.it.last_name || ''} ${b.it.first_name || ''}`.toLowerCase()
					return na.localeCompare(nb)
				}),
			}))
			// Unique instructor count for this college (de-dup by id)
			const uniqueCount = new Set(programs.flatMap(p => p.entries.map(e => e.it.id))).size
			return {
				college: cid !== '__none' ? collegeMap[cid] : null,
				programs,
				uniqueCount,
			}
		})
	}, [shown, colleges, courseById])

	return (
		<div>
			<div className="flex items-center justify-between mb-4">
				<h1 className="text-navy text-3xl font-semibold">INSTRUCTOR</h1>
				<button className="px-3 py-2 rounded bg-royal text-white flex items-center gap-2 disabled:opacity-60" onClick={openAdd} disabled={processing}>
					<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-4 h-4"><path d="M11 11V5h2v6h6v2h-6v6h-2v-6H5v-2h6z" /></svg>
					<span>Add Instructor</span>
				</button>
			</div>
			{/* Standardized fixed-height container for list/table area */}
			<div className="h-[520px] overflow-auto pr-1 [&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none]">
				<div className="mb-1 text-navy text-1xl font-semibold">Core Faculty per College</div>

				<div className="flex items-center justify-between mb-3 gap-4">
					<div className="flex items-center gap-2 text-sm">
						<span>Show</span>
						<div className="flex items-stretch border border-gray-300 rounded overflow-hidden">
							<input type="number" min="1" className="w-16 px-2 outline-none text-center" value={entries} onChange={e => setEntries(e.target.value)} />
							<div className="flex flex-col">
								<button type="button" aria-label="Increase" className="px-2 border-l border-b border-gray-300 hover:bg-gray-100" onClick={() => setEntries(prev => Number(prev || 0) + 1)}>▲</button>
								<button type="button" aria-label="Decrease" className="px-2 border-l border-gray-300 hover:bg-gray-100" onClick={() => setEntries(prev => Math.max(1, Number(prev || 0) - 1))}>▼</button>
							</div>
						</div>
						<span>entries</span>
					</div>
					<input className="w-full max-w-sm px-3 py-2 rounded-full border" placeholder="Search: Instructor" value={q} onChange={e => setQ(e.target.value)} />
				</div>
				<div className="overflow-x-auto space-y-4">
					{grouped.length === 0 && (
						<div className="text-center text-gray-400 py-10">No records found</div>
					)}
					{grouped.map(({ college, programs, uniqueCount }) => (
						<div key={college?.id || 'unassigned'} className="border border-gray-300 rounded-lg overflow-hidden">
							{/* College header — click to expand/collapse */}
							{(() => {
								const collegeKey = String(college?.id || 'unassigned')
								const collegeExpanded = expandedColleges.has(collegeKey)
								return (<>
								<button
									type="button"
									onClick={() => toggleCollege(collegeKey)}
									className="w-full bg-navy/90 hover:bg-navy text-white px-4 py-2 font-semibold text-sm flex items-center gap-2 text-left transition-colors"
								>
									<svg className="w-4 h-4 opacity-70" viewBox="0 0 24 24" fill="currentColor"><path d="M12 3L1 9l4 2.18v6L12 21l7-3.82v-6l2-1.09V17h2V9L12 3zm6.82 6L12 12.72 5.18 9 12 5.28 18.82 9zM17 15.99l-5 2.73-5-2.73v-3.72L12 15l5-2.73v3.72z" /></svg>
									<span>{college?.code || 'Unassigned'}</span>
									{college && <span className="font-normal opacity-70">— {college.description}</span>}
									<span className="ml-auto text-xs opacity-60">{uniqueCount} instructor{uniqueCount !== 1 ? 's' : ''}</span>
									<svg
										className={`w-4 h-4 opacity-60 transition-transform duration-200 ${collegeExpanded ? 'rotate-180' : ''}`}
										viewBox="0 0 20 20" fill="currentColor"
									><path fillRule="evenodd" d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" clipRule="evenodd"/></svg>
								</button>
								{/* Program sub-groups — only when college expanded */}
								{collegeExpanded && programs.map(({ program, entries }) => {
									const progKey = `${collegeKey}-${program?.id || 'noprog'}`
									const progExpanded = expandedPrograms.has(progKey)
									return (
									<div key={program?.id || '__none'}>
										{/* Program sub-header — click to expand/collapse */}
										<button
											type="button"
											onClick={() => toggleProgram(progKey)}
											className="w-full flex items-center gap-2 px-4 py-1.5 bg-blue-50 hover:bg-blue-100 border-b border-blue-100 text-left transition-colors"
										>
											<svg className="w-3 h-3 text-blue-400 shrink-0" viewBox="0 0 20 20" fill="currentColor"><path d="M10.394 2.08a1 1 0 00-.788 0l-7 3a1 1 0 000 1.84L5.25 8.051a.999.999 0 01.356-.257l4-1.714a1 1 0 11.788 1.838L7.667 9.088l1.94.831a1 1 0 00.787 0l7-3a1 1 0 000-1.838l-7-3zM3.31 9.397L5 10.12v4.102a8.969 8.969 0 00-1.05-.174 1 1 0 01-.89-.89 11.115 11.115 0 01.25-3.762zM9.3 16.573A9.026 9.026 0 007 14.935v-3.957l1.818.778a3 3 0 002.364 0l5.508-2.361a11.026 11.026 0 01.25 3.762 1 1 0 01-.89.89 8.968 8.968 0 00-5.35 2.524 1 1 0 01-1.4 0zM6 18a1 1 0 001-1v-2.065a8.935 8.935 0 00-2-.712V17a1 1 0 001 1z"/></svg>
											<span className="text-xs font-bold text-blue-700">{program ? program.code : 'No Program'}</span>
											{program?.major && <span className="text-[10px] text-blue-500">({program.major})</span>}
											{program?.description && <span className="text-[10px] text-blue-400 font-normal truncate">{program.description}</span>}
											<span className="ml-auto text-[10px] text-blue-400 shrink-0">{entries.length} instructor{entries.length !== 1 ? 's' : ''}</span>
											<svg
												className={`w-3 h-3 text-blue-400 transition-transform duration-200 ${progExpanded ? 'rotate-180' : ''}`}
												viewBox="0 0 20 20" fill="currentColor"
											><path fillRule="evenodd" d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" clipRule="evenodd"/></svg>
										</button>
										{/* Table — only shown when program expanded */}
										{progExpanded && <table className="min-w-full text-sm">
										<thead>
											<tr className="bg-gray-100 border-b border-gray-300">
												<th className="text-left px-3 py-1.5 w-12 text-gray-500 text-xs font-medium">#</th>
												<th className="text-left px-3 py-1.5 text-gray-500 text-xs font-medium">Instructor</th>
												<th className="text-left px-3 py-1.5 text-gray-500 text-xs font-medium">Designation</th>
												<th className="text-left px-3 py-1.5 text-gray-500 text-xs font-medium">Role in Program</th>
												<th className="text-left px-3 py-1.5 text-gray-500 text-xs font-medium">Specialization</th>
												<th className="text-center px-3 py-1.5 w-20 text-gray-500 text-xs font-medium">Status</th>
												<th className="text-center px-3 py-1.5 w-28 text-gray-500 text-xs font-medium">Action</th>
											</tr>
										</thead>
										<tbody className="divide-y divide-gray-200">
											{entries.map(({ it, isLinked }, idx) => {
											const fName = it.first_name || it.firstName || ''
											const mName = it.middle_name || it.middleName || ''
											const lName = it.last_name || it.lastName || ''
											const fullName = `${fName} ${mName ? mName + ' ' : ''}${lName}`.trim()
											const specializationText = it.assignable_courses || it.assignableCourses || ''
											// Program badges
											const homeCourse = it.home_course_id ? courseById[it.home_course_id] : null
											const linkedIds = (it.linked_course_ids || '').split(',').map(s => s.trim()).filter(Boolean)
											const linkedCourseList = linkedIds.map(id => courseById[parseInt(id)]).filter(Boolean)
											return (
												<tr key={`${it.id}-${program?.id || 'none'}`} className={idx % 2 ? 'bg-gray-50/50' : ''}>
													<td className="px-3 py-2 text-gray-400 text-xs">{idx + 1}</td>
												<td className="px-3 py-2 font-medium">{fullName || 'N/A'}</td>
												<td className="px-3 py-2">
													{it.designation
														? <span className="inline-block bg-amber-50 text-amber-700 text-xs px-2 py-0.5 rounded-full font-medium">{it.designation}</span>
														: <span className="text-gray-300">—</span>
													}
												</td>
													<td className="px-3 py-2">
														{/* Show whether this instructor appears here via home or link */}
														{isLinked ? (
															<span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-violet-100 text-violet-700 border border-violet-200">
																<svg className="w-2.5 h-2.5" viewBox="0 0 20 20" fill="currentColor"><path fillRule="evenodd" d="M12.586 4.586a2 2 0 112.828 2.828l-3 3a2 2 0 01-2.828 0 1 1 0 00-1.414 1.414 4 4 0 005.656 0l3-3a4 4 0 00-5.656-5.656l-1.5 1.5a1 1 0 101.414 1.414l1.5-1.5zm-5 5a2 2 0 012.828 0 1 1 0 101.414-1.414 4 4 0 00-5.656 0l-3 3a4 4 0 105.656 5.656l1.5-1.5a1 1 0 10-1.414-1.414l-1.5 1.5a2 2 0 11-2.828-2.828l3-3z" clipRule="evenodd"/></svg>
																linked from {homeCourse?.code || '—'}
															</span>
														) : homeCourse ? (
															<div className="flex flex-wrap items-center gap-1">
															<span
																className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold bg-blue-100 text-blue-800 border border-blue-200"
																title={homeCourse.major ? `${homeCourse.code} — ${homeCourse.description} (${homeCourse.major})` : `${homeCourse.code} — ${homeCourse.description}`}
															>
																<svg className="w-2.5 h-2.5" viewBox="0 0 20 20" fill="currentColor"><path d="M10.394 2.08a1 1 0 00-.788 0l-7 3a1 1 0 000 1.84L5.25 8.051a.999.999 0 01.356-.257l4-1.714a1 1 0 11.788 1.838L7.667 9.088l1.94.831a1 1 0 00.787 0l7-3a1 1 0 000-1.838l-7-3zM3.31 9.397L5 10.12v4.102a8.969 8.969 0 00-1.05-.174 1 1 0 01-.89-.89 11.115 11.115 0 01.25-3.762zM9.3 16.573A9.026 9.026 0 007 14.935v-3.957l1.818.778a3 3 0 002.364 0l5.508-2.361a11.026 11.026 0 01.25 3.762 1 1 0 01-.89.89 8.968 8.968 0 00-5.35 2.524 1 1 0 01-1.4 0zM6 18a1 1 0 001-1v-2.065a8.935 8.935 0 00-2-.712V17a1 1 0 001 1z"/></svg>
																{homeCourse.code}
																{homeCourse.major && <span className="text-blue-500 text-[9px] ml-0.5">({homeCourse.major})</span>}
															</span>
															{linkedCourseList.map(lc => (
																<span
																	key={lc.id}
																	title={lc.major ? `${lc.code} — ${lc.description} (${lc.major})` : `${lc.code} — ${lc.description}`}
																	className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded-full text-[10px] font-semibold bg-violet-100 text-violet-700 border border-violet-200"
																>
																	<svg className="w-2 h-2" viewBox="0 0 20 20" fill="currentColor"><path fillRule="evenodd" d="M12.586 4.586a2 2 0 112.828 2.828l-3 3a2 2 0 01-2.828 0 1 1 0 00-1.414 1.414 4 4 0 005.656 0l3-3a4 4 0 00-5.656-5.656l-1.5 1.5a1 1 0 101.414 1.414l1.5-1.5zm-5 5a2 2 0 012.828 0 1 1 0 101.414-1.414 4 4 0 00-5.656 0l-3 3a4 4 0 105.656 5.656l1.5-1.5a1 1 0 10-1.414-1.414l-1.5 1.5a2 2 0 11-2.828-2.828l3-3z" clipRule="evenodd"/></svg>
																	{lc.code}{lc.major && <span className="text-violet-400 ml-0.5">({lc.major})</span>}
																</span>
															))}
														</div>
														) : (
															<span className="text-gray-300 text-xs">No program set</span>
														)}
													</td>
												<td className="px-3 py-2 text-xs">
													{specializationText ? (
														<span className="text-gray-600">{specializationText}</span>
													) : (() => {
														// Suggest from home program
														const hc = homeCourse
														const hcKey = hc ? hc.code.trim().toUpperCase() : null
														const recs = hcKey ? (programRecommendedSubjects[hcKey] || []).slice(0, 6) : []
														return (
															<div>
																{recs.length > 0 ? (
																	<div className="flex flex-wrap gap-1 items-center">
																		<span className="text-[10px] text-amber-600 font-semibold flex items-center gap-0.5">
																			<svg className="w-3 h-3" viewBox="0 0 20 20" fill="currentColor"><path d="M11 3a1 1 0 10-2 0v1a1 1 0 102 0V3zM15.657 5.757a1 1 0 00-1.414-1.414l-.707.707a1 1 0 001.414 1.414l.707-.707zM18 10a1 1 0 01-1 1h-1a1 1 0 110-2h1a1 1 0 011 1zM5.05 6.464A1 1 0 106.464 5.05l-.707-.707a1 1 0 00-1.414 1.414l.707.707zM5 10a1 1 0 01-1 1H3a1 1 0 110-2h1a1 1 0 011 1zM8 16v-1h4v1a2 2 0 11-4 0zM12 14c.015-.18.028-.36.028-.54V11a4 4 0 10-8 0v2.46c0 .18.013.36.028.54H12z"/></svg>
																			Suggested
																		</span>
																		{recs.map(r => (
																			<button
																				key={r.code}
																				type="button"
																				title={`Add ${r.code} — ${r.description || ''}`}
																				className="px-1.5 py-0.5 rounded text-[10px] font-mono bg-amber-50 text-amber-700 border border-amber-200 hover:bg-amber-100 hover:border-amber-400 transition-colors"
																				onClick={() => openEdit(it)}
																			>
																				{r.code}
																			</button>
																		))}
																		{(programRecommendedSubjects[hcKey] || []).length > 6 && (
																			<span className="text-[10px] text-gray-400">+{(programRecommendedSubjects[hcKey] || []).length - 6} more</span>
																		)}
																	</div>
																) : (
																	<span className="text-gray-300">No subjects — <button type="button" className="underline text-blue-400 hover:text-blue-600" onClick={() => openEdit(it)}>assign</button></span>
																)}
															</div>
														)
													})()}
												</td>
												<td className="px-3 py-2 text-center">
													<button
														className={`inline-block px-2 py-0.5 rounded-full text-xs font-semibold cursor-pointer hover:opacity-80 ${it.is_active !== false ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
															}`}
														title={it.is_active !== false ? 'Click to deactivate' : 'Click to activate'}
														onClick={() => {
															const fn = `${it.first_name || ''} ${it.last_name || ''}`.trim()
															const newActive = it.is_active === false
															setConfirmDialog({
																open: true,
																title: newActive ? 'Activate Instructor' : 'Deactivate Instructor',
																message: `Are you sure you want to ${newActive ? 'activate' : 'deactivate'} "${fn}"?`,
																confirmText: newActive ? 'Activate' : 'Deactivate',
																variant: 'warning',
																onConfirm: async () => {
																	setConfirmDialog({ open: false })
																	try {
																		await upsert('instructor', { id: it.id, is_active: newActive })
																		await load(true)
																	} catch (err) { alert(err.message || 'Failed to toggle status') }
																},
															})
														}}
													>
														{it.is_active !== false ? 'Active' : 'Inactive'}
													</button>
												</td>
												<td className="px-3 py-2 space-x-2 text-center">
													<button className="inline-flex items-center justify-center w-7 h-7 rounded-full bg-blue-600 hover:opacity-90" title="Edit" onClick={() => openEdit(it)}>
														<img src="/assets/edit.png" alt="Edit" className="w-3.5 h-3.5 object-contain" onError={(e) => { e.currentTarget.style.display = 'none' }} />
													</button>
													<button className="inline-flex items-center justify-center w-7 h-7 rounded-full bg-red-600 hover:opacity-90" title="Delete" onClick={() => onDelete(it.id)}>
														<img src="/assets/delete.png" alt="Delete" className="w-3.5 h-3.5 object-contain" onError={(e) => { e.currentTarget.style.display = 'none' }} />
													</button>
												</td>
												</tr>
											)
												})}
											</tbody>
										</table>}
									</div>
									)
								})}
								</>)
								})()
								}
						</div>
					))}
				</div>
			</div>

			{show && (
				<div className="fixed inset-0 bg-black/30 flex items-center justify-center p-4 z-50">
					<form onSubmit={onSave} className="w-full max-w-lg bg-white rounded-xl shadow-lg p-5 space-y-3 max-h-[90vh] overflow-y-auto">
						<div className="text-lg font-semibold text-navy">{editing ? 'Edit Instructor' : 'Add Instructor'}</div>
						<input className="w-full px-3 py-2 rounded border" placeholder="First Name" value={firstName} onChange={e => setFirstName(e.target.value)} />
						<input className="w-full px-3 py-2 rounded border" placeholder="Middle Name (optional)" value={middleName} onChange={e => setMiddleName(e.target.value)} />
						<input className="w-full px-3 py-2 rounded border" placeholder="Last Name" value={lastName} onChange={e => setLastName(e.target.value)} />
						<select className="w-full px-3 py-2 rounded border" value={employmentType} onChange={e => setEmploymentType(e.target.value)}>
							<option value="regular">Regular</option>
							<option value="visiting">Visiting Lecturer</option>
						</select>
						<select className="w-full px-3 py-2 rounded border" value={designation} onChange={e => setDesignation(e.target.value)}>
							<option value="">No designation</option>
							{designations.map(d => (
								<option key={d.id} value={d.designation.split(' ').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ')}>
									{d.designation.split(' ').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ')} (−{d.deduction_hours} hrs)
								</option>
							))}
						</select>
						<select className="w-full px-3 py-2 rounded border" value={collegeId} onChange={e => setCollegeId(e.target.value)}>
							<option value="">Select College (optional)</option>
							{colleges.map(c => <option key={c.id} value={c.id}>{c.code} — {c.description}</option>)}
						</select>

						{/* ── Program Assignment Section ── */}
						<div className="border border-blue-200 rounded-lg p-3 space-y-2 bg-blue-50/40">
							<div className="flex items-center gap-2">
								<svg className="w-4 h-4 text-blue-600" viewBox="0 0 20 20" fill="currentColor"><path d="M10.394 2.08a1 1 0 00-.788 0l-7 3a1 1 0 000 1.84L5.25 8.051a.999.999 0 01.356-.257l4-1.714a1 1 0 11.788 1.838L7.667 9.088l1.94.831a1 1 0 00.787 0l7-3a1 1 0 000-1.838l-7-3zM3.31 9.397L5 10.12v4.102a8.969 8.969 0 00-1.05-.174 1 1 0 01-.89-.89 11.115 11.115 0 01.25-3.762zM9.3 16.573A9.026 9.026 0 007 14.935v-3.957l1.818.778a3 3 0 002.364 0l5.508-2.361a11.026 11.026 0 01.25 3.762 1 1 0 01-.89.89 8.968 8.968 0 00-5.35 2.524 1 1 0 01-1.4 0zM6 18a1 1 0 001-1v-2.065a8.935 8.935 0 00-2-.712V17a1 1 0 001 1z"/></svg>
								<span className="text-sm font-semibold text-blue-800">Program Assignment</span>
							</div>

							{/* Home Program */}
							<div>
								<label className="block text-xs font-medium text-gray-600 mb-1">
									Home Program <span className="text-gray-400">(this instructor's primary program)</span>
								</label>
								<select
									className="w-full px-3 py-2 rounded border text-sm"
									value={homeCourseId}
									onChange={e => {
										setHomeCourseId(e.target.value)
										// Remove the newly chosen home from linked list to avoid duplication
										const newHomeId = e.target.value ? parseInt(e.target.value) : null
										if (newHomeId) setLinkedCourses(prev => prev.filter(c => c.id !== newHomeId))
									}}
								>
									<option value="">— No program assigned (unrestricted) —</option>
									{(courses || []).map(c => (
										<option key={c.id} value={c.id}>
											{c.code} — {c.description}{c.major ? ` (${c.major})` : ''}
										</option>
									))}
								</select>
								{homeCourseId && (() => {
									const hc = courseById[parseInt(homeCourseId)]
									const hcLabel = hc ? `${hc.code}${hc.major ? ` (${hc.major})` : ''}` : ''
									return (
										<p className="text-[10px] text-blue-600 mt-1">
											⚠ Scheduler will <strong>only</strong> assign this instructor to <strong>{hcLabel}</strong> subjects unless a cross-program link is added below.
										</p>
									)
								})()}
								{!homeCourseId && (
									<p className="text-[10px] text-gray-400 mt-1">
										No restriction — instructor can be assigned to any program's subjects (legacy behaviour).
									</p>
								)}
							</div>

							{/* Linked Programs */}
							<div>
								<label className="block text-xs font-medium text-gray-600 mb-1">
									Linked Programs <span className="text-gray-400">(cross-program teaching authorization)</span>
								</label>
								{linkedCourses.length > 0 && (
									<div className="flex flex-wrap gap-1 mb-2">
										{linkedCourses.map(c => (
											<button
												key={c.id}
												type="button"
												onClick={() => removeLinkedCourse(c.id)}
												title={c.major ? `${c.code} — ${c.description} (${c.major})` : `${c.code} — ${c.description}`}
												className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-violet-600 text-white text-xs hover:bg-violet-700"
											>
												<svg className="w-2.5 h-2.5" viewBox="0 0 20 20" fill="currentColor"><path fillRule="evenodd" d="M12.586 4.586a2 2 0 112.828 2.828l-3 3a2 2 0 01-2.828 0 1 1 0 00-1.414 1.414 4 4 0 005.656 0l3-3a4 4 0 00-5.656-5.656l-1.5 1.5a1 1 0 101.414 1.414l1.5-1.5zm-5 5a2 2 0 012.828 0 1 1 0 101.414-1.414 4 4 0 00-5.656 0l-3 3a4 4 0 105.656 5.656l1.5-1.5a1 1 0 10-1.414-1.414l-1.5 1.5a2 2 0 11-2.828-2.828l3-3z" clipRule="evenodd"/></svg>
												{c.code}{c.major && <span className="text-white/70 text-[9px] ml-0.5">({c.major})</span>}
												<span className="text-white/70 text-[10px]">✕</span>
											</button>
										))}
									</div>
								)}
								<input
									className="w-full px-3 py-2 rounded border text-sm"
									placeholder="Search program to link (e.g. BSCS)…"
									value={linkedCourseSearch}
									onChange={e => setLinkedCourseSearch(e.target.value)}
									disabled={!homeCourseId}
								/>
								{!homeCourseId && (
									<p className="text-[10px] text-gray-400 mt-1">Set a Home Program first to add cross-program links.</p>
								)}
								{homeCourseId && linkedCourseOptions.length > 0 && (
									<div className="max-h-32 overflow-auto border rounded mt-1 bg-white">
										{linkedCourseOptions.map(c => (
											<button
												key={c.id}
												type="button"
												className="w-full text-left px-3 py-2 text-xs hover:bg-violet-50 border-b last:border-b-0 border-gray-100 flex items-center gap-2"
												onClick={() => addLinkedCourse(c)}
											>
											<svg className="w-3 h-3 text-violet-500" viewBox="0 0 20 20" fill="currentColor"><path fillRule="evenodd" d="M12.586 4.586a2 2 0 112.828 2.828l-3 3a2 2 0 01-2.828 0 1 1 0 00-1.414 1.414 4 4 0 005.656 0l3-3a4 4 0 00-5.656-5.656l-1.5 1.5a1 1 0 101.414 1.414l1.5-1.5zm-5 5a2 2 0 012.828 0 1 1 0 101.414-1.414 4 4 0 00-5.656 0l-3 3a4 4 0 105.656 5.656l1.5-1.5a1 1 0 10-1.414-1.414l-1.5 1.5a2 2 0 11-2.828-2.828l3-3z" clipRule="evenodd"/></svg>
												<span className="font-semibold">{c.code}</span>
												<span className="text-gray-400 truncate">{c.description}{c.major ? <span className="text-violet-400 ml-1">({c.major})</span> : ''}</span>
											</button>
										))}
									</div>
								)}
							</div>
						</div>

						{/* Specialization (subjects) */}
						<div className="space-y-2">
							<div className="text-sm font-medium text-navy">Specialization (subjects)</div>

							{/* Staffing-caps coverage panel — persists, collapsible */}
							{homeCourseId && (() => {
								const hc = courseById[parseInt(homeCourseId)]
								const hcKey = hc ? hc.code.trim().toUpperCase() : null
								if (!hcKey) return null
								const recs = (programRecommendedSubjects[hcKey] || [])
									.filter(r => !isExemptSubject(r.code.trim().toUpperCase().replace(/\s+/g, ' ')))
									.map(r => ({
										...r,
										coverage: ((subjectCoverageMap[hcKey] || {})[r.code.trim().toUpperCase().replace(/\s+/g, ' ')] || 0),
									})).sort((a, b) => a.coverage - b.coverage)
								if (!recs.length) return null
								const critical = recs.filter(r => r.coverage === 0)
								const MAX_VISIBLE_COVERAGE = Math.max(...recs.map(r => r.coverage), 2)
								return (
									<div className="border border-slate-200 rounded-lg bg-slate-50/60">
										{/* Header — always visible, click to toggle */}
										<button
											type="button"
											onClick={() => setCoveragePanelCollapsed(p => !p)}
											className="w-full flex items-center gap-2 px-3 py-2 hover:bg-slate-100/80 rounded-lg transition-colors"
										>
											<svg className="w-3.5 h-3.5 text-slate-500 shrink-0" viewBox="0 0 20 20" fill="currentColor"><path d="M9 6a3 3 0 11-6 0 3 3 0 016 0zM17 6a3 3 0 11-6 0 3 3 0 016 0zM12.93 17c.046-.327.07-.66.07-1a6.97 6.97 0 00-1.5-4.33A5 5 0 0119 16v1h-6.07zM6 11a5 5 0 015 5v1H1v-1a5 5 0 015-5z"/></svg>
											<span className="text-xs font-semibold text-slate-700">Staffing coverage — {hc?.code}{hc?.major ? ` (${hc.major})` : ''}</span>
											<span className="text-[10px] text-slate-400">{recs.length} subjects</span>
											{critical.length > 0 && (
												<span className="text-[10px] font-bold text-red-600 bg-red-50 border border-red-200 px-1.5 py-0.5 rounded-full">
													{critical.length} critical
												</span>
											)}
											{/* Chevron */}
											<svg
												className="w-3.5 h-3.5 text-slate-400 ml-auto shrink-0 transition-transform duration-200"
												style={{ transform: coveragePanelCollapsed ? 'rotate(-90deg)' : 'rotate(0deg)' }}
												viewBox="0 0 20 20" fill="currentColor"
											>
												<path fillRule="evenodd" d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" clipRule="evenodd" />
											</svg>
										</button>
										{/* Collapsible body */}
										{!coveragePanelCollapsed && (
											<div className="px-3 pb-3 space-y-2">
												{/* Action + legend row */}
												<div className="flex items-center gap-3 flex-wrap">
													{critical.length > 0 && (
														<button
															type="button"
															onClick={() => critical.forEach(r => addSpecialization(r.code))}
															className="text-[10px] px-2 py-0.5 rounded bg-red-500 text-white hover:bg-red-600 font-semibold"
														>Add {critical.length} critical</button>
													)}
													<div className="flex items-center gap-3 text-[10px] text-slate-400 ml-auto">
														<span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-red-400 inline-block"/>0 = critical</span>
														<span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-amber-400 inline-block"/>1 = solo risk</span>
														<span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-emerald-400 inline-block"/>2+ = ok</span>
													</div>
												</div>
												{/* Subject cards */}
												<div className="max-h-52 overflow-y-auto pr-1 space-y-1.5 [&::-webkit-scrollbar]:hidden">
													{recs.map(r => {
														const cov = r.coverage
														const isAlreadyAdded = specialization.includes(r.code)
														const cardBg     = cov === 0 ? '#fef2f2' : cov === 1 ? '#fffbeb' : '#f0fdf4'
														const cardBorder = cov === 0 ? '#fecaca' : cov === 1 ? '#fde68a' : '#bbf7d0'
														const barColor   = cov === 0 ? '#f87171' : cov === 1 ? '#fbbf24' : '#34d399'
														const labelColor = cov === 0 ? '#b91c1c' : cov === 1 ? '#92400e' : '#065f46'
														const barPct     = Math.min(100, Math.round((cov / MAX_VISIBLE_COVERAGE) * 100))
														return (
															<button
																key={r.code}
																type="button"
																disabled={isAlreadyAdded}
																onClick={() => addSpecialization(r.code)}
																className="w-full text-left disabled:opacity-50"
																style={{ borderRadius: '0.5rem', border: `1px solid ${cardBorder}`, padding: '0.5rem 0.625rem', backgroundColor: cardBg, cursor: isAlreadyAdded ? 'default' : 'pointer' }}
															>
																<div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '3px' }}>
																	<div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
																		<span style={{ fontSize: '0.75rem', fontWeight: 700, color: labelColor }}>{r.code}</span>
																		{r.semester && (
																			<span style={{ fontSize: '0.5625rem', fontWeight: 600, padding: '1px 4px', borderRadius: '9999px', backgroundColor: r.semester === 1 ? '#e0e7ff' : '#ccfbf1', color: r.semester === 1 ? '#4338ca' : '#0f766e' }}>S{r.semester}</span>
																		)}
																		{r.year_level && <span style={{ fontSize: '0.5625rem', color: '#9ca3af' }}>Yr {r.year_level}</span>}
																	</div>
																	<span style={{ fontSize: '0.625rem', fontWeight: 600, color: labelColor }}>
																		{cov === 0 ? 'No instructor' : `${cov} instructor${cov > 1 ? 's' : ''}`}
																	</span>
																</div>
																{r.description && <div style={{ fontSize: '0.5625rem', color: '#6b7280', marginBottom: '4px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{r.description}</div>}
																<div style={{ height: '5px', backgroundColor: '#e5e7eb', borderRadius: '9999px', overflow: 'hidden' }}>
																	<div style={{ height: '100%', backgroundColor: barColor, width: `${barPct}%`, transition: 'width 0.4s ease' }} />
																</div>
																{isAlreadyAdded && <div style={{ fontSize: '0.5rem', color: '#6b7280', marginTop: '2px' }}>✓ Added to specialization</div>}
															</button>
														)
													})}
												</div>
											</div>
										)}
									</div>
								)
							})()}

							<input
								className="w-full px-3 py-2 rounded border"
								placeholder="Search subject code or description"
								value={specializationSearch}
								onChange={e => setSpecializationSearch(e.target.value)}
							/>
							{specialization.length > 0 && (
								<>
								<div className="flex flex-wrap gap-2 mt-1">
									{specialization.map(code => {
										const sem = getSubjectSem(code)
										const vCount = getVariantCount(code)
										const norm = code.trim().toUpperCase().replace(/\s+/g, ' ')
										const group = subjectVariantsMap[norm]
										const tooltip = group?.variants?.map(v => `${v.description} (${v.type} ${v.unit}u)`).join('\n') || ''
										const isMismatch = mismatchedSpecs.has(code)
										const hcObj = homeCourseId ? courseById[parseInt(homeCourseId)] : null
										const homeCourseName = hcObj ? `${hcObj.code}${hcObj.major ? ` (${hcObj.major})` : ''}` : ''
										return (
											<button
												key={code}
												type="button"
												className={`px-2 py-1 rounded-full text-white text-xs flex items-center gap-1 ${
													isMismatch
														? 'bg-amber-500 ring-2 ring-amber-300'
														: 'bg-royal'
												}`}
												onClick={() => removeSpecialization(code)}
												title={
													isMismatch
														? `⚠ ${code} is not in ${homeCourseName}'s curriculum. The scheduler will still use this specialization if the instructor is linked to the correct program.\n\n${vCount > 1 ? `Matches ${vCount} subjects:\n${tooltip}` : tooltip}`
														: (vCount > 1 ? `Matches ${vCount} subjects:\n${tooltip}` : tooltip)
												}
											>
												{isMismatch && <span className="text-[10px]">⚠</span>}
												<span>{code}</span>
												{vCount > 1 && <span className="text-[9px] font-bold px-1 py-px rounded bg-amber-400 text-amber-900">×{vCount}</span>}
												<span className={`text-[9px] font-bold px-1 py-px rounded ${sem.color}`}>{sem.label}</span>
												<span className="text-white/80 text-[10px]">✕</span>
											</button>
										)
									})}
								</div>
								{/* Mismatch warning banner — reactive, updates when Home Program changes */}
								{mismatchedSpecs.size > 0 && homeCourseId && (() => {
									const hcObj = courseById[parseInt(homeCourseId)]
									const hcLabel = hcObj
										? `${hcObj.code}${hcObj.major ? ` (${hcObj.major})` : ''}`
										: '(unknown program)'
									// Map each mismatched code to the programs that own it
									const mismatchDetails = [...mismatchedSpecs].map(code => {
										const norm = code.trim().toUpperCase().replace(/\s+/g, ' ')
										const ownerKeys = Object.entries(courseSubjectCodeSet)
											.filter(([ck, cset]) => ck !== '__shared' && cset instanceof Set && cset.has(norm))
											.map(([ck]) => ck)
										return { code, ownerKeys }
									})
									return (
										<div className="mt-2 rounded-lg border border-amber-300 bg-amber-50 text-xs overflow-hidden">
											{/* Header */}
											<div className="flex gap-2 px-3 py-2 items-start">
												<span className="text-amber-500 text-base leading-none mt-0.5 shrink-0">⚠</span>
												<div className="min-w-0 flex-1">
													<span className="font-semibold text-amber-800">Program mismatch</span>
													<span className="text-amber-700"> — subject{mismatchedSpecs.size > 1 ? 's' : ''} not in </span>
													<span className="font-bold text-amber-900 bg-amber-200/70 px-1.5 py-0.5 rounded">{hcLabel}</span>
													<span className="text-amber-700">'s curriculum:</span>
												</div>
											</div>
											{/* Per-subject breakdown */}
											<div className="border-t border-amber-200 divide-y divide-amber-100">
												{mismatchDetails.map(({ code, ownerKeys }) => (
													<div key={code} className="flex items-center gap-2 px-3 py-1.5 flex-wrap">
														<span className="font-mono font-bold text-amber-900">{code}</span>
														<span className="text-amber-400 text-[10px]">→ belongs to</span>
														{ownerKeys.length > 0
															? ownerKeys.map(k => (
																<span key={k} className="text-[10px] font-semibold px-1.5 py-0.5 rounded-full bg-violet-100 text-violet-700 border border-violet-200">{k}</span>
															))
															: <span className="text-[10px] text-amber-400 italic">no program in DB</span>
														}
													</div>
												))}
											</div>
											{/* Footer */}
											<div className="border-t border-amber-200 px-3 py-1.5 text-amber-600">
												Add those programs as <strong>Linked Programs</strong> below to authorize the scheduler to use these subjects.
											</div>
										</div>
									)
								})()	}
								{/* Semester balance summary */}
								{(() => {
									const s1 = specialization.filter(c => { const s = getSubjectSem(c); return s.label === 'S1' || s.label === 'S1+S2' }).length
									const s2 = specialization.filter(c => { const s = getSubjectSem(c); return s.label === 'S2' || s.label === 'S1+S2' }).length
									const unmatched = specialization.filter(c => getSubjectSem(c).label === '?').length
									const maxS = Math.max(s1, s2, 1)
									const isLopsided = (s1 > 0 && s2 === 0) || (s2 > 0 && s1 === 0)
									return (
										<div className={`mt-2 p-2 rounded-lg border text-xs ${isLopsided ? 'bg-amber-50 border-amber-200' : 'bg-slate-50 border-slate-200'}`}>
											<div className="flex items-center gap-3 mb-1">
												<span className="font-bold text-slate-500">Semester Balance</span>
												{isLopsided && <span className="text-[10px] text-amber-600 font-bold">⚠ Lopsided</span>}
											</div>
											<div className="flex items-center gap-2">
												<span className="text-[10px] font-bold text-indigo-600 w-5">S1</span>
												<div className="flex-1 bg-slate-200 rounded-full h-2 overflow-hidden">
													<div className="h-2 rounded-full bg-indigo-500 transition-all" style={{width: `${(s1 / maxS) * 100}%`}}></div>
												</div>
												<span className="font-bold text-slate-700 w-4 text-right">{s1}</span>
												<span className="text-[10px] font-bold text-teal-600 w-5 ml-2">S2</span>
												<div className="flex-1 bg-slate-200 rounded-full h-2 overflow-hidden">
													<div className="h-2 rounded-full bg-teal-500 transition-all" style={{width: `${(s2 / maxS) * 100}%`}}></div>
												</div>
												<span className="font-bold text-slate-700 w-4 text-right">{s2}</span>
											</div>
											{unmatched > 0 && <div className="text-[10px] text-rose-500 mt-1">⚠ {unmatched} subject(s) not found in database</div>}
										</div>
									)
								})()}
								</>
							)}
							<div className="max-h-40 overflow-auto border rounded mt-1 bg-gray-50">
								{subjectOptions.length === 0 && (
									<div className="px-3 py-2 text-xs text-gray-500">No matching subjects</div>
								)}
								{subjectOptions.map(s => {
									const sem = getSubjectSem(s.code)
									const norm = s.code.trim().toUpperCase().replace(/\s+/g, ' ')
									const group = subjectVariantsMap[norm]
									const variants = group?.variants || [{ description: s.description, type: s.type, unit: s.unit }]
									return (
										<button
											key={s.id}
											type="button"
											className="w-full text-left px-3 py-2 text-xs hover:bg-royal/10 border-b last:border-b-0 border-gray-200"
											onClick={() => addSpecialization(s.code)}
										>
											<div className="flex items-center gap-2">
												<span className="font-semibold">{s.code}</span>
												<span className={`text-[9px] font-bold px-1 py-px rounded ${sem.color}`}>{sem.label}</span>
												{variants.length > 1 && <span className="text-[9px] font-bold px-1 py-px rounded bg-amber-100 text-amber-700">{variants.length} subjects</span>}
											</div>
											{variants.map((v, vi) => (
												<div key={vi} className="text-[10px] text-gray-500 pl-1 mt-0.5 flex items-center gap-1">
													<span className="text-[9px] font-bold text-slate-400">{v.type}</span>
													<span className="text-[9px] text-slate-400">{v.unit}u</span>
													<span className="truncate">{v.description}</span>
												</div>
											))}
										</button>
									)
								})}
							</div>
						</div>

						{error && <div className="text-sm text-red-600">{error}</div>}
						<div className="flex justify-end gap-2 pt-2">
							<button type="button" className="px-3 py-2 rounded border" onClick={() => setShow(false)} disabled={processing}>Cancel</button>
							<button className="px-3 py-2 rounded bg-royal text-white disabled:opacity-60" disabled={processing}>Save</button>
						</div>
					</form>
				</div>
			)}

			<ConfirmDialog
				{...confirmDialog}
				onCancel={() => setConfirmDialog({ open: false })}
			/>
		</div>
	)
}
