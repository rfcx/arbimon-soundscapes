"""Soundscape heat-map grid: exact, compact, DB-stored (2026-09-25).

Replaces the per-render .scidx fetch for PIXELS. The .scidx stays the source of
truth for per-peak recording identity (region recording lists, raw export).

Design + evidence: rfcx-local runbooks/evidence/irr-ledger-20260925-soundscape-grid-and-membership.md
(render parity, IRR pass 4: 0 of 10,013,892 pixels differ from the server renderer).

`grid` ENCODING 3 (the bytea stored in arbimon.soundscape_grids.grid), gzip of:

    counts   : width*height x uint16 LE, row-major, y = 0..height-1 (scidx row
               order = frequency bin from offsety), x = 0..width-1
    amps     : for every cell in the same order, its `count` peak amplitudes,
               float32, SORTED ASCENDING, stored as the IEEE-754 bit patterns
               delta-coded within the cell (uint32 wrapping subtraction from the
               previous value in that cell, first value from 0), then the whole
               uint32 array is byte-plane shuffled (all byte0s, all byte1s, ...),
               little-endian.

Sorted + delta + shuffle is what makes float32 compress (IRR pass 6: ~20-30 %
smaller than raw interleaved f32, bit-exact round trip). Every render mode needs
per-cell count(amp > th) for arbitrary th, which a sorted array answers exactly
by binary search; a count-only grid would be wrong for the 85 % of soundscapes
that use a threshold, and quantised amplitudes were measured inexact.

Also here: `parse_scidx` (a Python 3 reader for the v2 .scidx the job writes)
and `preview` (palette index per cell at the soundscape's stored settings).
"""
import gzip
import json
import struct
from array import array

ENCODING = 3          # counts + sorted amplitudes (scidx v2)
ENCODING_COUNTS = 1   # counts only (scidx v1 stores no amplitudes)
SCIDX_MAGIC = b'SCIDX '


# --------------------------------------------------------------- .scidx reader
def parse_scidx(buf):
    """Parse a v2 .scidx byte string.

    Returns dict(offsetx, width, offsety, height, recordings=[rec_id...],
    cells={(y, x): (rec_indices[list], amps[list of float])}) where y/x are
    0-based within the grid (offsets NOT applied), matching the writer.
    """
    if buf[:6] != SCIDX_MAGIC:
        raise ValueError('not a SCIDX file')
    version, offsetx, width, offsety, height = struct.unpack_from('>HHHHH', buf, 6)
    # v1 (early soundscapes) stores NO amplitudes: each cell is count + recording
    # indices only (arbimon-legacy scidx.js reads amps only `if version >= 2`).
    # Threshold rendering is impossible for v1 in every renderer, so a count-only
    # cell (amps = []) reproduces them exactly.
    if version not in (1, 2):
        raise ValueError('unsupported scidx version %r' % version)
    rcount = (buf[16] << 16) | (buf[17] << 8) | buf[18]
    rcbytes = buf[19]
    rows_ptr_start, = struct.unpack_from('>Q', buf, 20)
    recordings = list(struct.unpack_from('>%dQ' % rcount, buf, 28))
    row_ptrs = struct.unpack_from('>%dQ' % height, buf, rows_ptr_start)
    cells = {}
    for y in range(height):
        rp = row_ptrs[y]
        if not rp:
            continue
        cell_ptrs = struct.unpack_from('>%dQ' % width, buf, rp)
        for x in range(width):
            cp = cell_ptrs[x]
            if not cp:
                continue
            count, = struct.unpack_from('>H', buf, cp)
            p = cp + 2
            recs = []
            for _ in range(count):
                v = 0
                for b in range(rcbytes):
                    v = (v << 8) | buf[p + b]
                recs.append(v)
                p += rcbytes
            amps = list(struct.unpack_from('>%df' % count, buf, p)) if version >= 2 else []
            cells[(y, x)] = (recs, amps)
    return dict(version=version, offsetx=offsetx, width=width, offsety=offsety,
                height=height, recordings=recordings, cells=cells)


# ------------------------------------------------------------------ encoding 3
def _f32_bits_sorted(amps):
    a = array('f', amps)            # float32, exactly as stored in the scidx
    a = array('f', sorted(a))
    b = array('I')
    b.frombytes(a.tobytes())        # reinterpret as uint32 (native = little-endian)
    return b


