"""Business logic: hydrology, runoff, pond design, suitability.

Pure and testable — engines take plain inputs (arrays, domain objects) and
return domain objects. They never touch HTTP, and they reach storage only
through a ``repositories`` or ``providers`` Protocol passed in by the caller.
Every engine docstring names the algorithm it implements and cites its source.
"""
