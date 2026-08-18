"""Import root for the disposable P0-A platform core.

Everything under this package is P0-A experiment code: the source- and
normalization-independent platform foundation described in
``docs/project-state.md`` under "P0-A boundary". It is reachable only through the
pytest path entry for ``experiments/integrated-p0``, never as an installed
distribution, so that under DP-001 no P1 runtime or package dependency can point
at it and P0 stays disposable rather than becoming the production foundation.
Nothing here may carry a source, acquisition, Raw, snapshot, or normalization
concern; those belong to P0-B and start only after the P0-A Completion Gate.
"""
