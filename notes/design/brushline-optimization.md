# Brushline Optimization and Multi-Objective Search

Status: draft for Phase 0 review
Phase: P0
Date: 2026-11-14
Task: P0.8
Related: ADR 0006, `notes/design/brushline-architecture.md`

## 1. Purpose

The joint choice of where and when to treat, and where and when to monitor, is an NP-hard combinatorial
problem. Brushline does not build another solver. It implements a problem adapter over the released
`fresh-solutions` engine, adds a multi-objective archive, and validates the result on small instances. The
Pareto archive feeds the planning studio.

This note records the formulation, the adapter boundary, the search stack, the archive, the validation,
and the budget and reproducibility rules.

## 2. Why the problem is hard

A corridor of `S` segments over `T` periods with `A` actions has `A^(S*T)` naive combinations. The
constraints couple the choices:

- a budget and a cash ceiling in each period;
- contractor capacity and seasonality;
- access windows and crew travel;
- spatial continuity and adjacency along the corridor graph;
- service levels and asset clearance;
- monitoring decisions that change the information available for later decisions;
- multiple objectives that trade cost, risk, service, and uncertainty.

The problem contains a scheduling problem, a resource-constrained selection problem, and a partially
observable information problem. There is no claim of optimality for realistic instances.

## 3. Decision variables

### 3.1 Treatment

For each segment `s` and period `t`:

```text
x[s, t] in {none, method_1, method_2, ..., method_k, method_k + intensity_2, ...}
```

The option encodes the method, the intensity, and, where the contract requires it, the season. A segment
can carry at most one treatment per period. A treatment unit is a soft grouping of adjacent segments; the
model may schedule a subset if the contract allows it.

### 3.2 Monitoring

For each span `p` and period `t`:

```text
m[p, t] in {none, sensor_1, sensor_2, ..., sensor_j, sensor_j + sampling_2, ...}
```

The option encodes the sensor, the resolution, the route pattern, and the sampling intensity. A
monitoring action covers a span, not a single segment, because the mission travels along the corridor.

### 3.3 Contractor and resource assignment

For the tactical model, an optional variable assigns a treatment unit to a contractor, crew, or machine.
The strategic model leaves it to a capacity constraint; the operational model resolves it to a schedule.

### 3.4 Budget and service-level choices

The strategic model may include a plan-level budget and service-level choice. Those are scalar decisions
that change the constraint set, not per-segment actions.

## 4. Constraints

### 4.1 Hard constraints

- budget and cash by period;
- contractor capacity by period and method;
- access and seasonality;
- safety and environmental buffers;
- asset clearance and service standards;
- contractual windows;
- monitoring budget and sensor availability;
- data availability for a planned action.

### 4.2 Soft constraints

- service-level targets;
- risk targets;
- budget smoothness;
- workforce smoothness;
- equity across regions or communities;
- preference for continuity of work.

Soft constraints become penalty terms or objective dimensions, with the weight and the normalization
recorded.

### 4.3 Spatial constraints

- continuity of work along a span;
- adjacency of treated segments where the method requires it;
- crew travel along the corridor graph;
- monitoring route feasibility;
- no treatment in a segment that is inaccessible in the period.

### 4.4 Temporal constraints

- regrowth delay or green-up;
- seasonality;
- monitoring interval;
- a minimum or maximum time between treatments;
- a treatment that cannot follow another method within a stated window.

## 5. Objective vector

The first release uses four dimensions:

| Dimension | Direction | Unit | Notes |
| --- | --- | --- | --- |
| Present cost | minimize | currency | Treatment, monitoring, access, supervision, overhead, risk |
| Service risk | minimize | expected loss or index | Clearance, fall-in, fuel connectivity, access, reliability |
| Service attainment | maximize | fraction or index | The owner's service-level targets |
| Uncertainty | minimize | interval width or expected regret | The state uncertainty after the plan |

The vector is not collapsed into one number by default. A scalarization is a choice, and the archive keeps
the vector. The weights, the normalization, and the scalarization portfolio are visible in the archive
manifest.

## 6. The Fresh Solutions adapter

### 6.1 Contract

