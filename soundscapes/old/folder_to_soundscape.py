import os
import time
import shutil
import multiprocessing
import re
from datetime import datetime
from joblib import Parallel, delayed
from .soundscape import soundscape
from .indices import indices
from .a2pyutils import palette
from .process_rec import process_rec
from .soundscape.set_visual_scale_lib import get_norm_vector

#
# threshold_type = 'absolute' (default) or 'relative-to-peak-maximum'

def folder_to_soundscape(folder, output_folder, aggregation = 'time_of_day', bin_size = 86, threshold = 0.0, threshold_type = 'absolute', frequency = 0, normalize = 1):
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

    files = os.listdir(folder)
    recs_to_process = []
    timestamps = []
    for f in files:
        timestamp = parse_timestamp(f)
        if timestamp is None:
            continue
        recs_to_process.append(f)
        timestamps.append(timestamp)

    if len(recs_to_process) < 1:
        print("no recordings in folder")
        return

    start_time = time.time()
    resultsParallel = Parallel(n_jobs=num_cores)(
        delayed(process_rec)(folder + '/' + recordingi, bin_size, frequency, threshold) for recordingi in recs_to_process
    )
    print(f'timing: total processing recs: {time.time() - start_time:.2f}s')

    start_time = time.time()
    max_hertz = 22050
    for result in resultsParallel:
        if result is not None and max_hertz < result['recMaxHertz']:
            max_hertz = result['recMaxHertz']
    max_bins = int(max_hertz / bin_size)
    scp = soundscape.Soundscape(aggregation_params, bin_size, max_bins, amplitude_th=threshold, threshold_type=threshold_type)
    peaknumbers = indices.Indices(aggregation_params)
    hIndex = indices.Indices(aggregation_params)
    aciIndex = indices.Indices(aggregation_params)

    for idx, result in enumerate(resultsParallel):
        if result is None:
            continue
        timestamp = timestamps[idx]
        if result['freqs'] is not None:
            if len(result['freqs']) > 0:
                scp.insert_peaks(timestamp, result['freqs'], result['amps'], idx)
            peaknumbers.insert_value(timestamp ,len(result['freqs']), idx)
        if result['h'] is not None:
            hIndex.insert_value(timestamp, result['h'], idx)
        if result['aci'] is not None:
            aciIndex.insert_value(timestamp, result['aci'], idx)
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

    if normalize:
        scp.norm_vector = get_norm_vector(timestamps, aggregation_params)

    scp.write_image(working_folder + imgout, palette.get_palette())
    print(f'timing: write results: {time.time() - start_time:.2f}s')

        
def parse_timestamp(file_path):
    # Parse filename for timestamp
    timestamp_match = re.search(r'(\d{4}-\d{2}-\d{2}_\d{2}-\d{2})\.\w+', file_path)
    if not timestamp_match:
        print('Timestamp not found in filename')
        return None
    return datetime.strptime(timestamp_match.group(1), '%Y-%m-%d_%H-%M')
