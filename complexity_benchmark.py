#!/usr/bin/env python3
"""
Computational Complexity Benchmark for JRMSU Classroom Scheduling System
=========================================================================

This script empirically measures and demonstrates the computational complexity
(Big-O) of each algorithmic component in the scheduling system:

    1. K-Means Clustering   — api/clustering/kmeans_cluster.py
    2. Greedy Scheduler      — api/scheduler/greedy.py
    3. CP-SAT Model Build    — OR-Tools constraint model construction
    4. Full Pipeline         — K-Means → CP-SAT (end-to-end)

For each component, it:
    • Generates synthetic data at increasing sizes (n = 10, 20, 40, 80, 160, 320)
    • Times execution (median of 3 trials)
    • Computes growth ratios T(2n)/T(n)
    • Fits timing data to complexity curves (O(n), O(n log n), O(n²), O(n³))
    • Determines the best-fitting complexity class via R² values
    • Generates a combined chart saved as complexity_results.png

Usage:
    python complexity_benchmark.py
"""

import time
import statistics
import math
import sys
import os
import warnings
from collections import defaultdict

# ──────────────────────────────────────────────────────────────────────────────
# Dependency checks
# ──────────────────────────────────────────────────────────────────────────────
try:
    import numpy as np
except ImportError:
    print("ERROR: numpy is required.  Install with:  pip install numpy")
    sys.exit(1)

HAS_SKLEARN = False
try:
    from sklearn.cluster import KMeans
    from sklearn.preprocessing import StandardScaler
    HAS_SKLEARN = True
except (ImportError, ValueError) as _sklearn_err:
    # ValueError can happen with numpy/sklearn binary incompatibility
    print(f"WARNING: scikit-learn not available ({_sklearn_err}) — K-Means benchmark will be skipped.")
    print("  Fix: pip install --upgrade numpy scikit-learn")

HAS_ORTOOLS = False
try:
    from ortools.sat.python import cp_model
    HAS_ORTOOLS = True
except ImportError:
    print("WARNING: OR-Tools not found — CP-SAT benchmark will be skipped.")

HAS_MATPLOTLIB = False
try:
    import matplotlib
    matplotlib.use("Agg")          # non-interactive backend
    import matplotlib.pyplot as plt
    from matplotlib.ticker import FuncFormatter
    HAS_MATPLOTLIB = True
except ImportError:
    print("WARNING: matplotlib not found — chart will not be generated.")


# ──────────────────────────────────────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────────────────────────────────────
INPUT_SIZES      = [10, 20, 40, 80, 160, 320]
NUM_TRIALS       = 3          # median of 3 trials per size
NUM_ROOMS        = 15         # constant room pool (realistic for a campus)
NUM_INSTRUCTORS  = 20         # constant instructor pool
NUM_DAYS         = 5          # M T W TH F
NUM_TIME_BLOCKS  = 19         # from timeslots.py

# K-Means settings
K_CLUSTERS       = 3
NUM_FEATURES     = 4          # unit, year_level, semester, recommended_slots

# ──────────────────────────────────────────────────────────────────────────────
# Mock / Synthetic Data Generators
# ──────────────────────────────────────────────────────────────────────────────

class _MockSubject:
    """Lightweight mock for api.models.Subject."""
    __slots__ = ("id", "code", "type", "unit", "year_level", "semester",
                 "recommended_slots", "min_slots", "max_slots",
                 "course_id", "cluster", "is_block_shared")

    def __init__(self, sid, subj_type="LEC"):
        self.id = sid
        self.code = f"SUBJ-{sid}"
        self.type = subj_type
        self.unit = np.random.choice([1, 2, 3])
        self.year_level = np.random.choice([1, 2, 3, 4])
        self.semester = np.random.choice([1, 2])
        self.recommended_slots = np.random.choice([2, 3, 4])
        self.min_slots = 2
        self.max_slots = 4
        self.course_id = 1
        self.cluster = 0
        self.is_block_shared = False


