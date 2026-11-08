"""Conservative polygon masks for Landscape Grass weights (groundcover_mask.py, #100). Pure Python, no Unreal.

Grass weight is evaluated at landscape vertices (2 m apart on L_vilm) and interpolated between them, and the mask is
sampled bilinearly at each vertex. So for no plant to get weight inside a polygon, every cell the polygon touches is
blacked out (not only cells whose centres are inside), then grown by DILATE cells: one for the mask's own bilinear
footprint, one for the vertex interpolation (a 2 m cell is one vertex step).
"""

import math

DILATE = 2


def fill(pixels, width, height, points):
    """Zero every cell the closed polygon touches. Points are in cell units (cell (i, j) spans [i, i+1) x [j, j+1))."""
    edges = list(zip(points, points[1:] + points[:1]))
    for row in range(height):  # cells whose centre is inside (even-odd scanline)
        y = row + 0.5
        crossings = sorted(a[0] + (y - a[1]) * (b[0] - a[0]) / (b[1] - a[1]) for a, b in edges if (a[1] <= y) != (b[1] <= y))
        for left, right in zip(crossings[::2], crossings[1::2]):
            start, end = max(0, math.ceil(left - 0.5)), min(width, math.floor(right - 0.5) + 1)
            if end > start:
                pixels[row * width + start:row * width + end] = bytes(end - start)
    for a, b in edges:  # cells an edge passes through, which the centre test misses along the boundary
        steps = max(1, math.ceil(math.hypot(b[0] - a[0], b[1] - a[1]) * 8))
        for k in range(steps + 1):
            x, y = a[0] + (b[0] - a[0]) * k / steps, a[1] + (b[1] - a[1]) * k / steps
            i, j = math.floor(x), math.floor(y)
            for di in (-1, 0) if x == i else (0,):  # a point on a cell border touches both cells
                for dj in (-1, 0) if y == j else (0,):
                    if 0 <= i + di < width and 0 <= j + dj < height:
                        pixels[(j + dj) * width + i + di] = 0


def dilate(pixels, width, height, cells=DILATE):
    """Grow the zero cells by `cells` in every direction (a square neighbourhood)."""
    out = bytearray(pixels)
    for j in range(height):
        for i in range(width):
            if pixels[j * width + i] == 0:
                for jj in range(max(0, j - cells), min(height, j + cells + 1)):
                    out[jj * width + max(0, i - cells):jj * width + min(width, i + cells + 1)] = bytes(
                        min(width, i + cells + 1) - max(0, i - cells))
    return out


def bilinear(pixels, width, height, x, y):
    """The mask value at (x, y) in cell units, as a clamped bilinear texture sample (texel centres at i + 0.5)."""
    fx, fy = x - 0.5, y - 0.5
    i, j = math.floor(fx), math.floor(fy)
    tx, ty = fx - i, fy - j

    def at(a, b):
        return pixels[min(max(b, 0), height - 1) * width + min(max(a, 0), width - 1)]

    top = at(i, j) * (1 - tx) + at(i + 1, j) * tx
    bottom = at(i, j + 1) * (1 - tx) + at(i + 1, j + 1) * tx
    return top * (1 - ty) + bottom * ty
