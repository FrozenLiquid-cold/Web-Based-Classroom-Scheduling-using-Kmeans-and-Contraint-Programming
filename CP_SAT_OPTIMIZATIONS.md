# CP-SAT Optimization Plan

## Optimization Areas Identified

### 1. Variable Domain Reduction
- **Current**: Fixed step_size = rec_slots
- **Optimization**: Adaptive step_size based on problem size and available options
- **Impact**: 20-40% reduction in variables for large problems

### 2. Variable Naming
- **Current**: Long descriptive names (e.g., `start_c{subject_id}_r{room_id}_s{global_start}_i{instructor_id}_dur{num_slots}`)
- **Optimization**: Shorter names using indices
- **Impact**: 5-10% memory reduction, faster constraint building

### 3. Constraint Tightness
- **Current**: Basic OnlyEnforceIf constraints
- **Optimization**: Add inverse constraints, use AddExactlyOne for mutual exclusivity
- **Impact**: Better propagation, 10-20% faster solving

### 4. Solver Parameters
- **Current**: Basic parameter set
- **Optimization**: Enhanced parameters for better propagation and search
- **Impact**: 15-30% faster solving, better solution quality

### 5. Hint Selection
- **Current**: Up to 5000 hints, sorted by value
- **Optimization**: More selective hint application (top N per subject)
- **Impact**: Better warm-start, faster convergence

### 6. Objective Precomputation
- **Current**: Computed during objective building
- **Optimization**: Precompute objective coefficients during variable creation
- **Impact**: Faster model building, cleaner code

### 7. Interval Constraint Optimization
- **Current**: Good use of intervals
- **Optimization**: Batch interval creation, optimize grouping
- **Impact**: Slightly faster constraint building

## Proposed Changes

All changes preserve:
- ✅ Scheduling logic (same constraints, same meaning)
- ✅ Data model (no schema changes)
- ✅ Constraint semantics (same rules enforced)
- ✅ Solution quality (same or better)

Only improving:
- ⚡ Formulation efficiency
- ⚡ Variable definitions
- ⚡ Search strategies
- ⚡ OR-Tools best practices

