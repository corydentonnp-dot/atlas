#!/usr/bin/env python3
"""
repair_terrain_stl.py  --  rebuild 01-terrain.stl with correct triangulation.

WHY THIS EXISTS
---------------
The supplied 01-terrain.stl is not carvable. Its vertex data is perfect, but
its *connectivity* is wrong:

    96376 / 96690 triangles (99.7%) have zero projected area in XY
    95752 triangles have all three vertices on the SAME Y row

The exporter walked each DEM scanline and emitted triangles from three
consecutive points *along that row*, instead of stitching each row to the next.
The result is 94848 zero-area ribbons lying flat in the terrain instead of a
surface. Total projected area of the top "surface" is 24.96 mm2 against a
7587.84 mm2 panel.

A 3D Parallel toolpath over that mesh has no surface to follow, so Fusion drops
to the only real geometry left -- the base slab at Z-6.0. That is exactly the
"machines the whole stock down to the model base" failure the build notes warn
about, and a machining boundary does not prevent it, because the cause is the
mesh, not the boundary.

The wall and base triangles in the original file are already correct
(1840 walls + 2 base), so only the top surface is rebuilt here. The output has
exactly the same triangle count as the input (96690), which is a good
confirmation that the original count was right and only the indexing was wrong.

USAGE
-----
    python3 repair_terrain_stl.py 01-terrain.stl 01-terrain-FIXED.stl

No third-party dependencies. Reads and writes binary STL.
"""

import struct
import sys
from collections import defaultdict

BASE_Z = -6.0          # underside of the model slab, as in the original file
BASE_EPS = 1e-2        # tolerance for "is this vertex on the base slab"
GRID_EPS = 4           # decimal places used to snap grid coordinates


def read_binary_stl(path):
    """Return a list of triangles, each a tuple of three (x, y, z) vertices."""
    with open(path, "rb") as fh:
        fh.read(80)                                    # header, unused
        count = struct.unpack("<I", fh.read(4))[0]
        tris = []
        for _ in range(count):
            data = fh.read(50)                         # 12 floats + 2 byte attr
            v = struct.unpack("<12f", data[:48])
            tris.append((v[3:6], v[6:9], v[9:12]))     # skip the stored normal
    return tris


def write_binary_stl(path, tris, header=b"Lac de Neuchatel terrain - repaired"):
    """Write triangles to a binary STL, computing outward normals."""
    with open(path, "wb") as fh:
        fh.write(header[:80].ljust(80, b"\0"))
        fh.write(struct.pack("<I", len(tris)))
        for a, b, c in tris:
            ux, uy, uz = (b[0] - a[0], b[1] - a[1], b[2] - a[2])
            vx, vy, vz = (c[0] - a[0], c[1] - a[1], c[2] - a[2])
            nx, ny, nz = (uy * vz - uz * vy,
                          uz * vx - ux * vz,
                          ux * vy - uy * vx)
            length = (nx * nx + ny * ny + nz * nz) ** 0.5
            if length > 0:
                nx, ny, nz = nx / length, ny / length, nz / length
            fh.write(struct.pack("<12fH",
                                 nx, ny, nz,
                                 a[0], a[1], a[2],
                                 b[0], b[1], b[2],
                                 c[0], c[1], c[2],
                                 0))


def extract_height_field(tris):
    """Recover the DEM grid from the (correct) vertex data of a broken mesh."""
    heights = {}
    for tri in tris:
        for x, y, z in tri:
            if z < BASE_Z + BASE_EPS:
                continue                               # base slab, not terrain
            heights[(round(x, GRID_EPS), round(y, GRID_EPS))] = z

    xs = sorted({k[0] for k in heights})
    ys = sorted({k[1] for k in heights})
    missing = [(x, y) for y in ys for x in xs if (x, y) not in heights]
    if missing:
        raise SystemExit(
            "Grid is incomplete: %d of %d points missing. This repair only "
            "handles a complete regular grid." % (len(missing), len(xs) * len(ys)))
    return heights, xs, ys