Brushline implements `fresh_solutions.contracts.ProblemAdapter`:

```python
class BrushlineAdapter(ProblemAdapter):
    name: str
    variable_count: int

    def option_count(self, variable: int) -> int: ...
    def option_at(self, variable: int, option: int) -> object: ...
    def initial_assignment(self) -> dict[int, int]: ...
    def random_assignment(self, rng: random.Random) -> dict[int, int]: ...
    def mutate(self, assignment, rate, rng) -> dict[int, int]: ...
    def crossover(self, left, right, rng) -> dict[int, int]: ...
    def evaluate(self, assignment) -> Evaluation: ...
    def evaluate_batch(self, assignments) -> list[Evaluation]: ...
    def propose(self, assignment, rng) -> Change | None: ...
    def apply(self, assignment, change) -> dict[int, int]: ...
    def undo(self, assignment, change) -> dict[int, int]: ...
```

The adapter maps a variable index to `(segment or span, period)` and an option index to an action. The
mapping is stable and serialized in the run manifest.

### 6.2 Exact evaluator

The exact evaluator is the Brushline simulator:

- apply the schedule to the initial state;
- grow and transition each segment;
- accumulate cost, service, risk, and uncertainty;
- check hard feasibility and report violations;
- return `Evaluation(objective, feasible, details)`.

The evaluator is the source of truth. The batch path and the incremental path must agree with it.

### 6.3 Incremental path

The search needs a fast delta. The evaluator supports:

- a resident state with apply/undo;
- a cache keyed by the changed segment, period, and downstream effects;
- a fallback to the full evaluation when the cache cannot prove the delta;
- a test that the incremental result equals the full result.

The first release may start with a full evaluation and add the incremental path after profiling. The
contract includes both, so the search does not need a rewrite.

## 7. Search stack

| Layer | Provider | Brushline use |
| --- | --- | --- |
| Local search | `fresh_solutions.run_local_search` | Single-solution improvement, annealing |
| Population search | `fresh_solutions.run_population_search` | Diverse seeds, crossover |
| Hybrid handoff | `fresh_solutions.run_hybrid_search` | Population elites refined by exact local search |
| Convergence stopping | `fresh_solutions.run_to_convergence` | Budget certification and patience |
| Checkpoints | `fresh_solutions.SearchCheckpoint` | Long runs, resume, audit |
| Evidence | `fresh_solutions.EvidenceRecord` | Exact replay |
| Batch backend | `fresh_solutions.CpuBatchBackend` | Exact CPU batch; GPU later |

Brushline adds:

- the operator portfolio (toggle, shift, swap, segment block, monitoring move, repair);
- the multi-objective archive;
- the scalarization portfolio;
- the budget policy and the seed policy;
- the run artifact writer.

### 7.1 Operators

- **Toggle:** add or remove a treatment or monitoring action.
- **Shift:** move an action to another period.
- **Swap:** exchange two actions or two periods.
- **Block move:** move a contiguous run of segments to another period.
- **Method change:** change the treatment method or intensity.
- **Monitoring move:** change the span, sensor, or sampling intensity.
- **Repair:** restore budget, capacity, or service feasibility after a move.
- **Destroy-repair:** remove a set of actions and rebuild them greedily.

Each operator has a unit test and a property test that apply/undo restores the exact state.

### 7.2 Seeds and budgets

- Every run records its seed, budget, stopping rule, and package versions.
- A multi-start run records each start's seed.
- A parallel island run records the island seeds and the best island.
- A budget is reported with the result; a result without a budget is incomplete.
- A negative result is retained.

## 8. Multi-objective archive

### 8.1 Archive policy

- A scalarization portfolio covers the objective space: cost-first, risk-first, service-first,
  uncertainty-first, and balanced.
- Each scalarization runs a search with its own seed and budget.
- Every incumbent is evaluated on the full objective vector.
- The archive keeps the non-dominated set under the declared directions.
- Diversity is maintained with a crowding distance or a grid; the method is recorded.
- The archive has a maximum size; the eviction rule is recorded.

### 8.2 `pareto.json`

