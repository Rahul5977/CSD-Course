"""Asynchronous job definitions and the worker entrypoint.

Terrain analysis takes tens of seconds, so analysis routes accept a request,
enqueue a job and return ``202`` with a poll URL. The async job architecture is
on the never-cut list (``ROADMAP.md`` §5).
"""
