Optimization adapter and exact replay
=====================================

P5.4 maps Brushline onto the released `fresh-solutions` problem-adapter contract and records an
exactly replayable incumbent. Brushline supplies variables, options, exact evaluation, single-variable
proposals, apply/undo, and evidence. Fresh Solutions supplies local, population, hybrid, and
convergence search.

The core install does not require the optimizer. Install the optional extra before planning:

.. code-block:: console

   python -m pip install -e '.[opt]'

The adapter module itself imports without the extra; a search call imports Fresh Solutions.

Adapter contract
----------------

``BrushlineAdapter`` implements:

- ``variable_count`` and ``option_count``;
- ``option_at`` returning the stable Brushline option id;
- ``initial_assignment``, ``random_assignment``, ``mutate``, and ``crossover``;
- exact ``evaluate`` and ``evaluate_batch``;
- single-variable ``propose`` plus the typed ``propose_move`` for compound Brushline moves;
- reversible ``apply`` and ``undo``.

Random, mutated, and crossed assignments are passed through the P5.3 feasibility repair. Access and
locked-variable rules are honored.

Scalarization
-------------

Fresh Solutions needs a scalar. The adapter uses a declared ``Scalarization`` and converts
``service_attainment`` to a loss (``1 - value``). The four objective values remain in
``Evaluation.details`` and in the final ``SearchRun.objective_vector``.

The portfolio is ``cost_first``, ``risk_first``, ``service_first``, ``uncertainty_first``, and
``balanced``. A scalarization is a search weighting, not a replacement for the Pareto archive.

An infeasible assignment gets ``1e9`` per hard violation on top of its scalar. Feasibility is still
reported explicitly; the penalty only discourages the search from preferring an infeasible incumbent.

Search modes
------------

.. list-table::
   :header-rows: 1
   :widths: 20 80

   * - Mode
     - Fresh Solutions path
   * - ``local``
     - Simulated-annealing local search with ``iterations``, seed, temperature, and cooling.
   * - ``population``
     - Batched population search with population, generations, mutation, elite fraction, tournament,
       and random fraction.
   * - ``hybrid``
     - Population search followed by exact local refinement.
   * - ``convergence``
     - Population search followed by local rounds with patience, improvement threshold, round cap, and
       evaluation cap.

``SearchSpec.requested_budget`` records the requested evaluation budget; ``SearchRun.evaluations``
records the actual exact evaluations.

Replay and evidence
-------------------

Every run re-evaluates the reported assignment through the exact evaluator. The run fails if the
scalar, feasibility, or assignment coverage does not match. ``SearchRun`` carries:

- the seed, requested budget, mode, adapter name, and Fresh Solutions version;
- the assignment, scalar objective, four-objective vector, feasibility, evaluations, and history;
- the stop reason and optional checkpoint path;
- a Fresh Solutions ``EvidenceRecord`` mapping and ``replay_ok``.

``SearchRun`` rejects a record whose replay flag is false. ``replay_checkpoint`` loads a
``SearchCheckpoint``, verifies its objective, and returns a verified run.

.. code-block:: python

   from brushline.optimization.adapter import SearchSpec, run_search

   run = run_search(
       evaluator,
       SearchSpec(mode="local", instance_id="tiny", seed=7, iterations=100),
       checkpoint_path="runs/tiny/checkpoint.json",
   )
   assert run.replay_ok

Limits
------

- A scalar run does not enumerate the Pareto frontier; P5.5 owns the archive.
- Fresh Solutions search is a metaheuristic; no realistic-corridor optimality claim is made.
- The checkpoint stores the assignment, objective, seed, generation, and metadata; it does not store
  the full evaluator state.
- The adapter's compound moves are available through ``propose_move``; Fresh Solutions receives one
  reversible change at a time.
