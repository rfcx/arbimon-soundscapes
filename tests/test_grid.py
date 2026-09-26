"""Unit tests for soundscapes/old/soundscape/grid.py (no DB, no S3).

The scidx fixture is written by the job's own writer (scidx.write_scidx) so the
reader is tested against the real on-disk format, not a hand-rolled copy.
"""
import gzip
import os
import random
import struct
import tempfile
from array import array

from soundscapes.old.soundscape import grid as G
from soundscapes.old.soundscape import scidx as S


def _write_fixture(index, recordings, offsetx, width, offsety, height):
    fd, path = tempfile.mkstemp(suffix='.scidx')
    os.close(fd)
    S.write_scidx(path, index, recordings, offsetx, width, offsety, height)
    with open(path, 'rb') as f:
        buf = f.read()
    os.unlink(path)
    return buf


def _random_index(seed, w, h, offx, offy, nrec, fill=0.6):
    rnd = random.Random(seed)
    recs = [100000 + i for i in range(nrec)]
    index = {}
    for y in range(h):
        for x in range(w):
            if rnd.random() > fill:
                continue
            k = rnd.randint(1, min(12, nrec))
            chosen = rnd.sample(recs, k)
            index.setdefault(offy + y, {})[offx + x] = {r: rnd.uniform(0.001, 9.0) for r in chosen}
    return index, recs


def test_parse_matches_writer():
    index, recs = _random_index(1, 24, 69, 0, 0, 40)
    buf = _write_fixture(index, recs, 0, 24, 0, 69)
    p = G.parse_scidx(buf)
    assert (p['width'], p['height'], p['offsetx'], p['offsety']) == (24, 69, 0, 0)
    assert sorted(p['recordings']) == sorted(recs)
    ncells = sum(len(r) for r in index.values())
    assert len(p['cells']) == ncells
    # every cell: same recording SET and same float32 amplitudes as written
    for yy, row in index.items():
        for xx, cell in row.items():
            ridx, amps = p['cells'][(yy - 0, xx - 0)]
            got = {p['recordings'][i]: a for i, a in zip(ridx, amps)}
            assert set(got) == set(cell)
            for r, a in cell.items():
                assert got[r] == array('f', [a])[0]


def test_grid_round_trip_bit_exact_with_offsets():
    index, recs = _random_index(2, 12, 30, 1, 3, 300)
    buf = _write_fixture(index, recs, 1, 12, 3, 30)
    p = G.parse_scidx(buf)
    grid, meta = G.encode_grid(p)
    counts, amps = G.decode_grid(grid, meta['width'], meta['height'])
    for y in range(30):
        for x in range(12):
            c = p['cells'].get((y, x))
            want = sorted(array('f', c[1])) if c else []
            got = list(amps[y * 12 + x])
            assert counts[y * 12 + x] == len(want)
            assert [struct.pack('<f', v) for v in got] == [struct.pack('<f', v) for v in want]
    assert meta['max_count'] == max(counts)


def test_encoding_is_deterministic():
    index, recs = _random_index(3, 24, 69, 0, 0, 60)
    p = G.parse_scidx(_write_fixture(index, recs, 0, 24, 0, 69))
    assert G.encode_grid(p)[0] == G.encode_grid(p)[0]      # gzip mtime pinned


def test_empty_soundscape():
    p = G.parse_scidx(_write_fixture({}, [], 0, 24, 0, 69))
    grid, meta = G.encode_grid(p)
    counts, amps = G.decode_grid(grid, 24, 69)
    assert sum(counts) == 0 and meta['max_count'] == 0 and meta['max_amp'] == 0.0


def _render_reference(p, meta, settings, nv):
    """Straight port of arbimon-legacy soundscape-image.js (the authoritative renderer)."""
    w, h = p['width'], p['height']
    maxc = max([len(c[0]) for c in p['cells'].values()] or [0])
    vmax = settings.get('visual_max_value')
    scale = float(vmax) if (vmax is not None and float(vmax) > 0) else float(maxc)
    scale = scale or 1.0
    normalized = bool(int(settings.get('normalized') or 0)) and nv
    if normalized:
        scale = 1.0
    th = float(settings.get('threshold') or 0)
    if th and settings.get('threshold_type') == 'relative-to-peak-maximum':
        th *= meta['max_amp']
    out = bytearray(w * h)
    for r in range(h):
        y = h - 1 - r
        for x in range(w):
            c = p['cells'].get((y, x))
            v = 0
            if c:
                v = sum(1 for a in c[1] if a > th) if (th and c[1]) else len(c[0])
            if normalized:
                v = v / (float(nv.get(str(p['offsetx'] + x), 1) or 1) or 1.0)
            out[r * w + x] = max(0, min(int(v * 255.0 / scale), 255))
    return bytes(out)


