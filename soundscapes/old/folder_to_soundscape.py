import os
import time
import shutil
import multiprocessing
from joblib import Parallel, delayed
from .soundscape import soundscape
from .indices import indices
from .a2pyutils import palette
from .process_rec import process_rec

def folder_to_soundscape(folder, output_folder, aggregation = 'time_of_day', bin_size = 86, threshold = 0, threshold_type = 'absolute', frequency = 0, normalize = 1):
    num_cores = multiprocessing.cpu_count()

    working_folder = output_folder+"/results/"
    if os.path.exists(working_folder):
        shutil.rmtree(working_folder)
    os.makedirs(working_folder)

    aggregation_params = soundscape.aggregations.get(aggregation)
    if not aggregation_params:
        print("# Wrong agregation.")
        return None
    
    imgout = 'image.png'
    scidxout = 'index.scidx'
    
    if bin_size < 1:
        print("# Bin size must be a positive number. Input was: " + str(bin_size))
        return

    recs_to_process = os.listdir(folder)
    if len(recs_to_process) < 1:
        print("no recordings on folder.")
        return

    peaknumbers = indices.Indices(aggregation_params)

    hIndex = indices.Indices(aggregation_params)

    aciIndex = indices.Indices(aggregation_params)

    start_time = time.time()
    resultsParallel = Parallel(n_jobs=num_cores)(
        delayed(process_rec)(folder + '/' + recordingi, bin_size, frequency, threshold) for recordingi in recs_to_process
    )
    if len(resultsParallel) == 0:
        print('no results')
        return
    print(f'timing: total processing recs: {time.time() - start_time:.2f}s')

    start_time = time.time()
    max_hertz = 22050
    for result in resultsParallel:
        if result is not None:
            if   max_hertz < result['recMaxHertz']:
                max_hertz = result['recMaxHertz']
    max_bins = int(max_hertz / bin_size)
    scp = soundscape.Soundscape(aggregation_params, bin_size, max_bins, amplitude_th=threshold, threshold_type=threshold_type)
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
    print(f'timing: soundscape process: {time.time() - start_time:.2f}s')

    start_time = time.time()
    scp.write_index(working_folder+scidxout)

    peaknFile = working_folder+'peaknumbers'
    peaknumbers.write_index_aggregation_json(peaknFile+'.json')

    hFile = working_folder+'h'
    hIndex.write_index_aggregation_json(hFile+'.json')

    aciFile = working_folder+'aci'
    aciIndex.write_index_aggregation_json(aciFile+'.json')

    if aggregation_params['range'] == 'auto':
        statsMin = scp.stats['min_idx']
        statsMax = scp.stats['max_idx']
    else:
        statsMin = aggregation_params['range'][0]
        statsMax = aggregation_params['range'][1]

    scp.write_image(working_folder + imgout, palette.get_palette())
    print(f'timing: write results: {time.time() - start_time:.2f}s')

        

