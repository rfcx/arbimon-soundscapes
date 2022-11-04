import png
from datetime import datetime
from functools import reduce
from ..a2pyutils import bmpio
from . import scidx


aggregations = {
    'time_of_day': {
        'date': ['%H'], 'projection': [1], 'range': [0,  23]
    },
    'day_of_month': {
        'date': ['%d'], 'projection': [1], 'range': [1,  31]
    },
    'day_of_year': {
        'date': ['%j'], 'projection': [1], 'range': [1, 366]
    },
    'month_in_year': {
        'date': ['%m'], 'projection': [1], 'range': [1,  12]
    },
    'day_of_week': {
        'date': ['%w'], 'projection': [1], 'range': [0,   6]
    },
    'year': {
        'date': ['%Y'], 'projection': [1], 'range': 'auto'
    }
}


class Soundscape():
    def __init__(self, aggregation, bin_size, max_bins, finp=None, amplitude_th=None, threshold_type=None):
        "Constructs a soundscape from a peaks file"
        self.aggregation = aggregation
        self.start_bin = 0
        self.max_bins = max_bins
        self.bin_size = bin_size
        self.amplitude_th = amplitude_th
        self.threshold_type = threshold_type
        self.max_list_global = None
        self.norm_vector = None
        bins = {}
        recordings = {}
        self.recstemp = {}
        max_list = None
        stats = {
            'min_idx': float('inf'),
            'max_idx': float('-inf'),
            'min_amp': float('inf'),
            'max_amp': 0,
            'max_count': 0
        }

        if finp is None:
            self.recordings = recordings
        else:
            for i in self.get_peak_list(finp):
                i_bin, i_idx, i_id = (i['bin'], i['idx'], i['id'])
                amp = i.get('amplitude', 255)
                stats['min_idx'] = min(stats['min_idx'], i_idx)
                stats['max_idx'] = max(stats['max_idx'], i_idx)
                stats['min_amp'] = min(stats['min_amp'], amp)
                stats['max_amp'] = max(stats['max_amp'], amp)

                recs = self.insert_rec_entry(
                    i_id, i_bin, i_idx, recordings, bins,
                    amp
                )

                if not max_list or len(max_list) < len(recs):
                    max_list = recs

            stats['max_count'] = len(max_list) if max_list else 0
            self.recordings = recordings.keys()
            self.recordings.sort()
        self.bins = bins
        self.stats = stats

    def insert_peaks(self, date, freqs, amplitudes, i_id):
        aggregation = self.aggregation
        max_bins = self.max_bins
        bin_size = self.bin_size
        max_list = self.max_list_global
        idx = int(sum([
            float(date.strftime(x)) * y for (x, y) in
            zip(aggregation['date'], aggregation['projection'])
        ]))
        self.stats['min_idx'] = min(self.stats['min_idx'], idx)
        self.stats['max_idx'] = max(self.stats['max_idx'], idx)
        for f, amp in zip(freqs, amplitudes):
            i_bin = min(int(f * 1000 / bin_size), max_bins)
            recs = self.insert_rec_entry(
                i_id, i_bin, idx, self.recstemp, self.bins,
                amp
            )
            self.stats['min_amp'] = min(self.stats['min_amp'], amp)
            self.stats['max_amp'] = max(self.stats['max_amp'], amp)

            if not max_list or len(max_list) < len(recs):
                max_list = recs
        self.max_list_global = max_list
        self.stats['max_count'] = len(max_list) if max_list else 0
        self.recordings = self.recstemp
        self.recordings = sorted(self.recordings.keys())

    @staticmethod
    def insert_rec_entry(i_id, i_bin, i_idx, recordings, bins, amp):
        if i_id not in recordings:
            recordings[i_id] = 1
        if i_bin not in bins:
            bins[i_bin] = {}
        bin = bins[i_bin]
        if i_idx not in bin:
            bin[i_idx] = {}
        recs = bin[i_idx]
        if i_id not in recs:
            recs[i_id] = amp
        return recs


    def get_peak_list(self, finp):
        "Generator that reads a file and yields peaks in an aggregated form"
        aggregation = self.aggregation
        max_bins = self.max_bins
        bin_size = self.bin_size
        hwhitelist = ["date", "id", "PeaksFrec", "Amplitud"]
        header = []
        for i, l in enumerate(finp):
            if i == 0:
                headers = [x.strip() for x in l.split(',')]
            else:
                l = dict([(x, y) for (x, y) in zip(
                    headers,
                    [x.strip() for x in l.split(',')]
                ) if x in hwhitelist])
                date = datetime.strptime(l['date'], '%m/%d/%Y %I:%M %p')
                l['idx'] = int(sum([
                    float(date.strftime(x)) * y for (x, y) in
                    zip(aggregation['date'], aggregation['projection'])
                ]))
                l['bin'] = min(
                    int(float(l['PeaksFrec']) * 1000 / bin_size),
                    max_bins
                )
                l['amplitude'] = l['Amplitud']

                del l['date']
                del l['PeaksFrec']
                del l['Amplitud']
                yield l

    @staticmethod
    def cols_gen(bin, scalefn, from_x, to_x, amp_th=None):
        "yields counts for each column in a cell"
        for x in range(from_x, to_x):
            if bin and x in bin:
                cell = bin[x]
                if amp_th:
                    v = reduce(lambda _, amp: _ + (1 if amp > amp_th else 0), cell.values(), 0)
                else:
                    v = len(cell) if cell else 0
            else:
                v = 0
            yield scalefn(v,x)

    @classmethod
    def rows_gen(cls, bins, scalefn, from_y, to_y, from_x, to_x, amp_th=None):
        "yields column iterators for each row in the index"
        for y in range(to_y-1, from_y-1, -1):
            yield cls.cols_gen(bins.get(y), scalefn, from_x, to_x, amp_th)

    def write_image(self, imgout, palette):
        "Writes the soundscape to an image file"

        agg_range = self.aggregation['range']
        if agg_range == 'auto':
            agg_range = [self.stats['min_idx'], self.stats['max_idx']]
        offsetx = agg_range[0]
        width = agg_range[1] - offsetx + 1
        height = self.max_bins
        bpp = 8

        if imgout[-4:] == ".png":
            w = png.Writer(
                width=width, height=height, bitdepth=bpp, palette=palette
            )
        else:
            w = bmpio.Writer(
                width=width, height=height, bitdepth=bpp, palette=palette
            )

        scale = self.stats['max_count']
        if scale == 0:
            scale = 1

        scalefn = lambda x, col: max(0, min(int(x * 255.0 / scale), 255))

        if self.norm_vector:
            scale = 1
            sfn = scalefn

            def nv_scalefn(x, col):
                nv = float(self.norm_vector.get(col, 1) or 1)
                v = sfn(x / nv, col)
                return v
            scalefn = nv_scalefn
            
        amplitude_th = self.amplitude_th
        if self.amplitude_th and self.threshold_type == 'relative-to-peak-maximum':
            amplitude_th = self.amplitude_th * self.stats['max_amp']

        fout = open(imgout, "wb")
        w.write(fout, self.rows_gen(
            self.bins, scalefn,
            0, height, offsetx, offsetx + width, amplitude_th
        ))

    def write_index(self, indexout):
        bins = self.bins
        recordings = self.recordings
        max_count = self.stats['max_count']
        agg_range = self.aggregation['range']
        if agg_range == 'auto':
            offsetx = self.stats['min_idx']
            width = self.stats['max_idx'] - offsetx + 1
        else:
            offsetx = agg_range[0]
            width = agg_range[1] - offsetx + 1
        offsety = 0
        height = self.max_bins

        scidx.write_scidx(
            indexout, bins, recordings,
            offsetx, width, offsety, height
        )

    @classmethod
    def read_from_index(self, filename):
        (version, bins, recordings, offsetx, width, offsety, height,
            minx, maxx, miny, maxy) = scidx.read_scidx(filename)
        aggregation = {
            "range": [offsetx, width + offsetx - 1]
        }
        obj = Soundscape(aggregation, -1, height)
        obj.recordings = recordings
        obj.stats = {
            "max_count": max(len(bins[x][y]) for x in bins for y in bins[x]),
            "min_amp": min(amp for row in bins.values() for cell in row.values() for amp in cell.values()),
            "max_amp": max(amp for row in bins.values() for cell in row.values() for amp in cell.values()),
            "min_idx": aggregation["range"][0],
            "max_idx": aggregation["range"][1]
        }
        obj.bins = bins
        return obj
