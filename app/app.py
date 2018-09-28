import os
import itertools
# Flask
from flask import Flask, Response, jsonify, render_template, request
from flask_cors import CORS, cross_origin
# Caching
from multiprocessing import Pool
# Local Modules
from predictive_corpus import predictive_corpus
from find_passages import find_passages
from lemmatization import get_lemmas, lcd_for_word
from wikipedia import wikipedia_links, wikipedia_content, pool_wikipedia_content
from cache import clear_variables, instance

from rq import Worker, Queue, Connection

import time

app = Flask(__name__)
CORS(app)

q = Queue(connection=instance())


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


@app.route("/wikipedia-links")
def get_wikipedia_links():
    try:
        clear_variables()
        links = wikipedia_links(request.args.get('search'))
        job = q.enqueue_call(
            func=pool_wikipedia_content, args=(links,), result_ttl=5000
        )
        return jsonify(success=True, data=links, job=job.get_id())
    except Exception as error:
        print(error)
        return jsonify(success=False)


@app.route('/tasks/<task_id>')
def get_status(task_id):
    task = q.fetch_job(task_id)
    if task:
        response_object = {
            'status': 'success',
            'data': {
                'task_id': task.get_id(),
                'task_status': task.get_status(),
            }
        }
    else:
        response_object = {'status': 'error'}
    return jsonify(response_object)


@app.route("/predictive-corpus", methods=['GET', 'POST'])
def get_predictive_corpus():
    try:
        titles = request.json["wikipedia_titles"]
        content = "\n".join([wikipedia_content(t, True) for t in titles])
        data = predictive_corpus(content)
        return jsonify(success=True, data=data)
    except Exception as error:
        print(error)
        return jsonify(success=False)


@app.route("/wikipedia-passages", methods=['GET', 'POST'])
def wikipedia_passages():
    try:
        words = request.json["search_words"]
        titles = request.json["wikipedia_titles"]
        data = (find_passages(t, words) for t in titles)
        flattened = list(itertools.chain.from_iterable(list(data)))
        return jsonify(success=True, data=flattened)
    except Exception as error:
        print(error)
        return jsonify(success=False)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', debug=False, port=port)
