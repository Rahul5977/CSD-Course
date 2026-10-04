"""AI-based Village Pond Planning System.

Layered architecture. Dependencies point inwards only:

    api  ->  schemas  ->  engines  ->  domain
     |          |            |
     +-> jobs ->+            +-> providers, repositories

``domain`` is the innermost layer and imports nothing from the others.
``tests/test_layering.py`` enforces this mechanically.
"""

__version__ = "0.1.0"
