import maad
import numpy as np
import soundfile as sf
from scipy.signal import find_peaks
from math import floor

def get(rec_wav, bin_size, frequency, threshold):
    s, fs = sf.read(rec_wav)

    windowsize = next_power_of_2(floor(fs / bin_size))
    spec, tn, fn, _ = maad.sound.spectrogram(s, fs, mode='amplitude') # , nperseg=windowsize
    freqs, amps = fpeaks(spec, fn, min_freq_dist=frequency, min_peak_val=threshold)

    aci_spectrogram, _, _, _ = maad.sound.spectrogram(s, fs, mode='amplitude', nperseg=512, noverlap=0)  
    _, _ , aci  = maad.features.acoustic_complexity_index(aci_spectrogram)

    return freqs, amps, aci


def next_power_of_2(x):  
    return 1 if x == 0 else 2**(x - 1).bit_length()

def fpeaks(X, fn, min_peak_val=None, min_freq_dist=200, prominence=0):
    """
    Find the frequency peaks on a mean spectrum.
    
    Parameters
    ----------
    X : ndarray of floats (1d) or (2d)
        Amplitude spectrum (1d) or spectrogram (2d). If spectrogram, the mean
        spectrum will be computed before finding peaks
    fn : 1d ndarray of floats
        frequency vector
    min_peak_val : scalar, optional, default is None
        amplitude threshold parameter. Only peaks above this threshold will be 
        considered.
    min_freq_dist: scalar, optional, default is 200 
        frequency threshold parameter (in Hz). 
        If the frequency difference of two successive peaks is less than this threshold, 
        then the peak of highest amplitude will be kept only.
    prominence : number, ndarray or sequence, optional, default is None
        Prominence of peaks. The first element is the minimal prominence and the
        second element is the maximal prominence. If a single number is provided
        it is interpreted as the minimal value, and no maximial value will be used.
        
    Returns
    -------
    NBPeaks : integer
        Number of detected peaks on the mean spectrum
    """
    min_pix_distance = min_freq_dist/(fn[1]-fn[0])
    if not min_pix_distance >= 1:
        raise ValueError('`min_freq_dist` must be greater or equal to ???')

    # Force to be an array
    X = np.asarray(X)
    
    # mean spectrum
    if X.ndim == 2:
        S = maad.sound.avg_amplitude_spectro(X)
    else:
        S = X

    # Find peaks
    index, prop = find_peaks(S, height=min_peak_val, 
                             distance=min_pix_distance, 
                             prominence=prominence)

    return fn[index], S[index]

