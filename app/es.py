import os

from elasticsearch import Elasticsearch

ES_URL = os.getenv('ES_URL', "")
ES_PASSWORD = os.getenv('ES_PASSWORD', "")

if os.getenv('IS_HEROKU') != True:
    try:
        import config
        ES_URL = config.ES_URL
        ES_PASSWORD = config.ES_PASSWORD
    except ImportError:
      pass

es_client = Elasticsearch([ES_URL], http_auth=('elastic', ES_PASSWORD))
