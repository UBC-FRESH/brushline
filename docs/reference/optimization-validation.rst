Tiny-instance validation
========================

P5.6 checks correctness by exhaustive enumeration on a tiny formulation. It is a proof for that
finite instance only; it is not an optimality claim for a realistic corridor.

The committed formulation is ``notes/reference/p5-formulation.v1.json`` and the committed optimum is
``notes/reference/p5-tiny-optimum.v1.json``. The tiny instance has 6 variables and 324 assignments.

Enumerate and compare
---------------------

``enumerate_assignments`` returns every complete variable-to-option assignment in stable order.
``exhaustive_optimum`` evaluates all assignments twice:

1. one exact evaluation per assignment;
2. one exact batch evaluation.

``TinyOptimum.batch_agreement`` is true only when every pair matches. The best feasible scalar is kept;
ties are counted and resolved by the lexicographically smallest assignment. If no feasible assignment
exists, the optimum fields are ``None``.

.. code-block:: python

   from brushline.optimization.validation import (
       exhaustive_optimum,
       validate_tiny_instance,
   )

   optimum = exhaustive_optimum(evaluator, weights)
   assert optimum.batch_agreement
   report = validate_tiny_instance(evaluator, weights=weights, search=run)
   assert report.replay_ok

Known optimum
-------------

The committed tiny optimum is balanced-scalarized:

- 324 assignments;
- 72 feasible assignments;
- unique best assignment;
- best assignment ``{0: 1, 1: 1, 2: 0, 3: 0, 4: 0, 5: 0}``;
- best vector: present cost 100, near-zero service risk, service attainment 1, uncertainty 0.3253.

The best plan mows the shrub segment in both periods. A no-action plan misses the hard service height
after growth.

Search evidence
---------------

``validate_tiny_instance`` compares an optional ``SearchRun`` with the exhaustive optimum:

- ``gap`` is search scalar minus optimum scalar for a feasible search result;
- ``gap`` is ``None`` for an infeasible search or an instance with no feasible assignment;
- ``reaches_optimum`` is true only at a zero gap;
- ``replay_ok`` re-evaluates the search assignment and compares feasibility and scalar value;
- ``expected_ok`` compares a committed optimum's assignment, objective, and assignment count.

A positive gap is reported, not hidden.

Reports
-------

``TinyOptimum`` uses ``brushline.tiny-optimum.v1``. ``TinyValidationReport`` uses
``brushline.tiny-validation.v1`` and embeds the optional search run. Both have JSON writers and loaders.

Limits
------

- 324 assignments is a unit test, not a production search.
- The exhaustive result depends on the declared weights and contexts.
- Batch agreement checks exact evaluator plumbing, not model correctness.
- No MIP/CP bound is claimed; the finite enumeration is the bound for this instance.
