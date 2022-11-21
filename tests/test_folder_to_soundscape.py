import os
import png
import pytest
import tempfile
from soundscapes.old.folder_to_soundscape import folder_to_soundscape

def read_one_line_float_array_file(path):
    with open(path) as f:
        lines = f.readlines()
    assert len(lines) == 1
    return eval(lines[0])

def read_png(path):
    reader = png.Reader(path)
    w, h, pixels, metadata = reader.read_flat()
    return w, h, pixels


def test_wav():
    # Arrange
    folder = 'tests/data/wav_unknown'
    output_folder = tempfile.TemporaryDirectory()

    # Act
    folder_to_soundscape(folder, output_folder.name, 'time_of_day', 86, 0.005, 'absolute', 100, 0)

    # Assert
    files = os.listdir(output_folder.name + '/results')
    assert len(files) == 5

    fpeaks_expected = eval('[0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 28.833333333333332, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]')
    fpeaks_actual = read_one_line_float_array_file(output_folder.name + '/results/peaknumbers.json')
    assert fpeaks_actual == pytest.approx(fpeaks_expected, 0.01)

    aci_expected = eval('[0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 164.47476666666665, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]')
    aci_actual = read_one_line_float_array_file(output_folder.name + '/results/aci.json')
    assert aci_actual == pytest.approx(aci_expected, 0.01)

    image_w_expected, image_h_expected, image_pixels_expected = read_png('tests/data/wav_unknown/image.png')
    image_w_actual, image_h_actual, image_pixels_actual = read_png(output_folder.name + '/results/image.png')
    assert image_w_actual == image_w_expected
    assert image_h_actual == image_h_expected
    assert image_pixels_actual == image_pixels_expected

    output_folder.cleanup()

def test_wav_normalized():
    # Arrange
    folder = 'tests/data/wav_unknown'
    output_folder = tempfile.TemporaryDirectory()

    # Act
    folder_to_soundscape(folder, output_folder.name, 'time_of_day', 86, 0.005, 'absolute', 100, 1)

    # Assert
    image_w_expected, image_h_expected, image_pixels_expected = read_png('tests/data/wav_unknown/image-normalized.png')
    image_w_actual, image_h_actual, image_pixels_actual = read_png(output_folder.name + '/results/image.png')
    assert image_w_actual == image_w_expected
    assert image_h_actual == image_h_expected
    assert image_pixels_actual == image_pixels_expected

    output_folder.cleanup()