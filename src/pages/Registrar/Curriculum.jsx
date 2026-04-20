import { useState, useEffect, useRef, useCallback } from 'react';
import { list } from '../../store/db';
import ConfirmDialog from '../../components/ConfirmDialog';
import * as pdfjsLib from 'pdfjs-dist';
import pdfjsWorker from 'pdfjs-dist/build/pdf.worker.min.mjs?url';

pdfjsLib.GlobalWorkerOptions.workerSrc = pdfjsWorker;

// ─── Reusable PDF Viewer component ──────────────────────────────────────────
// Accepts either a File object or a URL string via `fileOrUrl` prop.
function PdfViewer({ fileOrUrl, containerRef, onScroll }) {
    const [pdfDoc, setPdfDoc] = useState(null);
    const [pageInfos, setPageInfos] = useState([]);
    const [zoom, setZoom] = useState(1.0);
    const renderedPages = useRef(new Set());
    const observerRef = useRef(null);
    const innerRef = useRef(null);
    const blobUrlRef = useRef(null);   // track blob URLs we create for cleanup

    const setRefs = useCallback((el) => {
        innerRef.current = el;
        if (containerRef) containerRef.current = el;
    }, [containerRef]);

    // Load PDF from either a File object or a URL string
    useEffect(() => {
        if (!fileOrUrl) return;
        let cancelled = false;
        setPdfDoc(null);
        setPageInfos([]);
        renderedPages.current = new Set();

        async function loadPdf() {
            try {
                let source;
                if (typeof fileOrUrl === 'string') {
                    // URL: pass directly to pdf.js (it will fetch it)
                    source = { url: fileOrUrl };
                } else {
                    // File object: read as ArrayBuffer
                    const arrayBuffer = await fileOrUrl.arrayBuffer();
                    source = { data: arrayBuffer };
                }
                const pdf = await pdfjsLib.getDocument(source).promise;
                if (cancelled) return;
                setPdfDoc(pdf);

                const infos = [];
                for (let i = 1; i <= pdf.numPages; i++) {
                    const page = await pdf.getPage(i);
                    const vp = page.getViewport({ scale: 1 });
                    infos.push({ pageNum: i, width: vp.width, height: vp.height });
                }
                if (!cancelled) setPageInfos(infos);
            } catch (err) {
                console.error('PDF load error:', err);
            }
        }

        loadPdf();
        return () => {
            cancelled = true;
            // Clean up any blob URL we created
            if (blobUrlRef.current) {
                URL.revokeObjectURL(blobUrlRef.current);
                blobUrlRef.current = null;
            }
        };
    }, [fileOrUrl]);

    // Core page-render function (DPR-aware for sharp text)
    const renderPage = useCallback(async (idx, doc, infos, currentZoom, container) => {
        if (!doc || !infos[idx]) return;
        const canvas = container.querySelector(`#pdf-cv-${idx}`);
        if (!canvas) return;

        const page = await doc.getPage(infos[idx].pageNum);
        const DPR = window.devicePixelRatio || 1;
        const containerWidth = container.clientWidth - 32; // 16px padding each side
        const baseScale = containerWidth / infos[idx].width;
        const finalScale = baseScale * currentZoom * DPR;

        const scaledVp = page.getViewport({ scale: finalScale });

        // Physical pixels = sharp; CSS size via style keeps layout correct
        canvas.width = scaledVp.width;
        canvas.height = scaledVp.height;
        canvas.style.width = `${scaledVp.width / DPR}px`;
        canvas.style.height = `${scaledVp.height / DPR}px`;

        const ctx = canvas.getContext('2d');
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        await page.render({ canvasContext: ctx, viewport: scaledVp }).promise;
    }, []);

    // Set up IntersectionObserver after doc + infos are ready
    useEffect(() => {
        if (!pdfDoc || pageInfos.length === 0 || !innerRef.current) return;

        if (observerRef.current) observerRef.current.disconnect();
        renderedPages.current = new Set();

        const container = innerRef.current;

        async function lazyRender(idx) {
            if (renderedPages.current.has(idx)) return;
            renderedPages.current.add(idx);
            await renderPage(idx, pdfDoc, pageInfos, zoom, container);
        }

        // First page immediately
        lazyRender(0);

        const observer = new IntersectionObserver(
            (entries) => {
                entries.forEach(entry => {
                    if (entry.isIntersecting) {
                        lazyRender(Number(entry.target.dataset.pageIdx));
                    }
                });
            },
            { root: container, rootMargin: '300px 0px' }
        );
        observerRef.current = observer;
        container.querySelectorAll('[data-page-idx]').forEach(el => observer.observe(el));

        return () => observer.disconnect();
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [pdfDoc, pageInfos]);

    // Re-render visible pages when zoom changes
    useEffect(() => {
        if (!pdfDoc || pageInfos.length === 0 || !innerRef.current) return;
        const container = innerRef.current;
        renderedPages.current = new Set();

        async function reRenderVisible() {
            const containerRect = container.getBoundingClientRect();
            const wrappers = container.querySelectorAll('[data-page-idx]');
            for (const wrapper of wrappers) {
                const rect = wrapper.getBoundingClientRect();
                if (rect.bottom > containerRect.top - 400 && rect.top < containerRect.bottom + 400) {
                    const idx = Number(wrapper.dataset.pageIdx);
                    if (renderedPages.current.has(idx)) continue;
                    renderedPages.current.add(idx);
                    await renderPage(idx, pdfDoc, pageInfos, zoom, container);
                }
            }
        }

        const timer = setTimeout(reRenderVisible, 80);
        return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [zoom]);

    const zoomIn  = () => setZoom(z => Math.min(z + 0.25, 4));
    const zoomOut = () => setZoom(z => Math.max(z - 0.25, 0.5));
    const zoomReset = () => setZoom(1.0);

    return (
        <div className="flex flex-col h-full bg-gray-800">
            {/* Toolbar */}
            <div className="flex-shrink-0 flex items-center gap-2 px-4 py-2 bg-gray-900/80 border-b border-gray-700">
                <svg className="h-4 w-4 text-red-400 flex-shrink-0" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8l-6-6zm-1 2l5 5h-5V4z"/>
                </svg>
                <span className="text-white font-bold text-sm tracking-wide">PDF Preview</span>
                {pdfDoc && (
                    <span className="text-gray-400 text-xs ml-1">{pdfDoc.numPages} page{pdfDoc.numPages !== 1 ? 's' : ''}</span>
                )}

                {/* Zoom controls */}
                <div className="ml-auto flex items-center gap-1">
                    <button onClick={zoomOut}  title="Zoom Out"
                        className="w-7 h-7 flex items-center justify-center rounded bg-gray-700 hover:bg-gray-500 text-white text-lg font-bold transition-colors">−</button>
                    <button onClick={zoomReset} title="Reset Zoom"
                        className="px-2 h-7 flex items-center justify-center rounded bg-gray-700 hover:bg-gray-500 text-white text-xs font-bold transition-colors min-w-[3rem]">
                        {Math.round(zoom * 100)}%
                    </button>
                    <button onClick={zoomIn}   title="Zoom In"
                        className="w-7 h-7 flex items-center justify-center rounded bg-gray-700 hover:bg-gray-500 text-white text-lg font-bold transition-colors">+</button>
                </div>
            </div>

            {/* Scrollable pages */}
            <div
                ref={setRefs}
                className="flex-1 overflow-y-auto overflow-x-auto"
                style={{ scrollbarWidth: 'thin', scrollbarColor: '#555 #222', background: '#1f2937' }}
                onScroll={onScroll}
            >
                <div className="p-4 space-y-3">
                    {pageInfos.map((info, idx) => {
                        const cw = innerRef.current ? innerRef.current.clientWidth - 32 : 600;
                        const displayH = (info.height / info.width) * cw * zoom;
                        return (
                            <div
                                key={idx}
                                data-page-idx={idx}
                                style={{ minHeight: `${displayH}px` }}
                                className="relative shadow-2xl"
                            >
                                <canvas
                                    id={`pdf-cv-${idx}`}
                                    className="block bg-white rounded"
                                    style={{ display: 'block', maxWidth: '100%' }}
                                />
                            </div>
                        );
                    })}

                    {pageInfos.length === 0 && (
                        <div className="flex flex-col items-center justify-center h-64 gap-3 text-gray-400 font-sans text-sm">
                            <svg className="animate-spin h-6 w-6" viewBox="0 0 24 24">
                                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none"/>
                                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
                            </svg>
                            Loading PDF…
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}

// ─── Main Component ──────────────────────────────────────────────────────────
export default function Curriculum() {
    const [courses, setCourses] = useState([]);
    const [courseId, setCourseId] = useState('');
    const [file, setFile] = useState(null);         // File object for verify view
    const [pdfUrl, setPdfUrl] = useState(null);     // Server URL for display view (persists on refresh)
    const [subjects, setSubjects] = useState([]);

    // 'upload' | 'verify' | 'display'
    const [view, setView] = useState('upload');
    const [processing, setProcessing] = useState(false);
    const [message, setMessage] = useState('');
    const [error, setError] = useState('');
    const [confirmDialog, setConfirmDialog] = useState({ open: false });
    const [parsedSubjects, setParsedSubjects] = useState([]);

    // Split pane
    const [splitRatio, setSplitRatio] = useState(50);
    const splitContainerRef = useRef(null);
    const isDragging = useRef(false);

    // Scroll sync
    const leftPaneRef  = useRef(null);
    const rightPaneRef = useRef(null);   // PDF container inside verify view
    const displayPdfRef = useRef(null);  // PDF container inside display view
    const isScrollSyncing = useRef(false);

    useEffect(() => { loadCourses(); }, []);

    async function loadCourses() {
        try { setCourses(await list('course')); }
        catch (err) { console.error('Failed to load courses', err); }
    }

    async function onCourseSelect(e) {
        const id = e.target.value;
        setCourseId(id);
        setSubjects([]);
        setParsedSubjects([]);
        setView('upload');
        setMessage('');
        setError('');
        setFile(null);
        setPdfUrl(null);
        if (id) fetchCurriculum(id);
    }

    async function fetchCurriculum(id) {
        try {
            const res = await fetch(`http://localhost:8000/api/curriculum/${id}`);
            if (res.ok) {
                const data = await res.json();
                if (data && data.length > 0) {
                    setSubjects(data);
                    // Check if a PDF is stored on the server for this curriculum
                    const pdfRes = await fetch(`http://localhost:8000/api/curriculum/${id}/pdf`, { method: 'HEAD' });
                    if (pdfRes.ok) {
                        // Add a cache-buster so stale cached PDF doesn't show
                        setPdfUrl(`http://localhost:8000/api/curriculum/${id}/pdf?t=${Date.now()}`);
                    }
                    setView('display');
                }
            }
        } catch (err) { console.error(err); }
    }

    function onFileChange(e) {
        const selected = e.target.files[0] || null;
        setFile(selected);
        setParsedSubjects([]);
        setMessage('');
        setError('');
    }

    async function onVerify() {
        if (!file || !courseId) return;
        setProcessing(true);
        setError('');
        setMessage('');

        const formData = new FormData();
        formData.append('file', file);
        formData.append('course_id', courseId);

        try {
            const res = await fetch('http://localhost:8000/api/curriculum/parse', {
                method: 'POST', body: formData
            });
            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.detail || 'Parsing failed');
            }
            const data = await res.json();
            setParsedSubjects(data);
            setView('verify');
            setMessage('PDF parsed successfully. Review the data below, then click Upload to save.');
        } catch (err) {
            setError(err.message);
        } finally {
            setProcessing(false);
        }
    }

    async function onUpload() {
        if (!courseId || parsedSubjects.length === 0) return;
        setProcessing(true);
        setError('');

        try {
            // 1. Save curriculum subjects to DB
            const res = await fetch(`http://localhost:8000/api/curriculum/${courseId}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(parsedSubjects)
            });
            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.detail || 'Save failed');
            }
            const result = await res.json();

            // 2. Persist the PDF file on the server
            if (file) {
                const formData = new FormData();
                formData.append('file', file);
                await fetch(`http://localhost:8000/api/curriculum/${courseId}/pdf`, {
                    method: 'POST', body: formData
                });
                // Use a timestamped URL so the browser doesn't cache the old version
                setPdfUrl(`http://localhost:8000/api/curriculum/${courseId}/pdf?t=${Date.now()}`);
            }

            const parts = ['Curriculum Saved Successfully!'];
            if (result.subjects_created > 0) parts.push(`${result.subjects_created} subject(s) added`);
            if (result.subjects_updated > 0) parts.push(`${result.subjects_updated} subject(s) updated`);
            setMessage(parts.join(' — '));
            setParsedSubjects([]);
            setSubjects(parsedSubjects);
            setFile(null);
            setView('display');
        } catch (err) {
            setError(err.message);
        } finally {
            setProcessing(false);
        }
    }

    async function onDelete() {
        setConfirmDialog({
            open: true,
            title: 'Delete Curriculum',
            message: 'Are you sure you want to delete this curriculum? This action cannot be undone.',
            confirmText: 'Delete',
            variant: 'danger',
            onConfirm: async () => {
                setConfirmDialog({ open: false });
                setProcessing(true);
                try {
                    const res = await fetch(`http://localhost:8000/api/curriculum/${courseId}`, { method: 'DELETE' });
                    if (!res.ok) throw new Error('Delete failed');
                    setSubjects([]);
                    setFile(null);
                    setPdfUrl(null);
                    setView('upload');
                    setMessage('Curriculum Deleted.');
                } catch (err) {
                    setError(err.message);
                } finally {
                    setProcessing(false);
                }
            },
        });
    }

    // ─── Split-pane drag ────────────────────────────────────────────────────
    const onMouseDown = useCallback((e) => {
        e.preventDefault();
        isDragging.current = true;

        const onMouseMove = (ev) => {
            if (!isDragging.current || !splitContainerRef.current) return;
            const rect = splitContainerRef.current.getBoundingClientRect();
            const pct = Math.min(Math.max(((ev.clientX - rect.left) / rect.width) * 100, 20), 80);
            setSplitRatio(pct);
        };

        const onMouseUp = () => {
            isDragging.current = false;
            document.removeEventListener('mousemove', onMouseMove);
            document.removeEventListener('mouseup', onMouseUp);
            document.body.style.cursor = '';
            document.body.style.userSelect = '';
        };

        document.body.style.cursor = 'col-resize';
        document.body.style.userSelect = 'none';
        document.addEventListener('mousemove', onMouseMove);
        document.addEventListener('mouseup', onMouseUp);
    }, []);

    // ─── Scroll sync (verify view) ──────────────────────────────────────────
    const handleSyncScroll = useCallback((source) => {
        if (isScrollSyncing.current) return;
        isScrollSyncing.current = true;
        const srcEl = source === 'left' ? leftPaneRef.current : rightPaneRef.current;
        const tgtEl = source === 'left' ? rightPaneRef.current : leftPaneRef.current;
        if (srcEl && tgtEl) {
            const ratio = srcEl.scrollTop / (srcEl.scrollHeight - srcEl.clientHeight || 1);
            tgtEl.scrollTop = ratio * (tgtEl.scrollHeight - tgtEl.clientHeight);
        }
        requestAnimationFrame(() => { isScrollSyncing.current = false; });
    }, []);

    // ─── Parsed-data overview (verify left pane) ────────────────────────────
    const years = [1, 2, 3, 4];
    const yearLabels = { 1: 'FIRST YEAR', 2: 'SECOND YEAR', 3: 'THIRD YEAR', 4: 'FOURTH YEAR' };

    const renderParsedOverview = (data) => {
        const totalSubjects = data.filter(s => !s.is_exit_point).length;
        const totalUnits    = data.filter(s => !s.is_exit_point).reduce((s, x) => s + (Number(x.units) || 0), 0);
        const courseName    = courses.find(c => String(c.id) === String(courseId))?.description || '';

        return (
            <div
                ref={leftPaneRef}
                className="h-full overflow-y-auto bg-gray-50 font-sans"
                style={{ scrollbarWidth: 'thin' }}
                onScroll={() => handleSyncScroll('left')}
            >
                <div className="sticky top-0 z-10 bg-gradient-to-r from-navy to-royal px-5 py-3 shadow-lg">
                    <h2 className="text-white font-bold text-base tracking-wide">📋 Parsed Data Overview</h2>
                    <p className="text-blue-200 text-xs mt-0.5">{courseName}</p>
                </div>

                <div className="grid grid-cols-2 gap-3 p-4">
                    <div className="bg-white rounded-xl border border-gray-200 p-3 shadow-sm">
                        <div className="text-[10px] text-gray-400 uppercase tracking-wider font-bold">Total Subjects</div>
                        <div className="text-2xl font-black text-navy mt-1">{totalSubjects}</div>
                    </div>
                    <div className="bg-white rounded-xl border border-gray-200 p-3 shadow-sm">
                        <div className="text-[10px] text-gray-400 uppercase tracking-wider font-bold">Total Units</div>
                        <div className="text-2xl font-black text-royal mt-1">{totalUnits}</div>
                    </div>
                </div>

                <div className="px-4 pb-6 space-y-4">
                    {years.map(year => {
                        const yi = data.filter(s => s.year_level === year && !s.is_exit_point);
                        if (!yi.length) return null;
                        return (
                            <div key={year} className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
                                <div className="bg-gradient-to-r from-navy/90 to-royal/80 text-white px-4 py-2 font-bold text-sm tracking-widest uppercase">{yearLabels[year]}</div>
                                {[
                                    { label: '1st Semester', items: yi.filter(s => s.semester === 1) },
                                    { label: '2nd Semester', items: yi.filter(s => s.semester === 2) },
                                    { label: 'Summer',       items: yi.filter(s => s.semester === 3) },
                                ].filter(g => g.items.length > 0).map(({ label, items }) => (
                                    <div key={label} className="border-b border-gray-100 last:border-b-0">
                                        <div className="px-4 pt-3 pb-1 flex items-center justify-between">
                                            <span className="text-xs font-bold text-gray-500 uppercase tracking-wider">{label}</span>
                                            <span className="text-[10px] bg-royal/10 text-royal px-2 py-0.5 rounded-full font-bold">
                                                {items.length} subj · {items.reduce((s, i) => s + (Number(i.units) || 0), 0)} units
                                            </span>
                                        </div>
                                        <div className="px-4 pb-3">
                                            <table className="w-full text-[11px]">
                                                <thead>
                                                    <tr className="text-gray-400 uppercase text-[9px] tracking-wider">
                                                        <th className="text-left pb-1 w-[22%]">Code</th>
                                                        <th className="text-left pb-1">Description</th>
                                                        <th className="text-center pb-1 w-[10%]">Lec</th>
                                                        <th className="text-center pb-1 w-[10%]">Lab</th>
                                                        <th className="text-center pb-1 w-[10%]">Units</th>
                                                    </tr>
                                                </thead>
                                                <tbody>
                                                    {items.map((s, i) => (
                                                        <tr key={i} className="border-t border-gray-50 hover:bg-blue-50/40 transition-colors">
                                                            <td className="py-1.5 font-bold text-navy">{s.code}</td>
                                                            <td className="py-1.5 text-gray-700 leading-tight">{s.description}</td>
                                                            <td className="py-1.5 text-center text-gray-500">{s.lec_hours || '-'}</td>
                                                            <td className="py-1.5 text-center text-gray-500">{s.lab_hours || '-'}</td>
                                                            <td className="py-1.5 text-center font-bold text-navy">{s.units}</td>
                                                        </tr>
                                                    ))}
                                                </tbody>
                                            </table>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        );
                    })}

                    {data.filter(s => s.is_exit_point).length > 0 && (
                        <div className="bg-amber-50 rounded-xl border border-amber-200 p-3">
                            <div className="text-xs font-bold text-amber-700 uppercase mb-2">Exit Points</div>
                            {data.filter(s => s.is_exit_point).map((ep, i) => (
                                <div key={i} className="text-sm text-amber-800 italic py-0.5">{ep.description}</div>
                            ))}
                        </div>
                    )}
                </div>
            </div>
        );
    };

    // ─── JSX ────────────────────────────────────────────────────────────────
    return (
        <div className="p-4 bg-white min-h-screen text-black font-sans">
            {/* ── Top bar ── */}
            <div className="no-print mb-6">
                <h1 className="text-3xl font-black text-navy mb-4">CURRICULUM</h1>
                <div className="flex gap-4 items-end bg-gray-100 p-4 rounded-xl border border-gray-200">
                    {/* Course selector */}
                    <div className="w-1/3">
                        <label className="block text-xs font-bold text-gray-600 mb-1 uppercase tracking-wider">Select Course</label>
                        <select
                            className="w-full px-3 py-2 rounded-lg border-2 border-gray-300 focus:border-royal outline-none transition-colors"
                            value={courseId}
                            onChange={onCourseSelect}
                            disabled={processing}
                        >
                            <option value="">-- Choose Course --</option>
                            {courses.map(c => (
                                <option key={c.id} value={c.id}>{c.code} - {c.description}</option>
                            ))}
                        </select>
                    </div>

                    {/* Action area */}
                    {courseId && (
                        <div className="flex-1 flex gap-3 items-center">
                            {/* File input — shown in upload and verify states */}
                            {(view === 'upload' || view === 'verify') && (
                                <>
                                    <div className="flex-1 bg-white border-2 border-dashed border-gray-300 rounded-lg p-1">
                                        <input
                                            type="file"
                                            accept="application/pdf"
                                            onChange={onFileChange}
                                            className="block w-full text-sm text-gray-500
                                                file:mr-4 file:py-1 file:px-4 file:rounded-md file:border-0
                                                file:text-xs file:font-bold file:bg-royal file:text-white hover:file:bg-blue-700"
                                        />
                                    </div>

                                    {file && view === 'upload' && (
                                        <button onClick={onVerify} disabled={processing}
                                            className="px-6 py-2 bg-amber-500 text-white font-bold rounded shadow hover:bg-amber-600 active:scale-95 transition-all text-sm uppercase flex items-center gap-2">
                                            {processing ? (
                                                <><svg className="animate-spin h-4 w-4" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none"/><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/></svg>ANALYZING…</>
                                            ) : (
                                                <><svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}><path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>VERIFY</>
                                            )}
                                        </button>
                                    )}

                                    {view === 'verify' && (
                                        <div className="flex gap-2">
                                            <button onClick={onUpload} disabled={processing}
                                                className="px-6 py-2 bg-green-600 text-white font-bold rounded shadow hover:bg-green-700 active:scale-95 transition-all text-sm uppercase flex items-center gap-2">
                                                {processing ? (
                                                    <><svg className="animate-spin h-4 w-4" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none"/><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/></svg>SAVING…</>
                                                ) : (
                                                    <><svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}><path strokeLinecap="round" strokeLinejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12"/></svg>UPLOAD</>
                                                )}
                                            </button>
                                            <button onClick={() => { setView('upload'); setParsedSubjects([]); setMessage(''); }}
                                                className="px-4 py-2 border-2 border-gray-400 text-gray-600 rounded font-bold hover:bg-gray-100 transition-all text-sm uppercase">
                                                CANCEL
                                            </button>
                                        </div>
                                    )}
                                </>
                            )}

                            {view === 'display' && (
                                <div className="flex gap-3">
                                    <button onClick={onDelete} disabled={processing}
                                        className="px-6 py-2 bg-red-600 text-white font-bold rounded shadow hover:bg-red-700 transition-all text-sm">
                                        DELETE
                                    </button>
                                    <button onClick={() => { setView('upload'); setFile(null); setParsedSubjects([]); }}
                                        className="px-6 py-2 border-2 border-gray-400 rounded font-bold hover:bg-gray-100 transition-all text-sm">
                                        RE-UPLOAD
                                    </button>
                                </div>
                            )}
                        </div>
                    )}
                </div>

                {message && <div className="mt-4 p-3 bg-blue-50 text-blue-700 rounded text-sm">{message}</div>}
                {error   && <div className="mt-4 p-3 bg-red-50  text-red-700  rounded text-sm">{error}</div>}
            </div>

            {/* ══ SPLIT-SCREEN VERIFY VIEW ══ */}
            {view === 'verify' && parsedSubjects.length > 0 && (
                <div
                    ref={splitContainerRef}
                    className="relative flex rounded-2xl overflow-hidden border-2 border-gray-200 shadow-xl"
                    style={{ height: 'calc(100vh - 220px)' }}
                >
                    {/* Left: parsed overview */}
                    <div className="overflow-hidden" style={{ width: `${splitRatio}%`, minWidth: 0 }}>
                        {renderParsedOverview(parsedSubjects)}
                    </div>

                    {/* Draggable divider */}
                    <div onMouseDown={onMouseDown} className="relative flex-shrink-0 group" style={{ width: '8px', cursor: 'col-resize' }}>
                        <div className="absolute inset-0 bg-gray-200 group-hover:bg-royal/40 transition-colors"/>
                        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 flex flex-col gap-[3px]">
                            {[...Array(5)].map((_, i) => (
                                <div key={i} className="w-1 h-1 rounded-full bg-gray-400 group-hover:bg-royal transition-colors"/>
                            ))}
                        </div>
                    </div>

                    {/* Right: PDF viewer */}
                    <div className="overflow-hidden flex flex-col" style={{ width: `${100 - splitRatio}%`, minWidth: 0 }}>
                        <PdfViewer
                            fileOrUrl={file}
                            containerRef={rightPaneRef}
                            onScroll={() => handleSyncScroll('right')}
                        />
                    </div>
                </div>
            )}

            {/* ══ DISPLAY VIEW: PDF viewer from server ══ */}
            {view === 'display' && (
                <div className="rounded-2xl overflow-hidden border-2 border-gray-200 shadow-xl" style={{ height: 'calc(100vh - 220px)' }}>
                    {pdfUrl ? (
                        <PdfViewer fileOrUrl={pdfUrl} containerRef={displayPdfRef} />
                    ) : (
                        /* PDF not stored on server yet — prompt to re-upload */
                        <div className="flex flex-col items-center justify-center h-full bg-gray-50 gap-4 text-center p-8">
                            <svg className="h-16 w-16 text-gray-300" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1}>
                                <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
                            </svg>
                            <div>
                                <p className="font-bold text-gray-500 text-lg">Curriculum is saved</p>
                                <p className="text-gray-400 text-sm mt-1">No PDF was stored with this curriculum. Click <strong>RE-UPLOAD</strong> to attach the PDF so it displays here.</p>
                            </div>
                            <button onClick={() => { setView('upload'); setFile(null); }}
                                className="mt-2 px-6 py-2 bg-royal text-white font-bold rounded shadow hover:bg-blue-700 transition-all text-sm uppercase">
                                RE-UPLOAD PDF
                            </button>
                        </div>
                    )}
                </div>
            )}

            <ConfirmDialog {...confirmDialog} onCancel={() => setConfirmDialog({ open: false })} />
        </div>
    );
}
