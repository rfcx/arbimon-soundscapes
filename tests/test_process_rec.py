import pytest
from soundscapes.old.process_rec import process_rec


def test_wav():
    rec = 'tests/data/wav_unknown/2022-11-01_11-25.wav'

    result = process_rec(rec, bin_size=344, threshold=0.005, frequency=100)

    assert len(result['freqs']) == 3
    assert result['freqs'] == pytest.approx([3.78984, 8.61328, 9.30234], 0.0001)
    assert len(result['amps']) == 3
    assert result['amps'] == pytest.approx([0.28270, 0.05240, 0.05435], 0.0001)
    assert result['aci'] == pytest.approx(145.78, 0.01)
    assert result['recMaxHertz'] == 11025

