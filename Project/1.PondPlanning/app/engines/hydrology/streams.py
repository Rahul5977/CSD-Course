"""Stream network vectorisation with Strahler order.

Stream cells (accumulation above threshold) are traced downstream from every
source or junction to the next junction or outlet, giving one polyline per
link. **Strahler (1957) order** is then assigned in upstream-to-downstream
order: a link fed by two or more links of the same highest order takes that
order plus one; otherwise it inherits the highest order among its feeders.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from app.engines.hydrology.flow import FlowModel, donors


@dataclass(frozen=True, slots=True)
class StreamLink:
    """One channel segment between junctions, as grid cell centres."""

    cells: list[tuple[int, int]]  # upstream → downstream
    order: int
    upstream_cells_at_head: int
    upstream_cells_at_mouth: int

    def length_m(self, cell_size: float) -> float:
        """Polyline length in metres."""
        total = 0.0
        for (r0, c0), (r1, c1) in zip(self.cells, self.cells[1:], strict=False):
            total += cell_size * (np.sqrt(2.0) if r0 != r1 and c0 != c1 else 1.0)
        return float(total)


def extract_links(model: FlowModel, mask: np.ndarray) -> list[StreamLink]:
    """Trace the stream cells into links and assign Strahler order."""
    cols = model.shape[1]
    flat_mask = mask.ravel()
    receiver = model.receiver.ravel()
    offsets, idx = donors(model.receiver)

    def stream_donors(cell: int) -> list[int]:
        return [int(d) for d in idx[offsets[cell] : offsets[cell + 1]] if flat_mask[d]]

    stream_cells = np.nonzero(flat_mask)[0]
    n_donors = {int(c): len(stream_donors(int(c))) for c in stream_cells}
    heads = [c for c in stream_cells if n_donors[int(c)] != 1]  # sources and junction outlets
    # A junction cell starts a new link; its feeders' links end *at* it.
    links_raw: list[list[int]] = []
    for head in heads:
        head = int(head)
        path = [head]
        current = head
        while True:
            nxt = int(receiver[current])
            if nxt < 0 or not flat_mask[nxt]:
                break
            path.append(nxt)
            if n_donors[nxt] != 1:  # reached a junction: link ends there
                break
            current = nxt
        links_raw.append(path)

    # Strahler order, resolved from sources downstream.
    order_by_head: dict[int, int] = {}
    mouth_to_links: dict[int, list[int]] = {}
    for i, path in enumerate(links_raw):
        mouth_to_links.setdefault(path[-1], []).append(i)
    # process links by ascending accumulation at head (sources first)
    acc = model.accumulation.ravel()
    sequence = sorted(range(len(links_raw)), key=lambda i: acc[links_raw[i][0]])
    orders = [1] * len(links_raw)
    for i in sequence:
        head = links_raw[i][0]
        feeders = [j for j in mouth_to_links.get(head, []) if j != i]
        if feeders:
            top = max(orders[j] for j in feeders)
            orders[i] = top + 1 if sum(1 for j in feeders if orders[j] == top) >= 2 else top
        order_by_head[head] = orders[i]

    links = []
    for i, path in enumerate(links_raw):
        cells = [(int(c // cols), int(c % cols)) for c in path]
        links.append(
            StreamLink(
                cells=cells,
                order=orders[i],
                upstream_cells_at_head=int(acc[path[0]]),
                upstream_cells_at_mouth=int(acc[path[-1]]),
            )
        )
    return links
