# Copied from https://github.com/rfcx/arbimon-jobs/blob/develop/scripts/Soundscapes/playlist2soundscape.py

import sys
import MySQLdb
import tempfile
import os
import time
import shutil
import math
import multiprocessing
import subprocess
import boto
import json
from joblib import Parallel, delayed
from datetime import datetime
from contextlib import closing
from soundscape import soundscape
from indices import indices
from a2pyutils.config import EnvironmentConfig
from a2pyutils.logger import Logger
from a2audio.rec import Rec
from a2pyutils import palette
from a2pyutils.news import insertNews
from boto.s3.connection import S3Connection
from soundscape.set_visual_scale_lib import get_norm_vector
from soundscape.set_visual_scale_lib import get_sc_data
from soundscape.set_visual_scale_lib import get_db

num_cores = multiprocessing.cpu_count()
configuration = EnvironmentConfig()

currDir = (os.path.dirname(os.path.realpath(__file__)))
USAGE = """
{prog} job_id
    job_id - job id in database
""".format(prog=sys.argv[0])


if len(sys.argv) < 2:
    print USAGE
    sys.exit(-1)

job_id = int(sys.argv[1].strip("'"))

tempFolders = str(configuration.pathsConfig['temp_dir'])
workingFolder = tempFolders+"/soundscape_"+str(job_id)+"/"
if os.path.exists(workingFolder):
    shutil.rmtree(workingFolder)
os.makedirs(workingFolder)

log = Logger(job_id, 'playlist2soundscape.py', 'main')
log.also_print = True
log.write('script started')

config = configuration.data()
log.write('configuration loaded')
log.write('trying database connection')
try:
    db = MySQLdb.connect(
        host=config[0], user=config[1],
        passwd=config[2], db=config[3]
    )
    dbDict = MySQLdb.connect(
        host=config[0], user=config[1],
        passwd=config[2], db=config[3],
        cursorclass=MySQLdb.cursors.DictCursor
    )
except MySQLdb.Error as e:
    print "# Fatal error: cannot connect to database."
    log.write('Fatal error: cannot connect to database.')
    log.close()
    quit()
log.write('database connection succesful')


with closing(db.cursor()) as cursor:
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
    print "Soundscape job #{0} not found".format(job_id)
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
    print "# Wrong agregation."
    print USAGE
    log.write('Wrong agregation')
    log.close()
    sys.exit(-1)

imgout = 'image.png'
scidxout = 'index.scidx'


if bin_size < 0:
    print "# Bin size must be a positive number. Input was: " + str(bin_size)
    print USAGE
    log.write('Bin size must be a positive number. Input was:' + str(bin_size))
    log.close()
    sys.exit(-1)

legacyBucketName = config[4]
sieveAwsKeyId = config[5]
sieveAwsKeySecret = config[6]

bucketName = config[7]
awsAccessKeyId = config[8]
awsSecretKey = config[9]