class _MockRoom:
    """Lightweight mock for api.models.Room."""
    __slots__ = ("id", "name", "type", "capacity", "is_available",
                 "cluster", "building_id")

    def __init__(self, rid, room_type="LEC"):
        self.id = rid
        self.name = f"Room-{rid}"
        self.type = room_type
        self.capacity = np.random.choice([30, 40, 50, 60])
        self.is_available = True
        self.cluster = 0
        self.building_id = 1


class _MockInstructor:
    """Lightweight mock for api.models.Instructor."""
    __slots__ = ("id", "name", "is_active", "college_id")

    def __init__(self, iid):
        self.id = iid
        self.name = f"Instructor-{iid}"
        self.is_active = True
        self.college_id = 1


class _MockDay:
    """Lightweight mock for api.models.Day."""
    __slots__ = ("id", "label")

    _labels = ["M", "T", "W", "TH", "F"]

    def __init__(self, did):
        self.id = did
        self.label = self._labels[did - 1] if did <= len(self._labels) else f"D{did}"


def _generate_subjects(n, mix_types=True):
    """Generate n mock subjects (70% LEC, 30% LAB)."""
    subjects = []
    for i in range(1, n + 1):
        stype = "LAB" if mix_types and i % 3 == 0 else "LEC"
        subjects.append(_MockSubject(i, stype))
    return subjects


def _generate_rooms(n=NUM_ROOMS):
    rooms = []
    for i in range(1, n + 1):
        rtype = "LAB" if i % 3 == 0 else "LEC"
        rooms.append(_MockRoom(i, rtype))
    return rooms


def _generate_instructors(n=NUM_INSTRUCTORS):
    return [_MockInstructor(i) for i in range(1, n + 1)]


def _generate_days(n=NUM_DAYS):
    return [_MockDay(i) for i in range(1, n + 1)]


TIME_BLOCKS_SYNTHETIC = [
    {"label": f"Block-{i}", "start_min": 420 + i * 30, "end_min": 420 + (i + 1) * 30}
    for i in range(NUM_TIME_BLOCKS)
]


def _generate_slots_by_day(days):
    """Generate slots_by_day mapping (day_label -> list of slot dicts)."""
    slots_by_day = {}
    for day in days:
        slots = []
        for idx, tb in enumerate(TIME_BLOCKS_SYNTHETIC):
            slots.append({
                "day": day.label,
                "index": idx,
                "label": tb["label"],
                "start_min": tb["start_min"],
                "end_min": tb["end_min"],
                "block_indices": [idx],
                "blocks_spanned": [idx],
                "is_lab": idx % 3 == 0,
            })
        slots_by_day[day.label] = slots
    return slots_by_day


# ──────────────────────────────────────────────────────────────────────────────
# Timing Utilities
# ──────────────────────────────────────────────────────────────────────────────

def _time_fn(fn, *args, **kwargs):
    """Time a function call.  Returns (elapsed_seconds, result)."""
    start = time.perf_counter()
    result = fn(*args, **kwargs)
    elapsed = time.perf_counter() - start
    return elapsed, result


def _benchmark(fn, sizes, trials=NUM_TRIALS):
    """Run fn(n) for each n in sizes, return {n: median_time}."""
    results = {}
    for n in sizes:
        times = []
        for _ in range(trials):
            elapsed, _ = fn(n)
            times.append(elapsed)
        results[n] = statistics.median(times)
    return results


# ──────────────────────────────────────────────────────────────────────────────
# Benchmark Functions
# ──────────────────────────────────────────────────────────────────────────────

def bench_kmeans(n):
    """Benchmark K-Means clustering with n subjects."""
    subjects = _generate_subjects(n)

    # Build feature matrix (mirrors kmeans_cluster.py)
    feature_data = []
    for s in subjects:
        feature_data.append([
            float(s.unit or 0),
            float(s.year_level or 1),
            float(s.semester or 1),
            float((s.recommended_slots or 1) * 2.0),
        ])
    X = np.array(feature_data)

    # Timed section: scale + fit
    start = time.perf_counter()
    X_scaled = StandardScaler().fit_transform(X)
    k = min(K_CLUSTERS, n)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
        labels = kmeans.fit_predict(X_scaled)
    elapsed = time.perf_counter() - start
    return elapsed, labels


