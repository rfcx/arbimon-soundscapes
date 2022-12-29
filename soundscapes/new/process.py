from ..config.logs import get_logger
import datetime
import concurrent.futures
import rfcx
import tempfile
from ..indices import indices

log = get_logger()

# The RFCx client reads the AUTH0_CLIENT_ID & AUTH0_CLIENT_SECRET env vars if they are set, else prompts for cli auth
client = rfcx.Client()
client.authenticate()
if client.credentials is None:
    raise Exception('Authentication failed. Please try again later or contact support.')



def process(project_id, segment_limit):
    log.info(f'Project {project_id}')
    segments = _get_segments(project_id, segment_limit)
    for segment in segments:
        log.info(segment)

    with tempfile.TemporaryDirectory() as temp_dir:
        with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
            futures = []
            for segment in segments:
                futures.append(executor.submit(_process_segment, segment, temp_dir))

            futures, _ = concurrent.futures.wait(futures)

    for future in futures:
        log.info(future.result())
    
    return 2

def _process_segment(segment, temp_dir):
    file_path = client.download_segment(segment['stream_id'], temp_dir, segment['start'], segment['file_extension'])
    log.info(file_path)
    freqs, amps, aci = indices.get(file_path, bin_size = 86, threshold = 0.0, frequency = 200)
    log.info(f'aci={aci}')


def _get_segments(project_id, segment_limit):
    segments = []
    streams = client.streams(projects=[project_id], fields=['id','name','start','end'])
    for stream in streams:
        if stream["start"] is None:
            continue
        log.info(f'Site {stream["id"]} {stream["name"]} {stream["start"]}')
        start, end = [datetime.datetime.strptime(s[0:10], "%Y-%m-%d") for s in [stream["start"], stream["end"]]]
        for date_range in _get_date_chunks(start, end, 365):
            log.info(date_range)
            found_segments = client.stream_segments(stream["id"], start=date_range[0], end=date_range[1], limit=segment_limit)
            for segment in found_segments:
                segment['stream_id'] = stream["id"]
            segments.extend(found_segments)
            if len(segments) >= segment_limit:
                break
        if len(segments) >= segment_limit:
            break
    return segments
            
def _get_date_chunks(d1: datetime, d2: datetime, chunk_duration_days):
    d = d1.replace(hour=0, minute=0, second=0, microsecond=0)
    d2 = d2.replace(hour=23, minute=59, second=59, microsecond=999999)
    step = datetime.timedelta(days=chunk_duration_days)
    date_chunks = []
    while d < d2:
        date_chunks.append([d, d+step])
        d += step
    return date_chunks