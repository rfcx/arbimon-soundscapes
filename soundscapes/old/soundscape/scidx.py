import struct
import math

VERSION = 2


class file_pointer_write_loc(object):
    def __init__(self, f, relative_pos=0):
        self.f = f
        self.pos = f.tell()
        self.relative_pos = relative_pos
        f.write(struct.pack(">Q", 0))

    def update(self):
        f = self.f
        pos = f.tell()
        wpos = pos
        if self.relative_pos:
            wpos -= self.relative_pos

        f.seek(self.pos)
        f.write(struct.pack(">Q", wpos))
        f.seek(pos)


def uint2BEbytes(x, n):
    return [(x >> (8*i)) & 0xff for i in range(n-1, -1, -1)]


def BEbytes2uint(b):
    v = sum([long(b[i]) << (8*(len(b) - 1 - i)) for i in range(len(b))])
    return v


def write_scidx(filename, index, recordings, offsetx, width, offsety, height):
    "Writes a scidx file to the given filename, given the index attributes"
    fout = open(filename, "wb")
    rcount = len(recordings)
    if rcount == 0:
        rcbytes = 1
    else:
        rcbytes = int(math.ceil(math.log(rcount, 2)/8.0))
    rcfmt = ">" + ("B"*rcbytes)
    rec_idx = {}
    # write header
    # file :
    #     field 	desc
    #     "SCIDX " 	6 byte magic number
    #     version   2 byte uint
    #     offsetx   2 byte uint
    #     width 	2 byte uint
    #     offsety   2 byte uint
    #     height 	2 byte uint
    #     rec_count 	3 byte uint
    #     rec_bytes 	1 byte uint
    #     rows_ptr_start 	array of 8 byte file offset from start - indicates
    #                       begining of rows_ptr[] array
    #     recs[] 	array of rec structures of size rec_count
    #     rows_ptr[] 	array of 8 byte file offset from start - indicates
    #                       begining of each entry of rows[]
    #     rows[] 	array of row structures of size height
    fout.write(struct.pack('>6sHHHHH', 'SCIDX '.encode('utf-8'), VERSION, offsetx, width, offsety, height))
    fout.write(struct.pack(">BBB", *uint2BEbytes(rcount, 3)))
    fout.write(struct.pack(">B", rcbytes))
    # setup file_pointer_write_loc for writing start of row pointers array
    rows_ptr_start = file_pointer_write_loc(fout)
    # write list of recording ids
    # rec structure :
    #     field 	desc
    #     rec_id 	8 byte uint - id of the recording in the database
    for i, rec in enumerate(recordings):
        fout.write(struct.pack(">Q", int(rec)))
        rec_idx[rec] = i
    # update the rows_ptr_start location to the current file position
    rows_ptr_start.update()
    # setup an array of file positions (one per row)
    row_pointers = [file_pointer_write_loc(fout) for y in range(height)]
    # write each row
    # row structure :
    #     field 	desc
    #     cells_ptr[] 	array of 8 byte offsets from the beginning of the
    #                   row structure - indicates begining of each entry of
    #                   cells[]
    #     cells[] 	array of cell structures of size width
    for y in range(height):
        off_y = offsety + y
        # if the row is in the index, then:::
        if off_y in index:
            # update the row_pointers[y] location to the current file position
            row_pointers[y].update()
            row = index[off_y]
            # fout.write(struct.pack(">6s", "[ROW ]"))
            # setup an array of positions relative to row (one per cell)
            cell_pointers = [
                file_pointer_write_loc(fout)  # , row_pointers[y].pos)
                for x in range(width)
            ]
            # write each cell
            # cell structure :
            #     field 	desc
            #     count 	2 byte uint - number of recordings in indices[]
            #     indices[] 	array of rec_bytes byte uints of size count -
            #                   indicates indices in recs[] lists
            for x in range(width):
                off_x = offsetx + x
                # if the row is in the index, then:::
                if off_x in row:
                    # update the cell_pointers[x] location to the current
                    # file position, relative to row_pointers[y]
                    cell_pointers[x].update()
                    cell = row[off_x]
                    rec_count = len(cell)
                    # fout.write(struct.pack(">6s", "[CELL]"))
                    fout.write(struct.pack(">H", rec_count))
                    recs, amps = cell.keys(), cell.values()
                    for rec in recs:
                        fout.write(struct.pack(
                            rcfmt, *uint2BEbytes(rec_idx[rec], rcbytes)
                        ))
                    fout.write(struct.pack(">"+("f"*rec_count), *amps))


def read_cell_recs(finp, rcfmt, rcbytes, count):
    p = finp.tell()
    finp.seek(0, 2)
    fp = finp.tell()
    finp.seek(p)
    for i in range(count):
        assert(finp.tell() < fp)
        yield BEbytes2uint(struct.unpack(
            rcfmt, finp.read(rcbytes)
        ))


