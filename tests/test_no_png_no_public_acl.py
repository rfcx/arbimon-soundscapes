"""Guard (2026-09-25, operator 20:37): the soundscape job must not render or
upload the heat-map PNG, and must not upload anything world-readable.

Every consumer renders the heat-map from `index.scidx` (the arbimon SPA canvas,
and arbimon-legacy's authenticated on-demand render). Objects are served only
through authenticated, project-scoped routes, so none needs a public ACL.

`soundscapes.uri` still stores the `.../image.png` path VALUE on purpose: it is
the row's storage-path handle (index.scidx is derived from it) and
`uri IS NOT NULL` is how arbimon-legacy lists soundscapes.

Source-level test: the job needs a DB + S3 to run end to end.
"""
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, '..', 'soundscapes', 'old', 'playlist_to_soundscape.py')


def _src():
    with open(SRC) as f:
        return f.read()


def test_no_heatmap_png_is_rendered():
    assert 'write_image(' not in _src()


def test_no_heatmap_png_is_uploaded():
    s = _src()
    uploads = re.findall(r'upload_file\(([^)]*)\)', s)
    assert uploads, 'expected the job to still upload its files'
    for args in uploads:
        assert 'imgout' not in args and 'imageUri' not in args, args


def test_the_scidx_and_index_json_are_still_uploaded():
    s = _src()
    for target in ('indexUri', 'peaknumbersUri', 'hUri', 'aciUri'):
        assert re.search(r'upload_file\([^)]*\b' + target + r'\b', s), target


def test_no_upload_is_world_readable():
    s = _src()
    assert 'public-read' not in s
    assert "'ACL'" not in s and '"ACL"' not in s


def test_uri_still_records_the_image_png_path_value():
    # the row keeps its historical value (apps only test it for NOT NULL)
    s = _src()
    assert "imageUri = 'project_'+str(pid)+'/soundscapes/'+str(soundscapeId)+'/image.png'" in s
    assert re.search(r"update soundscapes set uri = '\"\+imageUri\+\"'", s)

def test_objects_go_to_the_soundscape_bucket_with_flat_keys():
    # 2026-09-25: arbimon-soundscapes/<sid>/<file>, NOT arbimon2/project_<pid>/...
    s = _src()
    assert "bucket = s3.Bucket(config['s3_soundscape_bucket_name'])" in s
    assert "'s3_soundscape_bucket_name': os.getenv('S3_SOUNDSCAPE_BUCKET_NAME') or 'arbimon-soundscapes'" in s
    assert "keyBase = str(int(soundscapeId))" in s
    for f in ('index.scidx', 'peaknumbers.json', 'h.json', 'aci.json'):
        assert "keyBase + '/%s'" % f in s, f
    assert 'uriBase' not in s

def test_legacy_recordings_still_read_from_the_legacy_bucket():
    # the SAME env var picks where legacy recordings are downloaded from; it
    # must not be repointed at the soundscape bucket
    s = _src()
    assert "config['s3_legacy_bucket_name'] if rec['legacy'] else config['s3_bucket_name']" in s
