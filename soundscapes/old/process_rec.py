import os
import subprocess
import json
import re
import time
from datetime import datetime

(compute_index_h, compute_index_aci) = (False, True)

currDir = (os.path.dirname(os.path.realpath(__file__)))


def process_rec(rec, bin_size, frequency, threshold):
    print(f'processing {rec}')

    # Parse filename for timestamp
    rec_timestamp_match = re.search(r'(\d{4}-\d{2}-\d{2}_\d{2}-\d{2})\.\w+', rec)
    if not rec_timestamp_match:
        print('Timestamp not found in filename')
        return None
    timestamp = datetime.strptime(rec_timestamp_match.group(1), '%Y-%m-%d_%H-%M')

    # Convert file to wav if needed
    if rec.endswith('.flac'):
        rec_wav = rec.replace('.flac','.wav')
    elif rec.endswith('.opus'):
        rec_wav = rec.replace('.opus','.wav')
    elif rec.endswith('.wav'):
        rec_wav = rec
    else:
        return None
    start_time = time.time()
    if not os.path.isfile(rec_wav):
        command = ['/usr/bin/sox', rec, rec_wav]
        proc = subprocess.run(command, capture_output=True, text=True)
        if not os.path.isfile(rec_wav):
            return None
    print(f'timing: rec wav conversion: {time.time() - start_time:.2f}s')

    # Run fpeaks
    start_time = time.time()
    proc = subprocess.run([
        '/usr/bin/Rscript', currDir+'/fpeaks.R',
        rec_wav,
        '0', # str(threshold),
        str(bin_size),
        str(frequency)
    ], capture_output=True, text=True)
    stdout, stderr = proc.stdout, proc.stderr
    print(f'timing: rec calc fpeaks: {time.time() - start_time:.2f}s')

    # Parse fpeaks output
    if stderr and 'LC_TIME' not in stderr and 'OpenBLAS' not in stderr:
        return None
    ff=json.loads(stdout)
    freqs =[]
    amps =[]
    for i in range(len(ff)):
        freqs.append(ff[i]['f'])
        amps.append(ff[i]['a'])

    # Run h
    if compute_index_h:
        start_time = time.time()
        proc = subprocess.run(['/usr/bin/Rscript', currDir+'/h.R', rec_wav], capture_output=True, text=True)
        stdout, stderr = proc.stdout, proc.stderr
        hvalue = None
        if stdout and 'err' not in stdout:
            hvalue = float(stdout)
        print(f'timing: rec calc h: {time.time() - start_time:.2f}s')
    else:
        hvalue=-1

    # Run aci
    if compute_index_aci:
        start_time = time.time()
        proc = subprocess.run(['/usr/bin/Rscript', currDir+'/aci.R', rec_wav], capture_output=True, text=True)
        stdout, stderr = proc.stdout, proc.stderr
        acivalue = None
        if stdout and 'err' not in stdout:
            acivalue = float(stdout)
        print(f'timing: rec calc aci: {time.time() - start_time:.2f}s')
    else:
        acivalue=-1

    # Get sample rate
    start_time = time.time()
    proc = subprocess.run(['/usr/bin/soxi', '-r', rec_wav], capture_output=True, text=True)
    stdout, stderr = proc.stdout, proc.stderr
    recSampleRate = None
    if stdout and 'err' not in stdout:
        recSampleRate = float(stdout)
    recMaxHertz = float(recSampleRate) / 2.0
    print(f'timing: rec get sr: {time.time() - start_time:.2f}s')

    return { 'date': timestamp, 'freqs': freqs, 'amps': amps, 'h': hvalue, 'aci': acivalue, 'recMaxHertz': recMaxHertz }
