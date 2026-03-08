import { useState, useEffect } from 'react';
import { list } from '../../store/db';
import ConfirmDialog from '../../components/ConfirmDialog';

export default function Curriculum() {
    const [courses, setCourses] = useState([]);
    const [courseId, setCourseId] = useState('');
    const [file, setFile] = useState(null);
    const [subjects, setSubjects] = useState([]);
    const [view, setView] = useState('upload'); // 'upload' | 'display'
    const [processing, setProcessing] = useState(false);
    const [message, setMessage] = useState('');
    const [error, setError] = useState('');
    const [confirmDialog, setConfirmDialog] = useState({ open: false });

    useEffect(() => {
        loadCourses();
    }, []);

    async function loadCourses() {
        try {
            const data = await list('course');
            setCourses(data);
        } catch (err) {
            console.error("Failed to load courses", err);
        }
    }

    async function onCourseSelect(e) {
        const id = e.target.value;
        setCourseId(id);
        setSubjects([]);
        setView('upload');
        setMessage('');
        setError('');

        if (id) {
            fetchCurriculum(id);
        }
    }

    async function fetchCurriculum(id) {
        try {
            const res = await fetch(`http://localhost:8000/api/curriculum/${id}`);
            if (res.ok) {
                const data = await res.json();
                if (data && data.length > 0) {
                    setSubjects(data);
                    setView('display');
                }
            }
        } catch (err) {
            console.error(err);
        }
    }

    function onFileChange(e) {
        setFile(e.target.files[0]);
    }

    async function onUpload() {
        if (!file || !courseId) return;
        setProcessing(true);
        setError('');
        setMessage('');

        const formData = new FormData();
        formData.append('file', file);
        formData.append('course_id', courseId);

        try {
            const res = await fetch('http://localhost:8000/api/curriculum/parse', {
                method: 'POST',
                body: formData
            });

            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.detail || 'Parsing failed');
            }

            const data = await res.json();
            setSubjects(data);
            setView('display');
            setMessage('PDF Parsed Successfully. Please Review and Save.');
        } catch (err) {
            setError(err.message);
        } finally {
            setProcessing(false);
        }
    }

    async function onSave() {
        if (!courseId || subjects.length === 0) return;
        setProcessing(true);
        setError('');

        try {
            const res = await fetch(`http://localhost:8000/api/curriculum/${courseId}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(subjects)
            });

            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.detail || 'Save failed');
            }

            const result = await res.json();
            const parts = ['Curriculum Saved Successfully!'];
            if (result.subjects_created > 0) parts.push(`${result.subjects_created} subject(s) added`);
            if (result.subjects_updated > 0) parts.push(`${result.subjects_updated} subject(s) updated`);
            setMessage(parts.join(' — '));
            setFile(null);
            fetchCurriculum(courseId);
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
                setConfirmDialog({ open: false })
                setProcessing(true);
                try {
                    const res = await fetch(`http://localhost:8000/api/curriculum/${courseId}`, {
                        method: 'DELETE'
                    });
                    if (!res.ok) throw new Error("Delete failed");

                    setSubjects([]);
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

    // Helper to group items by year
    const years = [1, 2, 3, 4];

    const yearLabels = {
        1: "FIRST YEAR",
        2: "SECOND YEAR",
        3: "THIRD YEAR",
        4: "FOURTH YEAR"
    };

    const TotalRow = ({ list }) => {
        const totalLec = list.reduce((sum, item) => sum + (Number(item.lec_hours) || 0), 0);
        const totalLab = list.reduce((sum, item) => sum + (Number(item.lab_hours) || 0), 0);
        const total = list.reduce((sum, item) => sum + (Number(item.units) || 0), 0);
        return (
            <tr className="bg-white font-bold border-t-2 border-black">
                <td colSpan={2} className="px-3 py-1 text-center font-black tracking-[0.3em]">TOTAL</td>
                <td className="px-3 py-1 text-center border-l-2 border-black">{totalLec || ''}</td>
                <td className="px-3 py-1 text-center border-l border-black">{totalLab || ''}</td>
                <td className="px-3 py-1 text-center border-l-2 border-r-2 border-black font-black">{total}</td>
                <td className="px-3 py-1"></td>
            </tr>
        );
    };

    const SemesterTable = ({ title, list }) => (
        <div className="flex-1 min-w-0 border-2 border-black bg-white">
            <div className="bg-white border-b-2 border-black py-1 px-4 font-bold text-center uppercase text-sm">
                {title}
            </div>
            <table className="w-full text-[10px] border-collapse">
                <thead>
                    <tr className="border-b border-black">
                        <th rowSpan={2} className="px-1 py-1 text-center border-r-2 border-black w-[15%]">Course No.</th>
                        <th rowSpan={2} className="px-1 py-1 text-center border-r-2 border-black w-[45%]">Descriptive Title</th>
                        <th colSpan={3} className="px-1 py-0.5 text-center border-r-2 border-black w-[20%]">Units</th>
                        <th rowSpan={2} className="px-1 py-1 text-center w-[20%] text-[8px]">Pre-requisite/ Co-requisite</th>
                    </tr>
                    <tr className="border-b-2 border-black">
                        <th className="px-1 py-0.5 text-center border-r border-black text-[8px]">LEC</th>
                        <th className="px-1 py-0.5 text-center border-r border-black text-[8px]">LAB</th>
                        <th className="px-1 py-0.5 text-center border-r-2 border-black text-[8px]">Total</th>
                    </tr>
                </thead>
                <tbody className="divide-y divide-black">
                    {list.map((item, idx) => (
                        <tr key={idx} className="h-7 border-black">
                            <td className="px-1 py-1 border-r-2 border-black align-top font-bold uppercase">{item.code}</td>
                            <td className="px-1 py-1 border-r-2 border-black align-top leading-tight">{item.description}</td>
                            <td className="px-1 py-1 border-r border-black text-center align-top">{item.lec_hours || ''}</td>
                            <td className="px-1 py-1 border-r border-black text-center align-top">{item.lab_hours || ''}</td>
                            <td className="px-1 py-1 border-r-2 border-black text-center align-top font-bold">{item.units}</td>
                            <td className="px-1 py-1 text-[8px] align-top">{item.prerequisite}</td>
                        </tr>
                    ))}
                    {list.length > 0 && <TotalRow list={list} />}
                </tbody>
            </table>
        </div>
    );

    return (
        <div className="p-4 bg-white min-h-screen text-black font-serif">
            <div className="no-print mb-8">
                <h1 className="text-3xl font-black text-navy mb-4 font-sans">CURRICULUM</h1>
                <div className="flex gap-4 items-end bg-gray-100 p-4 rounded-xl border border-gray-200">
                    <div className="w-1/3">
                        <label className="block text-xs font-bold text-gray-600 mb-1 uppercase tracking-wider font-sans">Select Course</label>
                        <select
                            className="w-full px-3 py-2 rounded-lg border-2 border-gray-300 focus:border-royal outline-none transition-colors font-sans"
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

                    {courseId && (
                        <div className="flex-1 flex gap-4 items-center font-sans">
                            {view === 'upload' && (
                                <>
                                    <div className="flex-1 bg-white border-2 border-dashed border-gray-300 rounded-lg p-1">
                                        <input
                                            type="file"
                                            accept="application/pdf"
                                            onChange={onFileChange}
                                            className="block w-full text-sm text-gray-500 font-sans
                                                file:mr-4 file:py-1 file:px-4
                                                file:rounded-md file:border-0
                                                file:text-xs file:font-bold
                                                file:bg-royal file:text-white
                                                hover:file:bg-blue-700
                                            "
                                        />
                                    </div>
                                    <button
                                        onClick={onUpload}
                                        disabled={!file || processing}
                                        className="px-6 py-2 bg-royal text-white font-bold rounded shadow active:scale-95 transition-all text-sm font-sans uppercase"
                                    >
                                        {processing ? 'ANALYZING PDF...' : 'UPLOAD & PARSE'}
                                    </button>
                                </>
                            )}

                            {view === 'display' && (
                                <div className="flex gap-3">
                                    <button
                                        onClick={onSave}
                                        disabled={processing}
                                        className="px-6 py-2 bg-green-600 text-white font-bold rounded shadow hover:bg-green-700 transition-all text-sm font-sans"
                                    >
                                        SAVE CHANGES
                                    </button>
                                    <button
                                        onClick={onDelete}
                                        disabled={processing}
                                        className="px-6 py-2 bg-red-600 text-white font-bold rounded shadow hover:bg-red-700 transition-all text-sm font-sans"
                                    >
                                        DELETE
                                    </button>
                                    <button
                                        onClick={() => setView('upload')}
                                        className="px-6 py-2 border-2 border-gray-400 rounded font-bold hover:bg-gray-100 transition-all text-sm font-sans"
                                    >
                                        RE-UPLOAD
                                    </button>
                                </div>
                            )}
                        </div>
                    )}
                </div>
                {message && <div className="mt-4 p-3 bg-blue-50 text-blue-700 rounded font-sans text-sm animate-pulse">{message}</div>}
                {error && <div className="mt-4 p-3 bg-red-50 text-red-700 rounded font-sans text-sm">{error}</div>}
            </div>

            {/* Curriculum Table Layout */}
            {subjects.length > 0 && (
                <div className="max-w-5xl mx-auto space-y-12">
                    {/* Course Header */}
                    <div className="text-center mb-10 border-b-2 border-black pb-4">
                        <div className="font-bold text-xl uppercase tracking-wider">
                            {courses.find(c => String(c.id) === String(courseId))?.description}
                        </div>
                        <div className="text-[10px] italic mt-1 font-sans">(Generated from Official PDF Curriculum)</div>
                    </div>

                    {years.map(year => {
                        const yearItems = subjects.filter(s => s.year_level === year);
                        if (yearItems.length === 0) return null;

                        const sem1 = yearItems.filter(s => s.semester === 1 && !s.is_exit_point);
                        const sem2 = yearItems.filter(s => s.semester === 2 && !s.is_exit_point);
                        const summer = yearItems.filter(s => s.semester === 3 && !s.is_exit_point);
                        const exitPoints = yearItems.filter(s => s.is_exit_point);

                        return (
                            <div key={year} className="space-y-1">
                                <div className="border-[3px] border-black bg-white py-1 mb-0.5">
                                    <div className="text-center font-black text-lg uppercase tracking-[0.5em]">
                                        {yearLabels[year]}
                                    </div>
                                </div>

                                <div className="flex gap-1">
                                    <SemesterTable title="First Semester" list={sem1} />
                                    <SemesterTable title="Second Semester" list={sem2} />
                                </div>

                                {summer.length > 0 && (
                                    <div className="mt-4 w-full">
                                        <SemesterTable title="SUMMER" list={summer} />
                                    </div>
                                )}

                                {/* Exit Points */}
                                {exitPoints.map((ep, i) => (
                                    <div key={i} className="text-center py-2 italic font-bold text-sm tracking-tight border-b-2 border-black mb-4">
                                        {ep.description}
                                    </div>
                                ))}
                            </div>
                        );
                    })}
                </div>
            )}

            <ConfirmDialog
                {...confirmDialog}
                onCancel={() => setConfirmDialog({ open: false })}
            />
        </div>
    );
}
