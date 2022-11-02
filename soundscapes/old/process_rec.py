import os
import subprocess
import json
import re
from datetime import datetime

(compute_index_h, compute_index_aci) = (False, True)

currDir = (os.path.dirname(os.path.realpath(__file__)))



def process_rec(rec, bin_size, frequency):
    id = 1

    rec_timestamp_match = re.search(r'(\d{4}-\d{2}-\d{2}_\d{2}-\d{2})\.\w+', rec)
    if not rec_timestamp_match:
        print('Timestamp not found in filename')
        return None
    timestamp = datetime.strptime(rec_timestamp_match.group(1), '%Y-%m-%d_%H-%M')

    if rec.endswith(".flac"):
        rec_wav = rec.replace(".flac",".wav")
        fileType = 'flac'
    elif rec.endswith(".opus"):
        rec_wav = rec.replace(".opus",".wav")
        fileType = 'opus'
    elif rec.endswith(".wav"):
        rec_wav = rec
        fileType = 'wav'
    else:
        return None

    # Convert file to wav if needed
    print(rec, rec_wav)
    if not os.path.isfile(rec_wav):
        command = ['/usr/bin/sox', rec, rec_wav]
        proc = subprocess.run(command, capture_output=True, text=True)
        stdout, stderr = proc.stdout, proc.stderr

    if not os.path.isfile(rec_wav):
        return None

    localFile = rec_wav
    print("processing",rec_wav)
    proc = subprocess.run([
        '/usr/bin/Rscript', currDir+'/fpeaks.R',
        localFile,
        '0', # str(threshold),
        str(bin_size),
        str(frequency)
    ], capture_output=True, text=True)
    stdout, stderr = proc.stdout, proc.stderr
    if stderr and 'LC_TIME' not in stderr and 'OpenBLAS' not in stderr:
        return None
    elif stdout:
        if 'err' in stdout:
            return None
        ff=json.loads(stdout)
        freqs =[]
        amps =[]
        for i in range(len(ff)):
            freqs.append(ff[i]['f'])
            amps.append(ff[i]['a'])

        if compute_index_h:
            proc = subprocess.run([
            '/usr/bin/Rscript', currDir+'/h.R',
            localFile
            ], capture_output=True, text=True)
            stdout, stderr = proc.stdout, proc.stderr

            hvalue = None
            if stdout and 'err' not in stdout:
                hvalue = float(stdout)
        else:
            hvalue=-1

        if compute_index_aci:
            proc = subprocess.run([
            '/usr/bin/Rscript', currDir+'/aci.R',
            localFile
            ], capture_output=True, text=True)
            stdout, stderr = proc.stdout, proc.stderr

            acivalue = None
            if stdout and 'err' not in stdout:
                acivalue = float(stdout)
        else:
            acivalue=-1

        proc = subprocess.run([
            '/usr/bin/soxi', '-r',
            localFile
        ], capture_output=True, text=True)
        stdout, stderr = proc.stdout, proc.stderr

        recSampleRate = None
        if stdout and 'err' not in stdout:
            recSampleRate = float(stdout)
        recMaxHertz = float(recSampleRate)/2.0
        results = {"date": timestamp, "id": id, "freqs": freqs , "amps":amps , "h":hvalue , "aci" :acivalue,"recMaxHertz":recMaxHertz}
        return results