def bench_greedy(n):
    """Benchmark greedy scheduler with n subjects."""
    subjects = _generate_subjects(n)
    rooms    = _generate_rooms()
    instructors = _generate_instructors()
    days     = _generate_days()

    # Mirror greedy.py logic (simplified in-line to avoid DB imports)
    start = time.perf_counter()

    room_id_to_name = {r.id: r.name for r in rooms}
    schedule = []
    used = set()
    room_ranges = defaultdict(list)
    instr_ranges = defaultdict(list)

    for subject in subjects:
        placed = False
        for day in days:
            if placed:
                break
            for time_idx, block in enumerate(TIME_BLOCKS_SYNTHETIC):
                if placed:
                    break
                start_min = block["start_min"]
                end_min   = block["end_min"]

                # Type-matching rooms
                candidates = [r for r in rooms if r.type == subject.type]
                room_list = candidates if candidates else rooms

                for room in room_list:
                    if placed:
                        break
                    room_key = (day.id, time_idx, room.id)
                    if room_key in used:
                        continue

                    # Check range conflicts
                    room_name = room_id_to_name.get(room.id, "")
                    conflict = False
                    for rs, re_ in room_ranges.get((room_name, day.id), []):
                        if not (end_min <= rs or re_ <= start_min):
                            conflict = True
                            break
                    if conflict:
                        continue

                    for instructor in instructors:
                        inst_key = (day.id, time_idx, instructor.id)
                        if inst_key in used:
                            continue
                        i_conflict = False
                        for rs, re_ in instr_ranges.get((instructor.id, day.id), []):
                            if not (end_min <= rs or re_ <= start_min):
                                i_conflict = True
                                break
                        if i_conflict:
                            continue

                        used.add(room_key)
                        used.add(inst_key)
                        room_ranges[(room_name, day.id)].append((start_min, end_min))
                        instr_ranges[(instructor.id, day.id)].append((start_min, end_min))
                        schedule.append({
                            "subject_id": subject.id,
                            "day_id": day.id,
                            "room_id": room.id,
                            "instructor_id": instructor.id,
                        })
                        placed = True
                        break

    elapsed = time.perf_counter() - start
    return elapsed, schedule


def bench_cpsat_model_build(n):
    """
    Benchmark CP-SAT model construction with n subjects.

    This benchmarks the MODEL BUILDING phase — creating Boolean decision variables
    and adding pairwise no-overlap constraints.  It does NOT run the solver itself
    (which is bounded by max_time_seconds and is NP-hard).
    """
    subjects    = _generate_subjects(n)
    rooms       = _generate_rooms()
    instructors = _generate_instructors()
    days        = _generate_days()

    start = time.perf_counter()

    model = cp_model.CpModel()

    # Create decision variables: x[s, r, d, t, i] — one per valid option
    # In practice the real CP scheduler iterates over pre-generated start options.
    # We mirror that by creating ~O(subjects * rooms * days * slots * instructors) variables
    # but only for type-matched rooms (like the real code).
    decision_vars = {}
    subject_vars = defaultdict(list)

    for s in subjects:
        eligible_rooms = [r for r in rooms if r.type == s.type]
        eligible_instr = instructors  # simplified: all instructors eligible

        for r in eligible_rooms:
            for d in days:
                for t_idx, tb in enumerate(TIME_BLOCKS_SYNTHETIC):
                    for inst in eligible_instr:
                        var_name = f"x_s{s.id}_r{r.id}_d{d.id}_t{t_idx}_i{inst.id}"
                        var = model.NewBoolVar(var_name)
                        key = (s.id, r.id, d.id, t_idx, inst.id)
                        decision_vars[key] = var
                        subject_vars[s.id].append(var)

    # Constraint 1: Each subject scheduled at most once
    for sid, vars_list in subject_vars.items():
        model.Add(sum(vars_list) <= 1)

    # Constraint 2: No room double-booking (pairwise per room/day/time)
    for d in days:
        for t_idx in range(len(TIME_BLOCKS_SYNTHETIC)):
            for r in rooms:
                slot_vars = []
                for s in subjects:
                    for inst in instructors:
                        key = (s.id, r.id, d.id, t_idx, inst.id)
                        if key in decision_vars:
                            slot_vars.append(decision_vars[key])
                if len(slot_vars) > 1:
                    model.Add(sum(slot_vars) <= 1)

    # Constraint 3: No instructor double-booking (pairwise per instructor/day/time)
    for d in days:
        for t_idx in range(len(TIME_BLOCKS_SYNTHETIC)):
            for inst in instructors:
                inst_vars = []
                for s in subjects:
                    for r in rooms:
                        key = (s.id, r.id, d.id, t_idx, inst.id)
                        if key in decision_vars:
                            inst_vars.append(decision_vars[key])
                if len(inst_vars) > 1:
                    model.Add(sum(inst_vars) <= 1)

    # Objective: maximize scheduled subjects
    scheduled_indicators = []
    for sid, vars_list in subject_vars.items():
        indicator = model.NewBoolVar(f"sched_{sid}")
        model.Add(sum(vars_list) >= 1).OnlyEnforceIf(indicator)
        model.Add(sum(vars_list) == 0).OnlyEnforceIf(indicator.Not())
        scheduled_indicators.append(indicator)
    model.Maximize(sum(scheduled_indicators))

    elapsed = time.perf_counter() - start
    return elapsed, model


