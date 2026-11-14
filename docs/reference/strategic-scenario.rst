Strategic scenario archive
==========================

P6.6 records how a strategic plan was produced and verifies that the reconstructed portfolio and report
match the recorded artifacts. It references plan and report files; it does not duplicate their state.

Scenario record
---------------

``ScenarioVersions`` records the dataset version and digest, state/growth/treatment model versions,
adapter version, and Brushline version.

``StrategicScenario`` records the scenario and instance ids, versions, configuration and canonical
configuration digest, seed, budget, horizon, portfolio/report ids and paths, optional P5 archive path,
canonical portfolio/report digests, and timezone-aware creation time.

.. code-block:: python

   from brushline.strategic.scenario import build_scenario, replay_scenario

   scenario = build_scenario(
       scenario_id="strategy-v1",
       instance_id="corridor-1",
       versions=versions,
       configuration=configuration,
       portfolio=portfolio,
       report=report,
       seed=7,
       budget=100,
       horizon_years=10,
       portfolio_path="runs/strategy/portfolio.json",
       report_path="runs/strategy/report.json",
   )
   replay = replay_scenario(scenario, portfolio=portfolio, report=report)
   assert replay.ok

Canonical digests
-----------------

``canonical_digest`` serializes a JSON-like value with sorted keys, compact separators, ASCII output,
and the declared default string conversion, then hashes it with SHA-256. Key order therefore does not
change the digest.

Replay
------

``replay_scenario`` checks the portfolio and report ids and recomputes both digests. A missing artifact,
id mismatch, or digest mismatch is a named error. Replay does not reconstruct the objects from private
state; P6.7 supplies the reconstructed artifacts and verifies them.

Archive
-------

``ScenarioArchive`` uses ``brushline.strategic-scenario-archive.v1``. It carries scenarios, a creation
time, and a creator. ``validate_scenario_archive`` rejects duplicate scenario ids and an empty archive.
``write_scenario_archive`` and ``load_scenario_archive`` validate before writing/returning.

The committed example is ``notes/reference/p6-scenario.v1.json``.

Limits
------

- A digest proves artifact identity, not model correctness.
- Replay requires the caller to supply the reconstructed portfolio and report.
- Paths are references; the scenario writer does not copy the artifacts.
- No private data, credentials, or payloads are recorded.
