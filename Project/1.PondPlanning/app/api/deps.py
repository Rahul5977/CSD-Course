"""Shared router dependencies.

Small by design. Anything that grows logic belongs in an engine, not here.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Query, Response

from app.providers.fixtures import FIXTURE_HEADER


def mark_fixture(response: Response) -> None:
    """Stamp a response as fixture scaffolding.

    Declared as a dependency rather than written into each handler so that no
    fixture route can forget it, and so that deleting one line removes the mark
    when the real engine lands.
    """
    response.headers[FIXTURE_HEADER] = "true"


#: Applied to every route still backed by the fixture provider.
FixtureRoute = Depends(mark_fixture)


class Pagination:
    """Limit/offset paging, shared by every collection route."""

    def __init__(
        self,
        limit: Annotated[int, Query(ge=1, le=200)] = 50,
        offset: Annotated[int, Query(ge=0)] = 0,
    ) -> None:
        """Capture the validated paging window."""
        self.limit = limit
        self.offset = offset


PaginationDep = Annotated[Pagination, Depends(Pagination)]
