import boto3
import os

# AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID', "")
# AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY', "")
# print AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY

# if os.getenv('IS_HEROKU') != True:
#     try:
#         import config
#         AWS_ACCESS_KEY_ID = config.AWS_ACCESS_KEY_ID
#         AWS_SECRET_ACCESS_KEY = config.AWS_SECRET_ACCESS_KEY
#     except ImportError:
#       pass

session = boto3.Session(
    aws_access_key_id="AKIAJMA2CQOJ42TJJBFA",
    aws_secret_access_key="WcbdU3Rhuvl02xzR95pETD1+4UaDrzHji8rfGjLFWcbdU3Rhuvl02xzR95pETD1+4UaDrzHji8rfGjLF",
    region_name="us-east-1"
)
print "Hi"
s3_client = boto3.client('s3')
s3_resource = boto3.resource('s3')