def bench_cpsat_model_build_reduced(n):
    """
    Benchmark CP-SAT model construction with REDUCED variable space.

    Instead of enumerating all (subject × room × day × slot × instructor),
    we pre-generate ~10-20 valid options per subject (like the real scheduler)
    and only create variables for those options.  This mirrors the actual
    system's variable reduction optimization.
    """
    subjects    = _generate_subjects(n)
    rooms       = _generate_rooms()
    instructors = _generate_instructors()
    days        = _generate_days()
    options_per_subject = 15  # realistic number of valid start options

    start = time.perf_counter()

    model = cp_model.CpModel()

    # Pre-generate limited options per subject (mimics generate_subject_start_options)
    decision_vars = {}
    subject_vars = defaultdict(list)

    for s in subjects:
        eligible_rooms = [r for r in rooms if r.type == s.type]
        eligible_instr = instructors

        # Generate a limited number of options (randomized subset)
        generated_count = 0
        for r in eligible_rooms:
            if generated_count >= options_per_subject:
                break
            for d in days:
                if generated_count >= options_per_subject:
                    break
                t_idx = np.random.randint(0, len(TIME_BLOCKS_SYNTHETIC))
                inst = eligible_instr[np.random.randint(0, len(eligible_instr))]

                var_name = f"x_s{s.id}_o{generated_count}"
                var = model.NewBoolVar(var_name)
                key = (s.id, r.id, d.id, t_idx, inst.id)
                decision_vars[key] = var
                subject_vars[s.id].append(var)
                generated_count += 1

    # Constraint: Each subject at most once
    for sid, vars_list in subject_vars.items():
        model.Add(sum(vars_list) <= 1)

    # Room no-overlap constraints (AddAtMostOne per slot)
    slot_to_vars = defaultdict(list)
    for (sid, rid, did, tidx, iid), var in decision_vars.items():
        slot_to_vars[(rid, did, tidx)].append(var)
    for slot_key, vars_list in slot_to_vars.items():
        if len(vars_list) > 1:
            model.AddAtMostOne(vars_list)

    # Instructor no-overlap constraints
    inst_slot_to_vars = defaultdict(list)
    for (sid, rid, did, tidx, iid), var in decision_vars.items():
        inst_slot_to_vars[(iid, did, tidx)].append(var)
    for slot_key, vars_list in inst_slot_to_vars.items():
        if len(vars_list) > 1:
            model.AddAtMostOne(vars_list)

    elapsed = time.perf_counter() - start
    return elapsed, model


