import boto3
import os
from botocore.client import Config

AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID', "")
AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY', "")

if os.getenv('IS_HEROKU') != True:
    try:
        import config
        AWS_ACCESS_KEY_ID = config.AWS_ACCESS_KEY_ID
        AWS_SECRET_ACCESS_KEY = config.AWS_SECRET_ACCESS_KEY
    except ImportError:
      pass

session = boto3.Session(
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY
)

s3_client = boto3.client('s3', "us-east-1",  config=Config(signature_version="s3v4"))
s3_resource = boto3.resource('s3')