def read_scidx(filename, filter=None):
    "Reads a scidx file, given the filename"
    index = {}

    if not filter:
        filter = {}
    minx, maxx, miny, maxy = [filter.get(f, v) for f, v in zip(
        ['minx', 'maxx', 'miny', 'maxy'],
        [float('-inf'), float('inf'), float('-inf'), float('inf')],
    )]

    finp = file(filename, "rb")
    finp.seek(0, 2)
    fendpos = finp.tell()
    finp.seek(0)
    # read header
    # file :
    #     field 	desc
    #     "SCIDX " 	6 byte magic number
    #     version   2 byte uint
    #     offsetx   2 byte uint
    #     width 	2 byte uint
    #     offsety   2 byte uint
    #     height 	2 byte uint
    #     rec_count 	3 byte uint
    #     rec_bytes 	1 byte uint
    #     rows_ptr_start 	array of 8 byte file offset from start - indicates
    #                       begining of rows_ptr[] array
    #     recs[] 	array of rec structures of size rec_count
    #     rows_ptr[] 	array of 8 byte file offset from start - indicates
    #                   begining of each entry of rows[]
    #     rows[] 	array of row structures of size height
    magic, version, offsetx, width, offsety, height = struct.unpack(
        ">6sHHHHH", finp.read(16)
    )

    if not filter.get("ignore_offsets", False):
        minx -= offsetx
        maxx -= offsetx
        miny -= offsety
        maxy -= offsety

    rcount = BEbytes2uint(struct.unpack(">BBB", finp.read(3)))
    rcbytes, = struct.unpack(">B", finp.read(1))
    rcfmt = ">" + ("B"*rcbytes)
    # read pointer of start of row pointers array
    rows_ptr_start, = struct.unpack(">Q", finp.read(8))
    # read list of recording ids
    # rec structure :
    #     field 	desc
    #     rec_id 	8 byte uint - id of the recording in the database
    recordings = struct.unpack(">" + ("Q" * rcount), finp.read(8 * rcount))
    # seek to pointer of start of row pointers array
    finp.seek(rows_ptr_start)
    # read array of file positions of each row
    row_pointers = struct.unpack(">" + ("Q" * height), finp.read(8 * height))
    # read each row
    # row structure :
    #     field 	desc
    #     cells_ptr[] 	array of 8 byte offsets from the beginning of the row
    #                   structure - indicates begining of each entry of cells[]
    #     cells[] 	array of cell structures of size width
    for y in range(height):
        if row_pointers[y] and miny <= y <= maxy:
            # seek to the location of the current row
            finp.seek(row_pointers[y])
            off_y = offsety + y
            row = {}
            index[off_y] = row
            # syncer, = struct.unpack(">6s", finp.read(6))
            # print "(%s, %s) row : %r : %s <= %s <= %s :: %s x %s" % (
            #     hex(row_pointers[y]), hex(fendpos), syncer, miny, y,
            #     maxy, width, height
            # )
            # read array positions relative to row (one per cell)
            cell_pointers = struct.unpack(
                ">" + ("Q" * width), finp.read(8 * width)
            )
            # print cell_pointers
            # read each cell
            # cell structure :
            #     field 	desc
            #     count 	2 byte uint - number of recordings in indices[]
            #     indices[] 	array of rec_bytes byte uints of size count -
            #                   indicates indices in recs[] lists
            for x in range(width):
                if cell_pointers[x] and minx <= x <= maxx:
                    # seek to cell location denoted by cell_pointers[x],
                    # relative to row_pointers[y]
                    # finp.seek(cell_pointers[x] + row_pointers[y])
                    finp.seek(cell_pointers[x])
                    # syncer, = struct.unpack(">6s", finp.read(6))
                    # print "(%s, %s)   cell : %r : %s <= %s <= %s :: %s" % (
                    #     hex(cell_pointers[x]),
                    #     hex(fendpos),
                    #     syncer, minx, x,
                    #     maxx, width
                    # )
                    cell_count, = struct.unpack(">H", finp.read(2))
                    # print cell_count, rcfmt, rcbytes
                    cell_recs = [
                        i  # recordings[i]
                        for i in read_cell_recs(finp, rcfmt, rcbytes, cell_count)
                    ]
                    if version >= 2:
                        cell_amps = struct.unpack(
                            ">" + ("f" * cell_count), finp.read(4 * cell_count)
                        )
                    else:
                        cell_amps = [1024] * cell_count
                    row[offsetx + x] = dict(zip(cell_recs, cell_amps))
    return (version, index, recordings, offsetx, width, offsety, height,
            minx, maxx, miny, maxy)