def encode_grid(parsed):
    """Encode a parsed scidx to (grid_bytes, meta).

    meta = dict(width, height, offsetx, offsety, max_count, max_amp, encoding).
    encoding 1 (counts only) is used for v1 scidx files, which carry no
    amplitudes: the grid body is then just the u16 counts.
    """
    w, h = parsed['width'], parsed['height']
    counts_only = parsed.get('version', 2) < 2
    cells = parsed['cells']
    counts = array('H', [0]) * (w * h)
    deltas = array('I')
    max_count, max_amp = 0, 0.0
    for y in range(h):
        for x in range(w):
            c = cells.get((y, x))
            if not c:
                continue
            recs, amps = c
            n = len(recs)
            if n > 0xFFFF:
                raise ValueError('cell count %d exceeds uint16' % n)
            counts[y * w + x] = n
            if n > max_count:
                max_count = n
            if counts_only:
                continue
            if len(amps) != n:
                raise ValueError('cell (%d,%d): %d amplitudes for %d recordings' % (y, x, len(amps), n))
            bits = _f32_bits_sorted(amps)
            prev = 0
            for v in bits:
                deltas.append((v - prev) & 0xFFFFFFFF)
                prev = v
            if amps:
                m = max(array('f', amps))
                if m > max_amp:
                    max_amp = m
    if counts.itemsize != 2 or deltas.itemsize != 4:
        raise RuntimeError('unexpected array item sizes')
    cbytes = counts.tobytes() if _little() else _swap(counts).tobytes()
    raw = deltas.tobytes() if _little() else _swap(deltas).tobytes()
    n = len(deltas)
    shuffled = bytearray(len(raw))
    for b in range(4):                           # byte-plane shuffle
        shuffled[b * n:(b + 1) * n] = raw[b::4]
    grid = gzip.compress(cbytes + bytes(shuffled), compresslevel=6, mtime=0)
    return grid, dict(width=w, height=h, offsetx=parsed['offsetx'], offsety=parsed['offsety'],
                      max_count=max_count, max_amp=float(array('f', [max_amp])[0]),
                      encoding=ENCODING_COUNTS if counts_only else ENCODING)


def decode_grid(grid, width, height, encoding=ENCODING):
    """Inverse of encode_grid -> (counts[list], amps[list of array('f') sorted]).
    For encoding 1 every amps entry is empty (no amplitudes exist)."""
    raw = gzip.decompress(grid)
    ncell = width * height
    counts = array('H')
    counts.frombytes(raw[:ncell * 2])
    if not _little():
        counts = _swap(counts)
    if encoding == ENCODING_COUNTS:
        if len(raw) != ncell * 2:
            raise ValueError('encoding 1 grid has a body')
        return list(counts), [array('f') for _ in range(ncell)]
    body = raw[ncell * 2:]
    n = len(body) // 4
    if n != sum(counts):
        raise ValueError('grid body %d values != sum(counts) %d' % (n, sum(counts)))
    un = bytearray(len(body))
    for b in range(4):
        un[b::4] = body[b * n:(b + 1) * n]
    deltas = array('I')
    deltas.frombytes(bytes(un))
    if not _little():
        deltas = _swap(deltas)
    out, k = [], 0
    for c in counts:
        bits = array('I')
        prev = 0
        for _ in range(c):
            prev = (prev + deltas[k]) & 0xFFFFFFFF
            bits.append(prev)
            k += 1
        f = array('f')
        f.frombytes(bits.tobytes())
        out.append(f)
    return list(counts), out


# ------------------------------------------------------------------- preview
def _count_above(sorted_amps, th):
    lo, hi = 0, len(sorted_amps)
    while lo < hi:
        m = (lo + hi) // 2
        if sorted_amps[m] > th:
            hi = m
        else:
            lo = m + 1
    return len(sorted_amps) - lo


def preview(counts, amps, meta, settings, norm_vector=None):
    """u8 palette index per cell (row-major, TOP row = highest frequency bin,
    i.e. display order), gzip. Same math as arbimon-legacy
    app/utils/soundscape-image.js renderSoundscapePng.

    settings: visual_max_value, normalized, threshold, threshold_type.
    """
    w, h = meta['width'], meta['height']
    vmax = settings.get('visual_max_value')
    scale = float(vmax) if (vmax is not None and float(vmax) > 0) else float(meta['max_count'])
    if not scale:
        scale = 1.0
    normalized = bool(int(settings.get('normalized') or 0)) and norm_vector
    if normalized:
        scale = 1.0
    th = float(settings.get('threshold') or 0)
    if th and settings.get('threshold_type') == 'relative-to-peak-maximum':
        th = th * float(meta['max_amp'])
    out = bytearray(w * h)
    offx = meta['offsetx']
    for r in range(h):
        y = h - 1 - r
        for x in range(w):
            i = y * w + x
            v = counts[i]
            if th and len(amps[i]):
                v = _count_above(amps[i], th)
            if normalized:
                d = float(norm_vector.get(str(offx + x), norm_vector.get(offx + x, 1)) or 1) or 1.0
                v = v / d
            out[r * w + x] = max(0, min(int(v * 255.0 / scale), 255))
    return gzip.compress(bytes(out), compresslevel=6, mtime=0)


def norm_vector_json(nv):
    return json.dumps({str(k): int(v) for k, v in (nv or {}).items()}, sort_keys=True) if nv else None


def _little():
    import sys
    return sys.byteorder == 'little'


def _swap(a):
    b = array(a.typecode, a)
    b.byteswap()
    return b