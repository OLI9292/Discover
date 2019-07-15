import os
import itertools
import json
from multiprocessing import Pool
from itertools import repeat
import sys
import time
sys.dont_write_bytecode = True

from flask import Flask, Response, jsonify, render_template, request
from flask_cors import CORS, cross_origin

from address import find_addresses_in_text
from index_text import index_text, convert_epub_to_text

from wikipedia import wikipedia_image_search, upload_images_to_s3

from rq import Queue
from rq.registry import StartedJobRegistry
from redis import Redis

from s3 import s3_resource

from nltk import pos_tag, word_tokenize

app = Flask(__name__)
CORS(app)

REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379')
redis_conn = Redis.from_url(REDIS_URL)

q = Queue(connection=redis_conn)
registry = StartedJobRegistry('default', connection=redis_conn)

@app.route("/index-texts", methods=['GET', 'POST'])
def index_texts():
    text = request.files["text"]
    filename = text.filename
    index = request.args.get('index')
    is_rob = request.args.get('is_rob')
    # Check if job already running
    # redis_conn.flushall()
    old_job_ids = registry.get_job_ids()
    if len(old_job_ids) > 0:
        message = "Already processing file. Please wait a minute and try again."
        return jsonify(error=message)        
    # Convert epubs to text
    if filename.endswith("epub"):
        print("Converting epub to txt.")
        if os.path.exists("tmp") == False:
            os.makedirs("tmp")
        text.save("tmp/" + filename)
        text = convert_epub_to_text("tmp/" + filename)
        print("Conversion done.")
        filename = filename.replace("epub", "txt")
    # Store file on S3
    print("Storing", filename, "on s3.")
    s3_resource.Bucket('invisible-college-texts').put_object(Key=filename, Body=text)
    # Send to Background queue
    job = q.enqueue_call(func=index_text, args=(filename, index, is_rob), timeout=6000, result_ttl=5000)

    return jsonify(id=job.id)


@app.route('/tasks/<task_id>')
def get_status(task_id):
    job = q.fetch_job(task_id)
    if job:
        return jsonify({
            'data': {
                'job_id': job.get_id(),
                'status': job.get_status(),
                'es_id': job.meta.get('es_id'),
                'images': job.meta.get('images'),
                'error': job.meta.get('error'),
                'progress': job.meta.get('progress')
            }
        })    
    return jsonify(error="not found")


@app.route("/tag-pos")
def tag_pos():
    try:
        sentence = request.args.get('sentence')
        tagged = pos_tag(word_tokenize(sentence))
        tagged = [{"value": t[0], "tag": t[1]} for t in tagged]
        return jsonify(tagged=tagged)
    except Exception as error:
        return jsonify(error=error)

@app.route("/discover-images")
def discover_images():
    try:
        words = [s.strip() for s in request.args.get('words').split(",")]
        suffixes = [s.strip() for s in request.args.get('suffixes').split(",")]

        pool = Pool(4)
        args = zip(words, repeat([suffixes, len(words)]))
        images = pool.map(wikipedia_image_search, args)        
        images = [item for sublist in images for item in sublist]

        print("Found " + str(len(images)) + " images.")
        return jsonify(images=images)
    except Exception as error:
        print("ERR:", error)
        return jsonify(error=error)

@app.route("/upload-images", methods=['POST'])
def upload_images():
    try:
        # redis_conn.flushall()
        old_job_ids = registry.get_job_ids()
        
        if len(old_job_ids) > 0:
            message = "Already processing file. Please wait a minute and try again."
            return jsonify(error=message)     

        job = q.enqueue_call(
            func=upload_images_to_s3,
            args=(request.json),
            timeout=6000,
            result_ttl=5000)

        return jsonify(id=job.id)            
    except Exception as error:
        print("ERR:", error)
        return jsonify(error=error)        

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print("running...")
    app.run(host='0.0.0.0', debug=False, port=port)