def test_preview_matches_reference_renderer_all_modes():
    index, recs = _random_index(4, 24, 69, 0, 0, 80, fill=0.8)
    p = G.parse_scidx(_write_fixture(index, recs, 0, 24, 0, 69))
    grid, meta = G.encode_grid(p)
    counts, amps = G.decode_grid(grid, 24, 69)
    nv = {str(x): (x % 5) + 1 for x in range(24)}
    modes = [
        dict(visual_max_value=None, normalized=0, threshold=0, threshold_type='absolute'),
        dict(visual_max_value=7, normalized=0, threshold=0, threshold_type='absolute'),
        dict(visual_max_value=None, normalized=0, threshold=2.5, threshold_type='absolute'),
        dict(visual_max_value=None, normalized=1, threshold=0.3, threshold_type='relative-to-peak-maximum'),
        dict(visual_max_value=4, normalized=1, threshold=0.05, threshold_type='absolute'),
        dict(visual_max_value=None, normalized=0, threshold=0.999, threshold_type='relative-to-peak-maximum'),
    ]
    for m in modes:
        want = _render_reference(p, meta, m, nv)
        got = gzip.decompress(G.preview(counts, amps, meta, m, nv))
        assert got == want, m


def _v1_scidx(width, height, recordings, cells):
    """Hand-build a VERSION 1 scidx (the writer only makes v2): same layout, but a
    cell is u16 count + rec indices with NO float32 amplitudes (the format that
    arbimon-legacy scidx.js reads when `version < 2`)."""
    rcbytes = 1 if len(recordings) < 256 else 2
    head = struct.pack('>6sHHHHH', b'SCIDX ', 1, 0, width, 0, height)
    head += struct.pack('>BBB', (len(recordings) >> 16) & 255, (len(recordings) >> 8) & 255, len(recordings) & 255)
    head += struct.pack('>B', rcbytes)
    body_start = len(head) + 8
    recs = b''.join(struct.pack('>Q', r) for r in recordings)
    rows_ptr_start = body_start + len(recs)
    rows_blob = b''
    row_ptrs = []
    base = rows_ptr_start + 8 * height
    for y in range(height):
        row_cells = {x: v for (yy, x), v in cells.items() if yy == y}
        if not row_cells:
            row_ptrs.append(0)
            continue
        row_off = base + len(rows_blob)
        row_ptrs.append(row_off)
        cell_blob = b''
        cptrs = []
        cstart = row_off + 8 * width
        for x in range(width):
            if x not in row_cells:
                cptrs.append(0)
                continue
            cptrs.append(cstart + len(cell_blob))
            idxs = row_cells[x]
            cell_blob += struct.pack('>H', len(idxs)) + b''.join(i.to_bytes(rcbytes, 'big') for i in idxs)
        rows_blob += b''.join(struct.pack('>Q', c) for c in cptrs) + cell_blob
    return head + struct.pack('>Q', rows_ptr_start) + recs + b''.join(struct.pack('>Q', r) for r in row_ptrs) + rows_blob

def test_v1_scidx_counts_only_grid():
    recs = [500 + i for i in range(9)]
    cells = {(0, 0): [0, 1, 2], (0, 3): [4], (2, 1): [1, 5, 6, 7, 8], (4, 5): [3]}
    p = G.parse_scidx(_v1_scidx(6, 5, recs, cells))
    assert p['version'] == 1 and p['recordings'] == recs
    assert p['cells'][(2, 1)] == ([1, 5, 6, 7, 8], [])
    grid, meta = G.encode_grid(p)
    assert meta['encoding'] == G.ENCODING_COUNTS and meta['max_amp'] == 0.0 and meta['max_count'] == 5
    assert len(gzip.decompress(grid)) == 6 * 5 * 2          # counts only, no body
    counts, amps = G.decode_grid(grid, 6, 5, meta['encoding'])
    assert counts[2 * 6 + 1] == 5 and counts[0] == 3 and sum(counts) == 10
    assert all(len(a) == 0 for a in amps)
    # a threshold cannot apply to v1 (no amplitudes) -- every renderer falls back to counts
    m = dict(visual_max_value=None, normalized=0, threshold=0.5, threshold_type='absolute')
    got = gzip.decompress(G.preview(counts, amps, meta, m, None))
    want = _render_reference(p, meta, m, None)
    assert got == want

def test_rejects_non_scidx():
    try:
        G.parse_scidx(b'NOTSCI' + b'\x00' * 40)
    except ValueError:
        return
    assert False, 'expected ValueError'