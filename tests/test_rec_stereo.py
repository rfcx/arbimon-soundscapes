"""Soundscape Rec downmixes multi-channel audio for the R index scripts (2026-09-29).

Production path: playlist_to_soundscape -> Rec(...).process() -> readAudioFromFile()
-> the R scripts (fpeaks.R / h.R / aci.R) read Rec's LOCAL FILE with tuneR,
whose readWave() keeps only the LEFT channel of a stereo WAV. So a stereo
recording's soundscape ignored its right channel entirely (measured in the live
image: a 2 kHz-left / 5 kHz-right file scored identically to a left-only file).

Asserts (real soundfile I/O): after readAudioFromFile() on a stereo WAV the
local file is MONO and equals the channel mean; the in-memory signal is 1-D;
4/7-channel files too; a mono file is untouched (byte-identical, not rewritten).
When Rscript + tuneR exist (the production image), also asserts fpeaks.R now
sees the RIGHT channel's 5 kHz tone. RED control: pre-fix rec.py fails the
mono-file checks.
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

import numpy as np
import soundfile as sf

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from soundscapes.old.a2audio.rec import Rec  # noqa: E402

SR = 24000
T = np.arange(2 * SR) / SR
L = 0.3 * np.sin(2 * np.pi * 2000 * T)
R = 0.3 * np.sin(2 * np.pi * 5000 * T)
R_SCRIPTS = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'soundscapes', 'old'))

def _rec(path):
    r = Rec.__new__(Rec)
    r.filename = os.path.basename(path)
    r.localfilename = path
    r.logs = False
    return r

def _sha(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()

class SoundscapeRecStereo(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()

    def _write(self, data, name, subtype='PCM_16'):
        p = os.path.join(self.d, name)
        sf.write(p, data.astype(np.float32), SR, subtype=subtype)
        return p

    def test_stereo_local_file_becomes_mono_mean(self):
        p = self._write(np.stack([L, R], axis=1), 'st.wav')
        r = _rec(p)
        self.assertTrue(r.readAudioFromFile())
        self.assertEqual(np.asarray(r.original).ndim, 1)
        info = sf.info(r.localfilename)
        self.assertEqual(info.channels, 1, 'the file R reads must be mono')
        self.assertEqual(info.subtype, 'PCM_16', 'sample format preserved')
        y, _ = sf.read(r.localfilename)
        np.testing.assert_allclose(y, (L + R) / 2, atol=2e-4)

    def test_many_channels(self):
        for n in (4, 7):
            p = self._write(np.stack([L] * n, axis=1), f'c{n}.wav')
            r = _rec(p)
            self.assertTrue(r.readAudioFromFile())
            self.assertEqual(sf.info(r.localfilename).channels, 1)

    def test_mono_file_untouched(self):
        p = self._write(L, 'mono.wav')
        before = _sha(p)
        r = _rec(p)
        self.assertTrue(r.readAudioFromFile())
        self.assertEqual(_sha(r.localfilename), before, 'a mono file must not be rewritten')

    @unittest.skipUnless(shutil.which('Rscript') and os.path.isfile(os.path.join(R_SCRIPTS, 'fpeaks.R')),
                         'Rscript/tuneR not present (runs in the production image)')
    def test_fpeaks_now_sees_the_right_channel(self):
        p = self._write(np.stack([L, R], axis=1), 'st.wav')
        r = _rec(p)
        self.assertTrue(r.readAudioFromFile())
        out = subprocess.run(['Rscript', os.path.join(R_SCRIPTS, 'fpeaks.R'), r.localfilename, '0', '86', '200'],
                             capture_output=True, text=True, cwd=R_SCRIPTS).stdout
        peaks = json.loads(out)
        top = sorted(peaks, key=lambda q: -q['a'])[:2]
        khz = sorted(round(q['f']) for q in top)
        self.assertEqual(khz, [2, 5], f'top peaks {top}')

if __name__ == '__main__':
    unittest.main()