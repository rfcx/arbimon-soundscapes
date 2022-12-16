from ..config.logs import get_logger
import datetime
import rfcx
rfcx._api_rfcx.host = 'https://staging-api.rfcx.org'

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
    return 2

def _get_segments(project_id, segment_limit):
    segments = []
    streams = client.streams(projects=[project_id], fields=['id','name','start','end'])
    for stream in streams:
        log.info(f'Site {stream["id"]} {stream["name"]} {stream["start"]}')
        start, end = [datetime.datetime.strptime(s[0:10], "%Y-%m-%d") for s in [stream["start"], stream["end"]]]
        for date_range in _get_date_chunks(start, end, 7):
            log.info(date_range)
            found_segments = client.stream_segments(stream["id"], start=date_range[0], end=date_range[1], limit=segment_limit)
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