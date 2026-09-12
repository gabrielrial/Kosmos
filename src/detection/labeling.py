"""Connected-component labelling.

Uses ``scipy.ndimage.label`` when SciPy is installed and falls back to a
run-length union-find otherwise, so the detectors work either way.
Both paths use 8-connectivity and return identical region sets.
"""

from __future__ import annotations

import numpy as np

try:  # pragma: no cover - depends on the environment
    from scipy import ndimage as _ndimage
except ImportError:  # pragma: no cover
    _ndimage = None


_STRUCTURE_8 = np.ones((3, 3), dtype=bool)


def label_components(mask: np.ndarray) -> tuple[np.ndarray, int]:
    """Label the True regions of ``mask`` with 8-connectivity.

    Returns ``(labels, count)`` where ``labels`` is an int32 array with 0 for
    background and 1..count for regions.
    """

    if mask.dtype != bool:
        mask = mask.astype(bool)

    if _ndimage is not None:
        labels, count = _ndimage.label(mask, structure=_STRUCTURE_8)
        return labels.astype(np.int32, copy=False), int(count)

    return _label_fallback(mask)


def _label_fallback(mask: np.ndarray) -> tuple[np.ndarray, int]:
    """Row-run union-find labelling, used when SciPy is unavailable."""

    height, width = mask.shape
    labels = np.zeros((height, width), dtype=np.int32)
    parent: list[int] = [0]

    def find(node: int) -> int:
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    def union(left: int, right: int) -> None:
        root_left, root_right = find(left), find(right)
        if root_left != root_right:
            parent[max(root_left, root_right)] = min(root_left, root_right)

    previous_runs: list[tuple[int, int, int]] = []

    for y in range(height):
        row = mask[y]
        if not row.any():
            previous_runs = []
            continue

        edges = np.diff(row.astype(np.int8))
        starts = (np.nonzero(edges == 1)[0] + 1).tolist()
        ends = (np.nonzero(edges == -1)[0] + 1).tolist()
        if row[0]:
            starts.insert(0, 0)
        if row[-1]:
            ends.append(width)

        current_runs: list[tuple[int, int, int]] = []
        for start, end in zip(starts, ends):
            run_label = 0
            # 8-connectivity: a run touches the previous row's run if their
            # column spans overlap when widened by one pixel on each side.
            for previous_start, previous_end, previous_label in previous_runs:
                if previous_start <= end and start <= previous_end:
                    if run_label == 0:
                        run_label = find(previous_label)
                    else:
                        union(run_label, previous_label)
            if run_label == 0:
                run_label = len(parent)
                parent.append(run_label)
            labels[y, start:end] = run_label
            current_runs.append((start, end, run_label))
        previous_runs = current_runs

    if len(parent) == 1:
        return labels, 0

    # Flatten the union-find and renumber the surviving roots to 1..count.
    roots = np.array([find(node) for node in range(len(parent))], dtype=np.int32)
    used = np.unique(roots[1:])
    renumber = np.zeros(len(parent), dtype=np.int32)
    renumber[used] = np.arange(1, len(used) + 1, dtype=np.int32)
    labels = renumber[roots[labels]]
    return labels, int(len(used))


def region_sums(labels: np.ndarray, count: int, values: np.ndarray) -> np.ndarray:
    """Sum ``values`` per label. Index 0 holds the background sum."""

    return np.bincount(
        labels.ravel(), weights=values.ravel(), minlength=count + 1
    )


def region_areas(labels: np.ndarray, count: int) -> np.ndarray:
    """Pixel count per label. Index 0 holds the background count."""

    return np.bincount(labels.ravel(), minlength=count + 1)


def region_bounds(labels: np.ndarray, count: int) -> np.ndarray:
    """Bounding boxes per label as an array of ``(y0, y1, x0, x1)`` rows.

    Bounds are inclusive. Row 0 (background) is filled with zeros.
    """

    bounds = np.zeros((count + 1, 4), dtype=np.int32)
    if count == 0:
        return bounds

    ys, xs = np.nonzero(labels)
    if len(ys) == 0:
        return bounds

    flat = labels[ys, xs]
    order = np.argsort(flat, kind="stable")
    flat, ys, xs = flat[order], ys[order], xs[order]
    starts = np.searchsorted(flat, np.arange(1, count + 1), side="left")
    stops = np.searchsorted(flat, np.arange(1, count + 1), side="right")

    for index, (start, stop) in enumerate(zip(starts, stops), start=1):
        if start >= stop:
            continue
        bounds[index] = (
            ys[start:stop].min(),
            ys[start:stop].max(),
            xs[start:stop].min(),
            xs[start:stop].max(),
        )
    return bounds