# ──────────────────────────────────────────────────────────────────────────────
# Curve Fitting and Analysis
# ──────────────────────────────────────────────────────────────────────────────

def _fit_complexity(sizes, times):
    """
    Fit timing data against candidate complexity functions.
    Returns dict: { "O(n)": r_squared, "O(n log n)": r_squared, ... }
    """
    n = np.array(sizes, dtype=float)
    t = np.array(times, dtype=float)

    if len(n) < 3:
        return {}

    # Candidate models: t ≈ a * f(n) + b
    candidates = {
        "O(n)":       n,
        "O(n log n)": n * np.log2(np.maximum(n, 1)),
        "O(n²)":      n ** 2,
        "O(n³)":      n ** 3,
    }

    results = {}
    ss_total = np.sum((t - np.mean(t)) ** 2)
    if ss_total == 0:
        return {name: 1.0 for name in candidates}

    for name, fn_values in candidates.items():
        # Least-squares fit: t = a * fn_values + b
        A = np.vstack([fn_values, np.ones(len(fn_values))]).T
        try:
            coeffs, _, _, _ = np.linalg.lstsq(A, t, rcond=None)
            predictions = A @ coeffs
            ss_res = np.sum((t - predictions) ** 2)
            r_squared = 1 - ss_res / ss_total
            results[name] = r_squared
        except Exception:
            results[name] = -1.0

    return results


def _best_fit(r_squared_dict):
    """Return the complexity class with the highest R²."""
    if not r_squared_dict:
        return "Unknown"
    return max(r_squared_dict, key=r_squared_dict.get)


def _growth_ratios(sizes, times):
    """Compute T(2n)/T(n) for consecutive size doublings."""
    ratios = []
    for i in range(1, len(sizes)):
        if times[i - 1] > 0:
            ratio = times[i] / times[i - 1]
            ratios.append(ratio)
        else:
            ratios.append(float("inf"))
    return ratios


# ──────────────────────────────────────────────────────────────────────────────
# Reporting
# ──────────────────────────────────────────────────────────────────────────────

def _print_table(title, sizes, times, r_squared, ratios):
    """Print a nicely formatted results table."""
    print()
    print("=" * 80)
    print(f"  {title}")
    print("=" * 80)

    # Timing table
    print(f"\n  {'n':>6}  {'Time (s)':>12}  {'Growth T(2n)/T(n)':>20}")
    print(f"  {'─' * 6}  {'─' * 12}  {'─' * 20}")
    for i, n in enumerate(sizes):
        t = times[i]
        if i == 0:
            ratio_str = "—"
        else:
            ratio_str = f"{ratios[i - 1]:.2f}x"
        print(f"  {n:>6}  {t:>12.6f}  {ratio_str:>20}")

    # Complexity fit
    print(f"\n  Complexity Fit (R² values):")
    best = _best_fit(r_squared)
    for name, r2 in sorted(r_squared.items(), key=lambda x: -x[1]):
        marker = "  ◀ BEST FIT" if name == best else ""
        print(f"    {name:<12}  R² = {r2:.4f}{marker}")

    # Interpretation
    print(f"\n  ➤  Best-fit complexity: {best}")

    # Growth ratio interpretation
    avg_ratio = statistics.mean(ratios) if ratios and all(r != float("inf") for r in ratios) else float("inf")
    if avg_ratio != float("inf"):
        if avg_ratio < 1.5:
            interp = "Sub-linear or O(1)"
        elif avg_ratio < 2.5:
            interp = "~O(n)  [Linear]"
        elif avg_ratio < 3.5:
            interp = "~O(n log n)"
        elif avg_ratio < 5.0:
            interp = "~O(n²)  [Quadratic]"
        elif avg_ratio < 9.0:
            interp = "~O(n³)  [Cubic]"
        else:
            interp = "Super-polynomial / Exponential"
        print(f"  ➤  Avg growth ratio: {avg_ratio:.2f}x → suggests {interp}")
    print()


