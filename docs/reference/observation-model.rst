Observation model
=================

P8.1 simulates coverage, detection, class confusion, measurement error, and latency.

``ObservationConfig`` sets coverage, detection probability, measurement standard deviation, a
class-confusion table, and latency. ``simulate_observation`` is deterministic from the request seed. It
returns detection, covered, observed class, noisy value, error, confidence, and latency.

A missing detection has no observed class or measurement. A class absent from the confusion table is
reported as the true class. The model is a decision-support approximation, not a sensor calibration.
