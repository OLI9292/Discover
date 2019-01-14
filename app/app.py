import os
import itertools
import json
import os
import sys
sys.dont_write_bytecode = True

from flask import Flask, Response, jsonify, render_template, request
from flask_cors import CORS, cross_origin

from lemmatization import get_lemmas, lcd_for_word
from address import find_addresses_in_text
from index_text import index_text, convert_epub_to_text

from rq import Queue
from rq.registry import StartedJobRegistry
from redis import Redis

from s3 import s3_resource

app = Flask(__name__)
CORS(app)

REDIS_URL = os.getenv('REDIS_URL', 'http://localhost:6379')
redis_conn = Redis.from_url(REDIS_URL)

q = Queue(connection=redis_conn)
registry = StartedJobRegistry('default', connection=redis_conn)

@app.route("/index-texts", methods=['GET', 'POST'])
def index_texts():
    text = request.files["text"]
    filename = text.filename
    index = request.args.get('index')
    if index == None:
        return jsonify(error="index missing")
    # Convert epubs to text
    if filename.endswith("epub"):
        if os.path.exists("tmp") == False:
            os.makedirs("tmp")
        text.save("tmp/" + filename)
        text = convert_epub_to_text("tmp/" + filename)
        filename = filename.replace("epub", "txt")
    # Store file on S3
    s3_resource.Bucket('invisible-college-texts').put_object(Key=filename, Body=text)
    # Check if job already running
    old_job_ids = registry.get_job_ids()
    if len(old_job_ids) > 0:
        message = "Already processing file. Please wait a minute and try again."
        return jsonify(error=message)
    # Send to Background queue
    job = q.enqueue_call(func=index_text, args=(filename, index), timeout=1000, result_ttl=5000)
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
                'error': job.meta.get('error')
            }
        })    
    return jsonify(error="not found")


@app.route("/lemmatizations")
def lemmatizations():
    try:
        word = request.args.get('word')
        lemmas = get_lemmas(word)
        lcd = lcd_for_word(word, lemmas)
        return jsonify(lemmas=lemmas, lcd=lcd)
    except Exception as error:
        return jsonify(error=error)


@app.route("/find-addresses", methods=['GET', 'POST'])
def find_addresses():
    data = find_addresses_in_text(request.args.get("index"), request.args.get("id"))
    return jsonify(addresses=data)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', debug=False, port=port)