def _generate_chart(all_results, output_path="complexity_results.png"):
    """Generate a comparison chart of all benchmark results."""
    if not HAS_MATPLOTLIB:
        print("  [Chart skipped — matplotlib not installed]")
        return

    fig, axes = plt.subplots(1, len(all_results), figsize=(6 * len(all_results), 5))
    if len(all_results) == 1:
        axes = [axes]

    colors = ["#2196F3", "#4CAF50", "#FF9800", "#9C27B0"]

    for idx, (title, data) in enumerate(all_results.items()):
        ax = axes[idx]
        sizes = data["sizes"]
        times = data["times"]
        best = data["best_fit"]

        ax.plot(sizes, times, "o-", color=colors[idx % len(colors)],
                linewidth=2, markersize=8, label=f"Measured")

        # Plot best-fit curve
        n_smooth = np.linspace(min(sizes), max(sizes), 100)
        n_arr = np.array(sizes, dtype=float)
        t_arr = np.array(times, dtype=float)

        fit_funcs = {
            "O(n)":       lambda x: x,
            "O(n log n)": lambda x: x * np.log2(np.maximum(x, 1)),
            "O(n²)":      lambda x: x ** 2,
            "O(n³)":      lambda x: x ** 3,
        }
        if best in fit_funcs:
            fn = fit_funcs[best]
            A = np.vstack([fn(n_arr), np.ones(len(n_arr))]).T
            try:
                coeffs, _, _, _ = np.linalg.lstsq(A, t_arr, rcond=None)
                fit_values = fn(n_smooth) * coeffs[0] + coeffs[1]
                ax.plot(n_smooth, fit_values, "--", color=colors[idx % len(colors)],
                        alpha=0.5, label=f"Fit: {best}")
            except Exception:
                pass

        ax.set_title(title, fontsize=12, fontweight="bold")
        ax.set_xlabel("Input Size (n)", fontsize=10)
        ax.set_ylabel("Time (seconds)", fontsize=10)
        ax.legend(fontsize=9)
        ax.grid(True, alpha=0.3)

    plt.suptitle("Computational Complexity Analysis — JRMSU Scheduler",
                 fontsize=14, fontweight="bold", y=1.02)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    print(f"  ✅ Chart saved to: {output_path}")


# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────

