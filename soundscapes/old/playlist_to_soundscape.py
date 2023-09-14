# Copied from https://github.com/rfcx/arbimon-jobs/blob/develop/scripts/Soundscapes/playlist2soundscape.py

import sys
import os
import time
import contextlib
import shutil
import multiprocessing
import subprocess
import json
import tempfile
from joblib import Parallel, delayed
from datetime import datetime
from boto.s3.connection import S3Connection
from .a2audio.rec import Rec
from .a2pyutils import palette
from .indices import indices
from .soundscape import soundscape
from .db import connect

config = {
    's3_access_key_id': os.getenv('AWS_ACCESS_KEY_ID'),
    's3_secret_access_key': os.getenv('AWS_SECRET_ACCESS_KEY'),
    's3_bucket_name': os.getenv('S3_BUCKET_NAME'),
    's3_legacy_bucket_name': os.getenv('S3_LEGACY_BUCKET_NAME')
}

currDir = os.path.dirname(os.path.abspath(__file__))

# aggregation is 'time_of_day' (see soundscape.py for options)
def get_norm_vector(db, aggregation):
    aggregation = soundscape.aggregations[aggregation]
    norm_vector = {}
    date_parts = [
        'DATE_FORMAT(R.datetime, "{}")'.format(dp)
        for dp in aggregation['date']
    ]
    with contextlib.closing(db.cursor()) as cursor:
            cursor.execute('''
                SELECT {} , COUNT(*) as count
                FROM `playlist_recordings` PR
                JOIN `recordings` R ON R.recording_id = PR.recording_id
                WHERE PR.playlist_id = {}
                GROUP BY {}
            '''.format(
                ', '.join([
                    "{} as dp_{}".format(d, i)
                    for i, d in enumerate(date_parts)
                ]),
                int(sc_data['playlist_id']),
                ', '.join(date_parts)
            ))
            for row in cursor:
                idx = sum([
                    int(row['dp_{}'.format(i)]) * p
                    for i, p in enumerate(aggregation['projection'])
                ])
                norm_vector[idx] = row['count']
    return norm_vector

