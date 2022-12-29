import os
import subprocess
import tempfile
import json
import time
from soundscapes.indices import indices


(compute_index_h, compute_index_aci) = (False, True)

currDir = (os.path.dirname(os.path.realpath(__file__)))


def process_rec(rec, bin_size, frequency, threshold):
    print(f'processing {rec}')

    # Convert file to wav if needed
    temp_dir = tempfile.TemporaryDirectory()
    if rec.endswith('.flac'):
        rec_wav = temp_dir.name + os.path.basename(rec).replace('.flac','.wav')
    elif rec.endswith('.opus'):
        rec_wav = temp_dir.name + os.path.basename(rec).replace('.opus','.wav')
    elif rec.endswith('.wav'):
        rec_wav = rec
    else:
        return None
    if not os.path.isfile(rec_wav):
        start_time = time.time()
        command = ['/usr/bin/sox', rec, rec_wav]
        proc = subprocess.run(command, capture_output=True, text=True)
        print(f'timing: rec wav conversion: {time.time() - start_time:.2f}s')
        if not os.path.isfile(rec_wav):
            return None

    # Run fpeaks in R
    proc = subprocess.run([
        '/usr/bin/Rscript', currDir+'/fpeaks.R',
        rec_wav,
        '0', # str(threshold),
        str(bin_size),
        str(frequency)
    ], capture_output=True, text=True)
    stdout, stderr = proc.stdout, proc.stderr
    ff=json.loads(stdout)
    freqs_expected = []
    amps_expected = []
    for i in range(len(ff)):
        freqs_expected.append(ff[i]['f'])
        amps_expected.append(ff[i]['a'])
    
    # Calc fpeaks and aci in python
    freqs, amps, aci = indices.get(rec_wav, bin_size, frequency, threshold)
    print(freqs_expected)
    print(freqs)
    print(amps_expected)
    print(amps)

    # Get sample rate
    start_time = time.time()
    proc = subprocess.run(['/usr/bin/soxi', '-r', rec_wav], capture_output=True, text=True)
    stdout, stderr = proc.stdout, proc.stderr
    recSampleRate = None
    if stdout and 'err' not in stdout:
        recSampleRate = float(stdout)
    recMaxHertz = float(recSampleRate) / 2.0
    print(f'timing: rec get sr: {time.time() - start_time:.2f}s')

    temp_dir.cleanup()

    return { 'freqs': freqs, 'amps': amps, 'h': -1, 'aci': aci, 'recMaxHertz': recMaxHertz }