def main():
    print()
    print("╔═══════════════════════════════════════════════════════════════════════╗")
    print("║   JRMSU Scheduling System — Computational Complexity Benchmark      ║")
    print("╚═══════════════════════════════════════════════════════════════════════╝")
    print()
    print(f"  Input sizes:     {INPUT_SIZES}")
    print(f"  Trials per size: {NUM_TRIALS}")
    print(f"  Constant resources: {NUM_ROOMS} rooms, {NUM_INSTRUCTORS} instructors, "
          f"{NUM_DAYS} days, {NUM_TIME_BLOCKS} time blocks")
    print()

    all_results = {}

    # ── 1. K-Means Clustering ──────────────────────────────────────────────
    if HAS_SKLEARN:
        print("▶ Benchmarking K-Means Clustering...")
        km_timings = _benchmark(bench_kmeans, INPUT_SIZES)
        km_sizes = list(km_timings.keys())
        km_times = list(km_timings.values())
        km_r2 = _fit_complexity(km_sizes, km_times)
        km_ratios = _growth_ratios(km_sizes, km_times)
        _print_table("K-Means Clustering (subject clustering)", km_sizes, km_times, km_r2, km_ratios)
        all_results["K-Means\nClustering"] = {
            "sizes": km_sizes, "times": km_times, "best_fit": _best_fit(km_r2)
        }

    # ── 2. Greedy Scheduler ────────────────────────────────────────────────
    print("▶ Benchmarking Greedy Scheduler...")
    gr_timings = _benchmark(bench_greedy, INPUT_SIZES)
    gr_sizes = list(gr_timings.keys())
    gr_times = list(gr_timings.values())
    gr_r2 = _fit_complexity(gr_sizes, gr_times)
    gr_ratios = _growth_ratios(gr_sizes, gr_times)
    _print_table("Greedy Scheduler (first-fit fallback)", gr_sizes, gr_times, gr_r2, gr_ratios)
    all_results["Greedy\nScheduler"] = {
        "sizes": gr_sizes, "times": gr_times, "best_fit": _best_fit(gr_r2)
    }

    # ── 3. CP-SAT Model Construction (reduced) ─────────────────────────────
    if HAS_ORTOOLS:
        print("▶ Benchmarking CP-SAT Model Construction (reduced variable space)...")
        cp_red_timings = _benchmark(bench_cpsat_model_build_reduced, INPUT_SIZES)
        cp_red_sizes = list(cp_red_timings.keys())
        cp_red_times = list(cp_red_timings.values())
        cp_red_r2 = _fit_complexity(cp_red_sizes, cp_red_times)
        cp_red_ratios = _growth_ratios(cp_red_sizes, cp_red_times)
        _print_table("CP-SAT Model Build (reduced/realistic)", cp_red_sizes, cp_red_times, cp_red_r2, cp_red_ratios)
        all_results["CP-SAT Model\n(Reduced)"] = {
            "sizes": cp_red_sizes, "times": cp_red_times, "best_fit": _best_fit(cp_red_r2)
        }

    # ── 4. CP-SAT Model Construction (full) ─────────────────────────────────
    if HAS_ORTOOLS:
        # Use smaller sizes for the full model build (it explodes quadratically+)
        full_sizes = [s for s in INPUT_SIZES if s <= 40]
        if full_sizes:
            print("▶ Benchmarking CP-SAT Model Construction (full variable space)...")
            print(f"  (Using sizes up to {max(full_sizes)} to keep runtime manageable)")
            cp_full_timings = _benchmark(bench_cpsat_model_build, full_sizes)
            cp_full_sizes = list(cp_full_timings.keys())
            cp_full_times = list(cp_full_timings.values())
            cp_full_r2 = _fit_complexity(cp_full_sizes, cp_full_times)
            cp_full_ratios = _growth_ratios(cp_full_sizes, cp_full_times)
            _print_table("CP-SAT Model Build (full/naive)", cp_full_sizes, cp_full_times, cp_full_r2, cp_full_ratios)
            all_results["CP-SAT Model\n(Full)"] = {
                "sizes": cp_full_sizes, "times": cp_full_times, "best_fit": _best_fit(cp_full_r2)
            }

    # ── Summary ────────────────────────────────────────────────────────────
    print()
    print("=" * 80)
    print("  SUMMARY — Best-Fit Complexity Classes")
    print("=" * 80)
    print()
    print(f"  {'Component':<40}  {'Best-Fit Complexity':<20}")
    print(f"  {'─' * 40}  {'─' * 20}")
    for name, data in all_results.items():
        clean_name = name.replace("\n", " ")
        print(f"  {clean_name:<40}  {data['best_fit']:<20}")
    print()

    # Theoretical comparison
    print("  ┌─────────────────────────────────────────────────────────────────────┐")
    print("  │  Theoretical Complexity Reference:                                 │")
    print("  │                                                                    │")
    print("  │  K-Means:         O(n · k · i · d)  ≈ O(n) when k,i,d constant   │")
    print("  │  Greedy:          O(S · D · T · R · I)  polynomial                │")
    print("  │  CP-SAT Build:    O(S · R · D · T · I) for vars + pairwise constr │")
    print("  │  CP-SAT Solve:    NP-hard (bounded by timeout = 120s)             │")
    print("  │                                                                    │")
    print("  │  S=subjects, R=rooms, D=days, T=time blocks, I=instructors        │")
    print("  │  n=n_samples, k=clusters, i=iterations, d=features               │")
    print("  └─────────────────────────────────────────────────────────────────────┘")
    print()

    # ── Generate chart ─────────────────────────────────────────────────────
    output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "complexity_results.png")
    _generate_chart(all_results, output_path)

    print()
    print("  ✅ Benchmark complete!")
    print()


if __name__ == "__main__":
    main()