try:
    #------------------------------- PREPARE --------------------------------------------------------------------------------------------------------------------
    q = ("SELECT r.`recording_id`,`uri`, DATE_FORMAT( `datetime` , \
        '%Y-%m-%d %H:%i:%s') as date, IF(LEFT(r.uri, 8) = 'project_', 1, 0) legacy \
        FROM `playlist_recordings` pr \
        JOIN `recordings` r ON pr.`recording_id` = r.`recording_id` \
        WHERE `playlist_id` = " + str(playlist_id))

    log.write('retrieving playlist recordings list')
    totalRecs = 0
    recsToProcess = []
    with closing(db.cursor()) as cursor:
        cursor.execute(q)
        db.commit()
        numrows = int(cursor.rowcount)
        totalRecs = numrows
        for i in range(0, numrows):
            row = cursor.fetchone()
            recsToProcess.append({
                "uri": row[1],
                "id": row[0],
                "date": row[2],
                "legacy": row[3]
            })
        log.write('playlist recordings list retrieved')
    try:
        with closing(db.cursor()) as cursor:
            cursor.execute('update `jobs` set state="processing", `progress` = 1,\
                `progress_steps` = '+str(int(totalRecs)+5)+' \
                where `job_id` = '+str(job_id))
            db.commit()
    except Exception as e:
        log.write(str(e))
    if len(recsToProcess) < 1:
        print "# Fatal error: invalid playlist or no recordings on playlist."
        log.write('Invalid playlist or no recordings on playlist')

        with closing(db.cursor()) as cursor:
            cursor.execute('update `jobs` set `state`="error", \
                `completed` = -1,`remarks` = \'Error: Invalid playlist \
                (Maybe empty).\' where `job_id` = '+str(job_id))
            db.commit()
        log.close()
        sys.exit(-1)

    log.write(
        'init indices calculation with aggregation: '+str(aggregation)
        )

    if agr_ident=='year':
        agg_range = [int(i['date'].split('-')[0]) for i in recsToProcess]
        aggregation['range'] = [min(agg_range), max(agg_range)]

    peaknumbers  = indices.Indices(aggregation)
    hIndex = indices.Indices(aggregation)
    aciIndex = indices.Indices(aggregation)

    log.write("start parallel... ")

    #------------------------------- FUNCTION THAT PROCESS ONE RECORDING --------------------------------------------------------------------------------------------------------------------

    def processRec(rec, config):
        logofthread = Logger(job_id, 'playlist2soundscape.py', 'thread')
        logofthread.also_print = True

        id = rec['id']
        logofthread.write(
            '------------------START WORKER THREAD LOG (id:'+str(id) +
            ')------------------'
        )
        try:
            db1 = MySQLdb.connect(
                host=config[0], user=config[1], passwd=config[2], db=config[3]
            )
        except MySQLdb.Error as e:
            logofthread.write('worker id'+str(id)+' log: worker cannot \
                connect \to db')
            return None
        logofthread.write('worker id'+str(id)+' log: connected to db')
        try:
            with closing(db1.cursor()) as cursor:
                cursor.execute('update `jobs` set `state`="processing", \
                    `progress` = `progress` + 1 where `job_id` = '+str(job_id))
                db1.commit()
        except Exception as e:
            log.write(str(e))
        results = []
        date = datetime.strptime(rec['date'], '%Y-%m-%d %H:%M:%S')

        uri = rec['uri']
        logofthread.write('worker id'+str(id)+' log: rec uri:'+uri)
        start_time_rec = time.time()
        recobject = Rec(str(uri),
                        str(workingFolder),
                        legacyBucketName if rec['legacy'] else bucketName,
                        logofthread,
                        False,
                        legacy=rec['legacy'])

        logofthread.write(
            'worker id' + str(id) + ' log: rec from uri' +
            str(time.time()-start_time_rec)
        )
        if recobject .status == 'HasAudioData':
            localFile = recobject.getLocalFileLocation()
            logofthread.write('worker id'+str(id)+' log: rec HasAudioData')
            if localFile is None:
                logofthread.write(
                    '------------------END WORKER THREAD LOG (id:' + str(id) +
                    ')------------------'
                )
                db1.close()
                return None
            logofthread.write(
                'worker id' + str(id) + ' log: cmd: /usr/bin/Rscript ' +
                currDir + '/fpeaks.R' + ' ' + localFile + ' ' +
                str(threshold) + ' ' + str(bin_size) + ' ' + str(frequency)
            )
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
                logofthread.write(
                    'worker id' + str(id) + ' log: fpeaks.R err:' +
                    str(time.time()-start_time_rec) + " stdout: " + stdout +
                    " stderr: "+stderr
                )
                os.remove(localFile)
                logofthread.write(
                    'worker id' + str(id) + ' log:Error in recording:' + uri)
                with closing(db1.cursor()) as cursor:
                    cursor.execute(
                        'INSERT INTO `recordings_errors`(`recording_id`,`job_id`) \
                        VALUES ('+str(id)+','+str(job_id)+') ')
                    db1.commit()
                logofthread.write(
                    '------------------END WORKER THREAD LOG (id:' + str(id) +
                    ')------------------')
                db1.close()
                return None
            elif stdout:
                if 'err' in stdout:
                    logofthread.write('err in stdout')
                    logofthread.write(
                        '------------------END WORKER THREAD LOG (id:' +
                        str(id) + ')------------------')
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
                    if stdout and 'err' not in stdout:
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
                    if stdout and 'err' not in stdout:
                        acivalue = float(stdout)
                else:
                    acivalue=-1

                proc = subprocess.Popen([
                   '/usr/bin/soxi', '-r',
                   localFile
                ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                stdout, stderr = proc.communicate()

                recSampleRate = None
                if stdout and 'err' not in stdout:
                    recSampleRate = float(stdout)
                recMaxHertz = float(recSampleRate)/2.0
                os.remove(localFile)
                results = {"date": date, "id": id, "freqs": freqs , "amps":amps , "h":hvalue , "aci" :acivalue,"recMaxHertz":recMaxHertz}
                logofthread.write(
                    '------------------END WORKER THREAD LOG (id:' + str(id) +
                    ')------------------'
                )
                db1.close()
                return results
        else:
            logofthread.write(
                'worker id' + str(id) + ' log: Invalid recording:' + uri)
            with closing(db1.cursor()) as cursor:
                cursor.execute('INSERT INTO `recordings_errors`(`recording_id`, \
                    `job_id`) VALUES ('+str(id)+','+str(job_id)+') ')
                db1.commit()
            logofthread.write(
                '------------------END WORKER THREAD LOG (id:' + str(id) +
                ')------------------'
            )
            db1.close()
            return None
#finish function
#------------------------------- PARALLEL PROCESSING OF RECORDINGS --------------------------------------------------------------------------------------------------------------------
    start_time_all = time.time()
    resultsParallel = Parallel(n_jobs=num_cores)(
        delayed(processRec)(recordingi, config) for recordingi in recsToProcess
    )
    #----------------------------END PARALLEL --------------------------------------------------------------------------------------------------------------------
    # process result
    log.write("all recs parallel ---" + str(time.time() - start_time_all))
    if len(resultsParallel) > 0:
        log.write('processing recordings results: '+str(len(resultsParallel)))
        try:
            with closing(db.cursor()) as cursor:
                cursor.execute('update `jobs` set `state`="processing", \
                    `progress` = `progress` + 1 where `job_id` = '+str(job_id))
                db.commit()
        except Exception as e:
            log.write(str(e))
            try:
                log.write('Attempting to re-establish main MySQL connection')
                db.close()
                db = MySQLdb.connect(
                    host=config[0], user=config[1],
                    passwd=config[2], db=config[3]
                )
                with closing(db.cursor()) as cursor:
                    cursor.execute('update `jobs` set `state`="processing", \
                        `progress` = `progress` + 1 where `job_id` = '+str(job_id))
                    db.commit()
            except Exception as e:
                log.write(str(e))
                log.write('Fatal error: cannot connect to database.')
                log.close()
                db.close()
                quit()

        max_hertz = 22050
        for result in resultsParallel:
            if result is not None:
                if   max_hertz < result['recMaxHertz']:
                    max_hertz = result['recMaxHertz']
        max_bins = int(max_hertz / bin_size)
        log.write('max_bins '+str(max_bins))
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

        log.write("inserting peaks:" + str(time.time() - start_time_all))
        start_time_all = time.time()

        scp.write_index(workingFolder+scidxout)

        log.write("writing indices:" + str(time.time() - start_time_all))

        peaknFile = workingFolder+'peaknumbers'
        peaknumbers.write_index_aggregation_json(peaknFile+'.json')

        hFile = workingFolder+'h'
        hIndex.write_index_aggregation_json(hFile+'.json')

        aciFile = workingFolder+'aci'
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
            with closing(db.cursor()) as cursor:
                cursor.execute('update `jobs` set `state`="processing", \
                    `progress` = `progress` + 1 where `job_id` = '+str(job_id))
                db.commit()
                cursor.execute(query, query_data)
                db.commit()
                scpId = cursor.lastrowid
        except Exception as e:
            log.write(str(e))
        try:
            log.write('inserted soundscape into database')
            soundscapeId = scpId
            start_time_all = time.time()

            db1 = get_db(config)
            scData = get_sc_data(db1, soundscapeId)
            norm_vector = get_norm_vector(db1, scData) if normalized else None
            db1.close()
            if norm_vector is not None:
                scp.norm_vector = norm_vector

            scp.write_image(workingFolder + imgout, palette.get_palette())
            try:
                with closing(db.cursor()) as cursor:
                    cursor.execute('update `jobs` set `state`="processing", \
                        `progress` = `progress` + 1 where `job_id` = '+str(job_id))
                    db.commit()
            except Exception as e:
                log.write(str(e))
            log.write("writing image:" + str(time.time() - start_time_all))
            uriBase = 'project_'+str(pid)+'/soundscapes/'+str(soundscapeId)
            imageUri = uriBase + '/image.png'
            indexUri = uriBase + '/index.scidx'
            peaknumbersUri = uriBase + '/peaknumbers.json'
            hUri = uriBase + '/h.json'
            aciUri = uriBase + '/aci.json'

            log.write('tring connection to bucket')
            start_time = time.time()
            bucket = None
            conn = S3Connection(sieveAwsKeyId, sieveAwsKeySecret)
            try:
                log.write('connecting to ' + legacyBucketName)
                bucket = conn.get_bucket(legacyBucketName)
            except Exception, ex:
                log.write('Fatal error: cannot connect to bucket '+ex.error_message)
                with closing(db.cursor()) as cursor:
                    cursor.execute('UPDATE `jobs` \
                    SET `completed` = -1, `state`="error", \
                    `remarks` = \'Error: connecting to bucket.\' \
                    WHERE `job_id` = '+str(job_id))
                    db.commit()
                db.close()
                quit()
            log.write('connect to bucket  succesful')
            k = bucket.new_key(imageUri)
            k.set_contents_from_filename(workingFolder+imgout)
            k.set_acl('public-read')
            try:
                with closing(db.cursor()) as cursor:
                    cursor.execute('update `jobs` set `state`="processing", \
                        `progress` = `progress` + 1 where `job_id` = '+str(job_id))
                    db.commit()
            except Exception as e:
                log.write(str(e))
            k = bucket.new_key(indexUri)
            k.set_contents_from_filename(workingFolder+scidxout)
            k.set_acl('public-read')
            with closing(db.cursor()) as cursor:
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
            with closing(db.cursor()) as cursor:
                cursor.execute('delete from soundscapes where soundscape_id ='+str(scpId))
                db.commit()
                cursor.execute('update `jobs` set `state`="error", \
                    `completed` = -1,`remarks` = \'Error: No results found.\' \
                    where `job_id` = '+str(job_id))
                db.commit()
    else:
        print 'no results from playlist id:'+playlist_id
        with closing(db.cursor()) as cursor:
            cursor.execute('update `jobs` set `state`="error", \
                `completed` = -1,`remarks` = \'Error: No results found.\' \
                where `job_id` = '+str(job_id))
            db.commit()
        log.write('no results from playlist id:'+playlist_id)
        try:
            with closing(db.cursor()) as cursor:
                cursor.execute('update `jobs` set \
                    `progress` = `progress` + 4 where `job_id` = '+str(job_id))
                db.commit()
        except Exception as e:
            log.write(str(e))

    try:
        with closing(db.cursor()) as cursor:
            cursor.execute('update `jobs` set `state`="completed", `completed`=1, \
                `progress` = `progress` + 1 where `job_id` = '+str(job_id))
            insertNews(cursor, uid, pid, json.dumps({"soundscape": name}), 11)
            db.commit()
    except Exception as e:
        log.write(str(e))
    log.write('closing database')

    db.close()
    log.write('removing temporary folder')

    shutil.rmtree(tempFolders+"/soundscape_"+str(job_id))
except Exception, e:
    import traceback
    errmsg = traceback.format_exc()
    log.write(errmsg)
    with closing(db.cursor()) as cursor:
        cursor.execute('\
            UPDATE `jobs` \
            SET `state`=%s, `completed`=%s, `remarks`=%s \
            WHERE `job_id` = %s', [
            'error', -1, errmsg, job_id
        ])
        db.commit()
    shutil.rmtree(tempFolders+"/soundscape_"+str(job_id))
    db.close()
log.write('ended script')
log.close()