```json
{
  "schema_version": "brushline.pareto.v1",
  "instance_id": "example-corridor",
  "run_id": "run-001",
  "objectives": [
    {"name": "present_cost", "direction": "minimize", "unit": "CAD"},
    {"name": "service_risk", "direction": "minimize", "unit": "index"},
    {"name": "service_attainment", "direction": "maximize", "unit": "fraction"},
    {"name": "uncertainty", "direction": "minimize", "unit": "index"}
  ],
  "scalarizations": [
    {"id": "cost-first", "weights": {"present_cost": 0.7, "service_risk": 0.1, "service_attainment": 0.1, "uncertainty": 0.1}}
  ],
  "members": [
    {
      "plan_id": "plan-001",
      "objective": {"present_cost": 1200000.0, "service_risk": 0.18, "service_attainment": 0.96, "uncertainty": 0.12},
      "feasible": true,
      "seed": 17,
      "evidence": "evidence-001.json",
      "plan": "plan-001.json"
    }
  ],
  "eviction": "crowding-distance",
  "created_utc": "2026-11-14T00:00:00Z"
}
```

### 8.3 Promotion

The studio can promote an archive member to a plan version. The promotion records:

- the archive member and its evidence record;
- the promotion reason and the operator;
- the new plan version and its parent;
- the data and model versions.

Promotion does not rerun the search. It does not claim that the member is the best compromise; it records
the choice.

## 9. Exact validation

- **Exhaustive enumeration:** a tiny corridor with a small state space and a known optimum.
- **Independent bound:** a mixed-integer or constraint-programming bound on a small instance where
  practical.
- **Exact/batch agreement:** every assignment in the tiny instance evaluates the same on both paths.
- **Replay:** every reported incumbent replays to the same objective and feasibility.
- **Property tests:** apply/undo restores the state; the archive is non-dominated; the promotion keeps the
  objective vector.

The exact validation is a test in the repository, not a claim about realistic instances.

## 10. Performance and scale

The first target is provisional:

- 10,000 segments;
- 30 years;
- 1,000 candidate schedule evaluations;
- 8 cores;
- under 10 minutes.

The design supports:

- vectorized state transitions;
- sparse or class-based state storage;
- incremental evaluation;
- parallel islands and scenarios;
- cached terrain, canopy, and route products;
- a batch evaluator for the population path;
- a checkpoint and resume path.

The prototype measures the real cost. The target is revised with evidence, not silently dropped.

## 11. Reproducibility

Every run records:

- the Brushline version and the adapter version;
- the `fresh-solutions` version;
- the dataset version and digest;
- the model ids and versions;
- the scenario, targets, weights, and normalization;
- the seed, budget, and stopping rule;
- the operator portfolio and the archive policy;
- the hardware and the wall-clock time.

Every incumbent has an evidence record. The simulator is deterministic given a schedule. The search is
reproducible from its seed and configuration.

## 12. What Brushline does not claim

- It does not claim global optimality for realistic instances.
- It does not claim that a scalarization is the decision-maker's preference.
- It does not hide an infeasible solution behind a scalar objective.
- It does not report a benchmark win without an exact, replayable schedule.
- It does not replace a MIP solver for a small exact problem; MIP remains a validation and bound tool.

## 13. Acceptance criteria

- The adapter satisfies the Fresh Solutions contract and passes the contract tests.
- The exact and batch evaluators agree on the tiny instance.
- Apply/undo restores the exact state.
- Every reported incumbent replays.
- The archive keeps only non-dominated members and records its policy.
- The studio can read `pareto.json` and promote a member.
- A tiny instance reaches the known optimum within a stated budget, or the gap is reported.
- The dashboard is green.

## 14. Open questions

| Question | Resolve in |
| --- | --- |
| How much of the state belongs in resident memory versus a recomputed cache? | P5 |
| Which operators are worth their complexity on a corridor graph? | P5 |
| How many scalarizations fit a practical budget? | P5 |
| How should uncertainty enter the objective without double counting? | P4 and P5 |
| When does a MIP bound add value over exhaustive enumeration? | P5 |
| How is the archive promoted into a plan without losing the evidence? | P9 and P10 |