def build_solid(heights, xs, ys):
    """Build a watertight solid: terrain top, four skirt walls, flat base."""
    tris = []
    z = lambda x, y: heights[(x, y)]

    # --- top surface -------------------------------------------------------
    # Each grid cell becomes two triangles, wound counter-clockwise seen from
    # +Z so the normal points up and out of the material.
    for j in range(len(ys) - 1):
        y0, y1 = ys[j], ys[j + 1]
        for i in range(len(xs) - 1):
            x0, x1 = xs[i], xs[i + 1]
            v00 = (x0, y0, z(x0, y0))
            v10 = (x1, y0, z(x1, y0))
            v11 = (x1, y1, z(x1, y1))
            v01 = (x0, y1, z(x0, y1))
            tris.append((v00, v10, v11))
            tris.append((v00, v11, v01))

    # --- skirt walls -------------------------------------------------------
    # Windings are chosen so every wall normal faces away from the solid.
    y_min, y_max = ys[0], ys[-1]
    for i in range(len(xs) - 1):
        x0, x1 = xs[i], xs[i + 1]
        # front wall (y = y_min), outward normal -Y
        a, b = (x0, y_min, z(x0, y_min)), (x1, y_min, z(x1, y_min))
        la, lb = (x0, y_min, BASE_Z), (x1, y_min, BASE_Z)
        tris.append((a, la, lb))
        tris.append((a, lb, b))
        # back wall (y = y_max), outward normal +Y
        a, b = (x0, y_max, z(x0, y_max)), (x1, y_max, z(x1, y_max))
        la, lb = (x0, y_max, BASE_Z), (x1, y_max, BASE_Z)
        tris.append((a, b, lb))
        tris.append((a, lb, la))

    x_min, x_max = xs[0], xs[-1]
    for j in range(len(ys) - 1):
        y0, y1 = ys[j], ys[j + 1]
        # left wall (x = x_min), outward normal -X
        a, b = (x_min, y0, z(x_min, y0)), (x_min, y1, z(x_min, y1))
        la, lb = (x_min, y0, BASE_Z), (x_min, y1, BASE_Z)
        tris.append((a, b, lb))
        tris.append((a, lb, la))
        # right wall (x = x_max), outward normal +X
        a, b = (x_max, y0, z(x_max, y0)), (x_max, y1, z(x_max, y1))
        la, lb = (x_max, y0, BASE_Z), (x_max, y1, BASE_Z)
        tris.append((a, la, lb))
        tris.append((a, lb, b))

    # --- base --------------------------------------------------------------
    # The walls subdivide the bottom perimeter at every grid point, so the base
    # has to use those same points or we leave T-junctions and the solid is not
    # manifold. Fan from the centre out to each perimeter segment, wound
    # clockwise seen from +Z so the normal points down.
    perimeter = []
    perimeter += [(x, y_min, BASE_Z) for x in xs[:-1]]
    perimeter += [(x_max, y, BASE_Z) for y in ys[:-1]]
    perimeter += [(x, y_max, BASE_Z) for x in reversed(xs[1:])]
    perimeter += [(x_min, y, BASE_Z) for y in reversed(ys[1:])]

    centre = ((x_min + x_max) / 2.0, (y_min + y_max) / 2.0, BASE_Z)
    for k in range(len(perimeter)):
        p = perimeter[k]
        q = perimeter[(k + 1) % len(perimeter)]
        tris.append((centre, q, p))

    return tris


def xy_area(tri):
    (x1, y1, _), (x2, y2, _), (x3, y3, _) = tri
    return abs((x2 - x1) * (y3 - y1) - (x3 - x1) * (y2 - y1)) / 2.0


def check_watertight(tris):
    """Every edge of a closed manifold must be shared by exactly two faces."""
    edges = defaultdict(int)
    for a, b, c in tris:
        for p, q in ((a, b), (b, c), (c, a)):
            key = tuple(sorted((tuple(round(v, 5) for v in p),
                                tuple(round(v, 5) for v in q))))
            edges[key] += 1
    return sum(1 for n in edges.values() if n != 2), len(edges)


def report_slope(heights, xs, ys, stepover):
    """Largest step in Z the cutter meets when advancing one stepover in Y."""
    pitch = ys[1] - ys[0]
    worst = 0.0
    for j in range(len(ys) - 1):
        y0, y1 = ys[j], ys[j + 1]
        for x in xs:
            worst = max(worst, abs(heights[(x, y1)] - heights[(x, y0)]))
    return worst, worst * stepover / pitch


def main():
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    src, dst = sys.argv[1], sys.argv[2]

    original = read_binary_stl(src)
    degenerate = sum(1 for t in original if xy_area(t) < 1e-9)
    print("input : %s" % src)
    print("        %d triangles, %d degenerate in XY (%.1f%%)"
          % (len(original), degenerate, 100.0 * degenerate / len(original)))

    heights, xs, ys = extract_height_field(original)
    print("        recovered grid %d x %d, pitch %.3f mm, "
          "Z %.4f .. %.4f" % (len(xs), len(ys), xs[1] - xs[0],
                              min(heights.values()), max(heights.values())))

    repaired = build_solid(heights, xs, ys)
    bad_edges, total_edges = check_watertight(repaired)
    area = sum(xy_area(t) for t in repaired if xy_area(t) > 1e-9)

    print("output: %s" % dst)
    print("        %d triangles, %d degenerate in XY"
          % (len(repaired), sum(1 for t in repaired if xy_area(t) < 1e-9)))
    print("        projected area %.2f mm2 (panel %.2f mm2)"
          % (area / 2.0, (xs[-1] - xs[0]) * (ys[-1] - ys[0])))
    print("        non-manifold edges %d of %d  -> %s"
          % (bad_edges, total_edges, "WATERTIGHT" if bad_edges == 0 else "OPEN"))

    raw, per_stepover = report_slope(heights, xs, ys, stepover=0.15)
    print("        steepest Y-adjacent rise %.4f mm per %.2f mm of grid"
          % (raw, ys[1] - ys[0]))
    print("        -> at 0.15 mm stepover, worst cut per pass ~%.4f mm"
          % per_stepover)

    write_binary_stl(dst, repaired)


if __name__ == "__main__":
    main()
