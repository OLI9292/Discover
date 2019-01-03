import os
import itertools
import json
import os
import sys
sys.dont_write_bytecode = True

from flask import Flask, Response, jsonify, render_template, request
from flask_cors import CORS, cross_origin

from entity_detector.address import find_addresses_in_text

from index_text import index_text, convert_epub_to_text
from lemmatization import get_lemmas, lcd_for_word
from cache import clear_variables, instance

from werkzeug.utils import secure_filename

from rq import Worker, Queue, Connection

import time

from s3 import s3_resource

app = Flask(__name__)
CORS(app)

q = Queue(connection=instance())


@app.route("/index-texts", methods=['GET', 'POST'])
def index_texts():
    f = request.files["text"]
    filename = f.filename
    index = request.args.get('index')
    if index == None:
        return jsonify({ 'error': 'index is missing' })    
    
    if os.path.exists("tmp") == False:
        os.makedirs("tmp")
    
    if filename.endswith("epub"):
        f.save("tmp/" + filename)
        text = convert_epub_to_text("tmp/" + filename)
        filename = filename.replace("epub", "txt")
    
    s3_resource.Bucket('invisible-college-images').put_object(Key=filename, Body=text)

    job = q.enqueue_call(func=index_text, args=(filename, index), result_ttl=5000)
    return jsonify(success=True, id=job.id)


@app.route('/tasks/<task_id>')
def get_status(task_id):
    job = q.fetch_job(task_id)
    if job:
        response_object = {
            'status': 'success',
            'data': {
                'job_id': job.get_id(),
                'status': job.get_status(),
                'es_id': job.meta.get('es_id')
            }
        }
    else:
        response_object = {'status': 'error'}
    return jsonify(response_object)


@app.route("/lemmatizations")
def lemmatizations():
    try:
        word = request.args.get('word')
        lemmas = get_lemmas(word)
        lcd = lcd_for_word(word, lemmas)
        return jsonify(success=True, lemmas=lemmas, lcd=lcd)
    except Exception as error:
        print(error)
        return jsonify(success=False)


@app.route("/find-addresses", methods=['GET', 'POST'])
def find_addresses():
    return jsonify(find_addresses_in_text(request.args.get("index"), request.args.get("id")))


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', debug=False, port=port)
