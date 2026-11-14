LiDAR benchmark
===============

The benchmark compares Brushline, FEMIC, WS4, and FHOPS values on the same pinned bundle, segment,
CRS, resolution, vertical datum, statistic, buffer, and valid-pixel rule. It is deterministic and
offline; it does not call a sibling runtime or read a payload.

The committed fixture is ``notes/reference/lidar-benchmark.v1.json``.

Request
-------

A ``BenchmarkRequest`` pins:

- a benchmark id, bundle id, bundle version, and segment id;
- the product ids and SHA-256 checksums;
- one shared ``BenchmarkContract``;
- one or more metrics with Brushline and sibling values, absolute and relative tolerances.

Each ``BenchmarkValue`` has a consumer, value, provenance, contract, optional missing reason, and a
required flag. A comparison must declare the same contract as the request. A different CRS, resolution,
vertical datum, statistic, buffer, or valid-pixel rule fails with ``BENCHMARK-CONTRACT``.

The committed fixture compares:

- elevation mean;
- slope mean;
- CHM mean;
- cover at 10 m.

The values are synthetic benchmark evidence, not a live multi-repository integration.

.. code-block:: python

   from datetime import UTC, datetime
   from pathlib import Path
   from brushline.integrations.lidar_benchmark import (
       BenchmarkRequest,
       run_lidar_benchmark,
       validate_lidar_benchmark,
   )

   request = BenchmarkRequest.model_validate_json(
       Path("notes/reference/lidar-benchmark.v1.json").read_text()
   )
   report = run_lidar_benchmark(
       request,
       created_utc=datetime(2026, 11, 14, tzinfo=UTC),
   )
   assert validate_lidar_benchmark(report).is_valid

Tolerance and missing values
----------------------------

A comparison passes when the absolute difference is within the absolute tolerance **or** the relative
difference is within the relative tolerance. The report records both differences and both tolerances.

A missing value:

- fails when it is required;
- fails when it has no reason;
- is a warning when it is optional and explained.

A required missing value is not silently skipped. The benchmark report names the metric, consumer, and
reason.

States
------

.. list-table::
   :header-rows: 1
   :widths: 20 80

   * - Status
     - Meaning
   * - ``pass``
     - Within the absolute or relative tolerance.
   * - ``fail``
     - Outside both tolerances.
   * - ``missing``
     - No value; required or unexplained missing is an error, optional explained missing is a warning.
   * - ``contract``
     - The consumer contract differs from the shared contract.

The report includes a hash of the pinned product checksums and the benchmark request. The same request
and values produce the same cases.

Named errors
------------

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Prefix
     - Meaning
   * - ``BENCHMARK-TOLERANCE``
     - A difference is outside both tolerances.
   * - ``BENCHMARK-CONTRACT``
     - A consumer uses a different measurement contract.
   * - ``BENCHMARK-MISSING``
     - A required value is missing, or a missing value has no reason.
   * - ``BENCHMARK-STATUS``, ``BENCHMARK-CASE``
     - Unknown case status or an inconsistent pass/fail record.
   * - ``BENCHMARK-ID``
     - Duplicate case key.
   * - ``BENCHMARK-TIME``
     - The report time is not timezone-aware.
   * - ``BENCHMARK-EMPTY``
     - No cases (warning).

Limits
------

- The sibling values are a committed benchmark fixture, not a live WS4 or FHOPS run.
- The benchmark does not prove that a consumer is correct; it records whether the values agree within
  the stated tolerance.
- A difference outside the tolerance stops the claim of agreement. It does not trigger an automatic
  correction.