def playlist_to_soundscape(job_id, output_folder = tempfile.gettempdir()):
    num_cores = multiprocessing.cpu_count()

    working_folder = output_folder+"/working/"
    if os.path.exists(working_folder):
        shutil.rmtree(working_folder)
    os.makedirs(working_folder)

    print('trying database connection')
    try:
        db = connect()
    except:
        print('Fatal error: cannot connect to database.')
        quit()
    print('database connection successful')


    with contextlib.closing(db.cursor()) as cursor:
        cursor.execute("""
        SELECT JP.playlist_id, JP.max_hertz, JP.bin_size,
            JP.soundscape_aggregation_type_id,
            SAT.identifier as aggregation, JP.threshold, JP.threshold_type,
            J.project_id, J.user_id, JP.name, JP.frequency , JP.normalize ,J.ncpu
        FROM jobs J
        JOIN job_params_soundscape JP ON J.job_id = JP.job_id
        JOIN soundscape_aggregation_types SAT ON
            SAT.soundscape_aggregation_type_id = JP.soundscape_aggregation_type_id
        WHERE J.job_id = {0}
        LIMIT 1
        """.format(job_id))

        job = cursor.fetchone()

    if not job:
        print("Soundscape job #{0} not found".format(job_id))
        sys.exit(-1)

    (
        playlist_id, max_hertz, bin_size, agrrid, agr_ident,
        threshold, threshold_type, pid, uid, name, frequency , normalized ,ncpu
    ) = job
    (
        compute_index_h,
        compute_index_aci
    ) = (False, True)
    num_cores = multiprocessing.cpu_count()
    if int(ncpu) > 0:
        num_cores = int(ncpu)
    aggregation = soundscape.aggregations.get(agr_ident)

    if not aggregation:
        print('Wrong agregation')
        sys.exit(-1)

    imgout = 'image.png'
    scidxout = 'index.scidx'

    if bin_size < 0:
        print('Bin size must be a positive number. Input was:' + str(bin_size))
        sys.exit(-1)

    try:
        #------------------------------- PREPARE --------------------------------------------------------------------------------------------------------------------
        q = ("SELECT r.`recording_id`,`uri`, DATE_FORMAT( `datetime` , \
            '%Y-%m-%d %H:%i:%s') as date, IF(LEFT(r.uri, 8) = 'project_', 1, 0) legacy \
            FROM `playlist_recordings` pr \
            JOIN `recordings` r ON pr.`recording_id` = r.`recording_id` \
            WHERE `playlist_id` = " + str(playlist_id))

        print('retrieving playlist recordings list')
        totalRecs = 0
        recsToProcess = []
        with contextlib.closing(db.cursor()) as cursor:
            cursor.execute(q)
            recsToProcess = []
            recs = cursor.fetchall()
            totalRecs = len(recs)
            for row in recs:
                recsToProcess.append({
                    "uri": row[1],
                    "id": row[0],
                    "date": row[2],
                    "legacy": row[3]
                })
            print('playlist recordings list retrieved')
        try:
            with contextlib.closing(db.cursor()) as cursor:
                cursor.execute('update `jobs` set state="processing", `progress` = 1,\
                    `progress_steps` = '+str(int(totalRecs)+5)+' \
                    where `job_id` = '+str(job_id))
                db.commit()
        except Exception as e:
            print(str(e))
        if len(recsToProcess) < 1:
            print('Fatal error: Invalid playlist or no recordings on playlist')
            with contextlib.closing(db.cursor()) as cursor:
                cursor.execute('update `jobs` set `state`="error", \
                    `completed` = -1,`remarks` = \'Error: Invalid playlist \
                    (Maybe empty).\' where `job_id` = '+str(job_id))
                db.commit()
            sys.exit(-1)

        print('init indices calculation with aggregation: '+str(aggregation))

        if agr_ident=='year':
            agg_range = [int(i['date'].split('-')[0]) for i in recsToProcess]
            aggregation['range'] = [min(agg_range), max(agg_range)]

        peaknumbers  = indices.Indices(aggregation)
        hIndex = indices.Indices(aggregation)
        aciIndex = indices.Indices(aggregation)

        print("start parallel... ")

        #------------------------------- FUNCTION THAT PROCESS ONE RECORDING --------------------------------------------------------------------------------------------------------------------

        def processRec(rec, config):
            id = rec['id']
            print((
                '------------------START WORKER THREAD LOG (id:'+str(id) +
                ')------------------'
            ))
            try:
                db1 = connect()
            except:
                print('worker id'+str(id)+' log: worker cannot connect \to db')
                return None
            print('worker id'+str(id)+' log: connected to db')
            try:
                with contextlib.closing(db1.cursor()) as cursor:
                    cursor.execute('update `jobs` set `state`="processing", \
                        `progress` = `progress` + 1 where `job_id` = '+str(job_id))
                    db1.commit()
            except Exception as e:
                print(str(e))
            results = []
            date = datetime.strptime(rec['date'], '%Y-%m-%d %H:%M:%S')

            uri = rec['uri']
            print('worker id'+str(id)+' log: rec uri:'+uri)
            start_time_rec = time.time()
            recobject = Rec(str(uri),
                            str(working_folder),
                            config['s3_legacy_bucket_name'] if rec['legacy'] else config['s3_bucket_name'],
                            True,
                            False,
                            legacy=rec['legacy'])

            print((
                'worker id' + str(id) + ' log: rec from uri' +
                str(time.time()-start_time_rec)
            ))
            if recobject .status == 'HasAudioData':
                localFile = recobject.getLocalFileLocation()
                print('worker id'+str(id)+' log: rec HasAudioData')
                if localFile is None:
                    print((
                        '------------------END WORKER THREAD LOG (id:' + str(id) +
                        ')------------------'
                    ))
                    db1.close()
                    return None
                print((
                    'worker id' + str(id) + ' log: cmd: /usr/bin/Rscript ' +
                    currDir + '/fpeaks.R' + ' ' + localFile + ' ' +
                    str(threshold) + ' ' + str(bin_size) + ' ' + str(frequency)
                ))
                start_time_rec = time.time()
                proc = subprocess.Popen([
                    '/usr/bin/Rscript', currDir+'/fpeaks.R',
                    localFile,
                    '0', # str(threshold),
                    str(bin_size),
                    str(frequency)
                ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                stdout, stderr = proc.communicate()
                if stderr and 'LC_TIME' not in stderr and 'OpenBLAS' not in stderr:
                    print((
                        'worker id' + str(id) + ' log: fpeaks.R err:' +
                        str(time.time()-start_time_rec) + " stdout: " + stdout +
                        " stderr: "+stderr
                    ))
                    os.remove(localFile)
                    print((
                        'worker id' + str(id) + ' log:Error in recording:' + uri))
                    with contextlib.closing(db1.cursor()) as cursor:
                        cursor.execute(
                            'INSERT INTO `recordings_errors`(`recording_id`,`job_id`) \
                            VALUES ('+str(id)+','+str(job_id)+') ')
                        db1.commit()
                    print((
                        '------------------END WORKER THREAD LOG (id:' + str(id) +
                        ')------------------'))
                    db1.close()
                    return None
                elif stdout:
                    if 'err' in str(stdout):
                        print('err in stdout')
                        print((
                            '------------------END WORKER THREAD LOG (id:' +
                            str(id) + ')------------------'))
                        db1.close()
                        return None
                    ff=json.loads(stdout)
                    freqs =[]
                    amps =[]
                    for i in range(len(ff)):
                        freqs.append(ff[i]['f'])
                        amps.append(ff[i]['a'])
                    if compute_index_h:
                        proc = subprocess.Popen([
                        '/usr/bin/Rscript', currDir+'/h.R',
                        localFile
                        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                        stdout, stderr = proc.communicate()

                        hvalue = None
                        if stdout and 'err' not in str(stdout):
                            hvalue = float(stdout)
                    else:
                        hvalue=-1

                    if compute_index_aci:
                        proc = subprocess.Popen([
                        '/usr/bin/Rscript', currDir+'/aci.R',
                        localFile
                        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                        stdout, stderr = proc.communicate()

                        acivalue = None
                        if stdout and 'err' not in str(stdout):
                            acivalue = float(stdout)
                    else:
                        acivalue=-1

                    proc = subprocess.Popen([
                    '/usr/bin/soxi', '-r',
                    localFile
                    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    stdout, stderr = proc.communicate()

                    recSampleRate = None
                    if stdout and 'err' not in str(stdout):
                        recSampleRate = float(stdout)
                    recMaxHertz = float(recSampleRate)/2.0
                    os.remove(localFile)
                    results = {"date": date, "id": id, "freqs": freqs , "amps":amps , "h":hvalue , "aci" :acivalue,"recMaxHertz":recMaxHertz}
                    print((
                        '------------------END WORKER THREAD LOG (id:' + str(id) +
                        ')------------------'
                    ))
                    db1.close()
                    return results
            else:
                print((
                    'worker id' + str(id) + ' log: Invalid recording:' + uri))
                with contextlib.closing(db1.cursor()) as cursor:
                    cursor.execute('INSERT INTO `recordings_errors`(`recording_id`, \
                        `job_id`) VALUES ('+str(id)+','+str(job_id)+') ')
                    db1.commit()
                print((
                    '------------------END WORKER THREAD LOG (id:' + str(id) +
                    ')------------------'
                ))
                db1.close()
                return None
    #finish function
    #------------------------------- PARALLEL PROCESSING OF RECORDINGS --------------------------------------------------------------------------------------------------------------------
        start_time_all = time.time()
        # resultsParallel = Parallel(n_jobs=num_cores)(
        #     delayed(processRec)(recordingi, config) for recordingi in recsToProcess
        # )
        resultsParallel = [processRec(recordingi, config) for recordingi in recsToProcess]

        #----------------------------END PARALLEL --------------------------------------------------------------------------------------------------------------------
        # process result
        print("all recs parallel ---" + str(time.time() - start_time_all))
        if len(resultsParallel) > 0:
            print('processing recordings results: '+str(len(resultsParallel)))
            try:
                with contextlib.closing(db.cursor()) as cursor:
                    cursor.execute('update `jobs` set `state`="processing", \
                        `progress` = `progress` + 1 where `job_id` = '+str(job_id))
                    db.commit()
            except Exception as e:
                print(str(e))
                try:
                    print('Attempting to re-establish main MySQL connection')
                    db.close()
                    db = mysql.connector.connect(
                        host=config['db_host'], user=config['db_user'],
                        password=config['db_password'], database=config['db_name']
                    )
                    with contextlib.closing(db.cursor()) as cursor:
                        cursor.execute('update `jobs` set `state`="processing", \
                            `progress` = `progress` + 1 where `job_id` = '+str(job_id))
                        db.commit()
                except Exception as e:
                    print(str(e))
                    print('Fatal error: cannot connect to database.')
                    db.close()
                    quit()

            max_hertz = 22050
            for result in resultsParallel:
                if result is not None:
                    if   max_hertz < result['recMaxHertz']:
                        max_hertz = result['recMaxHertz']
            max_bins = int(max_hertz / bin_size)
            print('max_bins '+str(max_bins))
            scp = soundscape.Soundscape(aggregation, bin_size, max_bins, amplitude_th=threshold, threshold_type=threshold_type)
            start_time_all = time.time()
            for result in resultsParallel:
                if result is not None:
                    if result['freqs'] is not None:
                        if len(result['freqs']) > 0:
                            scp.insert_peaks(result['date'], result['freqs'], result['amps'], result['id'])
                        peaknumbers.insert_value(result['date'] ,len(result['freqs']),result['id'])
                    if result['h'] is not None:
                        hIndex.insert_value(result['date'] ,result['h'],result['id'])
                    if result['aci'] is not None:
                        aciIndex.insert_value(result['date'] ,result['aci'],result['id'])

            print("inserting peaks:" + str(time.time() - start_time_all))
            start_time_all = time.time()

            scp.write_index(working_folder+scidxout)

            print("writing indices:" + str(time.time() - start_time_all))

            peaknFile = working_folder+'peaknumbers'
            peaknumbers.write_index_aggregation_json(peaknFile+'.json')

            hFile = working_folder+'h'
            hIndex.write_index_aggregation_json(hFile+'.json')

            aciFile = working_folder+'aci'
            aciIndex.write_index_aggregation_json(aciFile+'.json')

            if aggregation['range'] == 'auto':
                statsMin = scp.stats['min_idx']
                statsMax = scp.stats['max_idx']
            else:
                statsMin = aggregation['range'][0]
                statsMax = aggregation['range'][1]

            query, query_data = ("""
                INSERT INTO `soundscapes`( `name`, `project_id`, `user_id`,
                `soundscape_aggregation_type_id`, `bin_size`, `uri`, `min_t`,
                `max_t`, `min_f`, `max_f`, `min_value`, `max_value`,
                `date_created`, `playlist_id`, `threshold` , `threshold_type` ,`frequency` ,`normalized`)
                VALUES (
                    %s, %s, %s, %s, %s, NULL, %s, %s, 0, %s, 0, %s, NOW(), %s,
                    %s, %s, %s, %s
                )
            """, [
                name, pid, uid, agrrid,
                bin_size, statsMin, statsMax,
                max_hertz, scp.stats['max_count'],
                playlist_id, threshold, threshold_type, frequency , normalized
            ])

            scpId = -1
            try:
                with contextlib.closing(db.cursor()) as cursor:
                    cursor.execute('update `jobs` set `state`="processing", \
                        `progress` = `progress` + 1 where `job_id` = '+str(job_id))
                    db.commit()
                    cursor.execute(query, query_data)
                    db.commit()
                    scpId = cursor.lastrowid
            except Exception as e:
                print(str(e))
            try:
                print('inserted soundscape into database')
                soundscapeId = scpId
                start_time_all = time.time()

                scData = {'time_of_day'}
                norm_vector = get_norm_vector(db1, scData) if normalized else None

                if norm_vector is not None:
                    scp.norm_vector = norm_vector

                scp.write_image(working_folder + imgout, palette.get_palette())
                try:
                    with contextlib.closing(db.cursor()) as cursor:
                        cursor.execute('update `jobs` set `state`="processing", \
                            `progress` = `progress` + 1 where `job_id` = '+str(job_id))
                        db.commit()
                except Exception as e:
                    print(str(e))
                print("writing image:" + str(time.time() - start_time_all))
                uriBase = 'project_'+str(pid)+'/soundscapes/'+str(soundscapeId)
                imageUri = uriBase + '/image.png'
                indexUri = uriBase + '/index.scidx'
                peaknumbersUri = uriBase + '/peaknumbers.json'
                hUri = uriBase + '/h.json'
                aciUri = uriBase + '/aci.json'

                print('trying connection to bucket')
                bucket = None
                conn = S3Connection(config['s3_access_key_id'], config['s3_secret_access_key'])
                try:
                    print('connecting to ' + config['s3_legacy_bucket_name'])
                    bucket = conn.get_bucket(config['s3_legacy_bucket_name'])
                except Exception as ex:
                    print('Fatal error: cannot connect to bucket '+ex.error_message)
                    with contextlib.closing(db.cursor()) as cursor:
                        cursor.execute('UPDATE `jobs` \
                        SET `completed` = -1, `state`="error", \
                        `remarks` = \'Error: connecting to bucket.\' \
                        WHERE `job_id` = '+str(job_id))
                        db.commit()
                    db.close()
                    quit()
                print('connect to bucket successful')
                k = bucket.new_key(imageUri)
                k.set_contents_from_filename(working_folder+imgout)
                k.set_acl('public-read')
                try:
                    with contextlib.closing(db.cursor()) as cursor:
                        cursor.execute('update `jobs` set `state`="processing", \
                            `progress` = `progress` + 1 where `job_id` = '+str(job_id))
                        db.commit()
                except Exception as e:
                    print(str(e))
                k = bucket.new_key(indexUri)
                k.set_contents_from_filename(working_folder+scidxout)
                k.set_acl('public-read')
                with contextlib.closing(db.cursor()) as cursor:
                    cursor.execute("update `soundscapes` set `uri` = '"+imageUri+"' \
                        where  `soundscape_id` = "+str(soundscapeId))
                    db.commit()

                k = bucket.new_key(peaknumbersUri)
                k.set_contents_from_filename(peaknFile+'.json')
                k.set_acl('public-read')

                k = bucket.new_key(hUri)
                k.set_contents_from_filename(hFile+'.json')
                k.set_acl('public-read')

                k = bucket.new_key(aciUri)
                k.set_contents_from_filename(aciFile+'.json')
                k.set_acl('public-read')
            except:
                with contextlib.closing(db.cursor()) as cursor:
                    cursor.execute('delete from soundscapes where soundscape_id ='+str(scpId))
                    db.commit()
                    cursor.execute('update `jobs` set `state`="error", \
                        `completed` = -1,`remarks` = \'Error: No results found.\' \
                        where `job_id` = '+str(job_id))
                    db.commit()
        else:
            print('no results from playlist id:'+playlist_id)
            with contextlib.closing(db.cursor()) as cursor:
                cursor.execute('update `jobs` set `state`="error", \
                    `completed` = -1,`remarks` = \'Error: No results found.\' \
                    where `job_id` = '+str(job_id))
                db.commit()
            print('no results from playlist id:'+playlist_id)
            try:
                with contextlib.closing(db.cursor()) as cursor:
                    cursor.execute('update `jobs` set \
                        `progress` = `progress` + 4 where `job_id` = '+str(job_id))
                    db.commit()
            except Exception as e:
                print(str(e))

        try:
            with contextlib.closing(db.cursor()) as cursor:
                cursor.execute('update `jobs` set `state`="completed", `completed`=1, \
                    `progress` = `progress` + 1 where `job_id` = '+str(job_id))
                db.commit()
        except Exception as e:
            print(str(e))
        print('closing database')

        db.close()
        print('removing temporary folder')

        shutil.rmtree(working_folder)
    except Exception as e:
        import traceback
        errmsg = traceback.format_exc()
        print(errmsg)
        with contextlib.closing(db.cursor()) as cursor:
            cursor.execute('\
                UPDATE `jobs` \
                SET `state`=%s, `completed`=%s, `remarks`=%s \
                WHERE `job_id` = %s', [
                'error', -1, errmsg, job_id
            ])
            db.commit()
        shutil.rmtree(working_folder)
        db.close()
    print('ended script')


if __name__ == 'main':
    currDir = (os.path.dirname(os.path.realpath(__file__)))
    USAGE = """
    {prog} job_id
        job_id - job id in database
    """.format(prog=sys.argv[0])
    if len(sys.argv) < 2:
        print(USAGE)
        sys.exit(-1)

    job_id = int(sys.argv[1].strip("'"))
    playlist_to_soundscape(job_id)