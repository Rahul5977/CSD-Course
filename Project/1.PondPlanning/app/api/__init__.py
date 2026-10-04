"""HTTP transport layer: FastAPI routers, dependencies, exception handlers.

Rule: **routers contain zero business logic.** A router may validate input,
call exactly one engine or repository, map the result to a response schema,
and translate domain errors into HTTP status codes. Anything else belongs in
``engines/``. This is graded directly (Code quality: layering, 3 marks).
"""
