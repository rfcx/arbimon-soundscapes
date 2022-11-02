import os
import time
import shutil
import multiprocessing
from joblib import Parallel, delayed
from .soundscape import soundscape
from .indices import indices
from .a2pyutils import palette
from .process_rec import process_rec

def folder_to_soundscape(folder, output_folder, agr_ident = 'time_of_day'):
    num_cores = multiprocessing.cpu_count()

    working_folder = output_folder+"/results/"
    if os.path.exists(working_folder):
        shutil.rmtree(working_folder)
    os.makedirs(working_folder)

    aggregation = soundscape.aggregations.get(agr_ident)

    if not aggregation:
        print("# Wrong agregation.")
        return None
    imgout = 'image.png'
    scidxout = 'index.scidx'
    threshold = 0
    frequency = 0
    bin_size = 86
    if bin_size < 0:
        print("# Bin size must be a positive number. Input was: " + str(bin_size))
        return None

    recs_to_process = os.listdir(folder)
    if len(recs_to_process) < 1:
        print("no recordings on folder.")
        return None

    peaknumbers = indices.Indices(aggregation)

    hIndex = indices.Indices(aggregation)

    aciIndex = indices.Indices(aggregation)

    start_time_all = time.time()
    resultsParallel = Parallel(n_jobs=num_cores)(
        delayed(process_rec)(folder + '/' + recordingi, bin_size, frequency) for recordingi in recs_to_process
    )
    if len(resultsParallel) > 0:
        max_hertz = 22050
        for result in resultsParallel:
            if result is not None:
                if   max_hertz < result['recMaxHertz']:
                    max_hertz = result['recMaxHertz']
        max_bins = int(max_hertz / bin_size)
        scp = soundscape.Soundscape(aggregation, bin_size, max_bins)
        start_time_all = time.time()
        i = 0
        for result in resultsParallel:
            if result is not None:
                i = i + 1
                if result['freqs'] is not None:
                    if len(result['freqs']) > 0:
                        scp.insert_peaks(result['date'], result['freqs'], result['amps'], i)
                    peaknumbers.insert_value(result['date'] ,len(result['freqs']),i)
                if result['h'] is not None:
                    hIndex.insert_value(result['date'] ,result['h'],i)
                if result['aci'] is not None:
                    aciIndex.insert_value(result['date'] ,result['aci'],i)

        scp.write_index(working_folder+scidxout)

        peaknFile = working_folder+'peaknumbers'
        peaknumbers.write_index_aggregation_json(peaknFile+'.json')

        hFile = working_folder+'h'
        hIndex.write_index_aggregation_json(hFile+'.json')

        aciFile = working_folder+'aci'
        aciIndex.write_index_aggregation_json(aciFile+'.json')

        if aggregation['range'] == 'auto':
            statsMin = scp.stats['min_idx']
            statsMax = scp.stats['max_idx']
        else:
            statsMin = aggregation['range'][0]
            statsMax = aggregation['range'][1]

        scp.write_image(working_folder + imgout, palette.get_palette())

    else:
        print('no results')

