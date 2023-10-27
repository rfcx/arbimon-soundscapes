# How to use?
#
# `make serve-run SCRIPT=s3_get`
# to list entire bucket
#
# `make serve-run SCRIPT="s3_get project_1907"`
# to list objects with prefix `project_1907`
#
# `make serve-run SCRIPT="s3_get project_1907/soundscapes/5850/peaknumbers.json"`
# to print out content of 1 object


import boto3
import os
import sys

config = {
    's3_access_key_id': os.getenv('AWS_ACCESS_KEY_ID'),
    's3_secret_access_key': os.getenv('AWS_SECRET_ACCESS_KEY'),
    's3_bucket_name': os.getenv('S3_BUCKET_NAME'),
    's3_endpoint': os.getenv('S3_ENDPOINT')
}

s3 = boto3.resource('s3', 
                    aws_access_key_id=config['s3_access_key_id'], 
                    aws_secret_access_key=config['s3_secret_access_key'],
                    endpoint_url=config['s3_endpoint'])

bucket = s3.Bucket(config['s3_bucket_name'])

prefix = sys.argv[1] if len(sys.argv) > 1 else None

# List objects
if not prefix:
    objects = list(bucket.objects.all())
else:
    objects = list(bucket.objects.filter(Prefix=prefix))
for obj in objects:
    print(obj.key)

# Only 1 object then print it
if len(objects) == 1:
    body = objects[0].get()["Body"].read()
    print(body)
