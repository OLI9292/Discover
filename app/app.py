import os
# Flask
from flask import Flask, Response, jsonify, render_template, request
from flask_cors import CORS, cross_origin
from flask_socketio import SocketIO, emit, send
# Caching
import redis
from rq import Queue
from worker import conn
from multiprocessing import Pool
# Local Modules
from predictive_corpus import predictive_corpus
from find_passages import find_passages
from lemmatization import get_lemmas, lcd_for_word
# Etc
from mediawiki import MediaWiki
wikipedia = MediaWiki()
import itertools

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app)

redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
db = redis.from_url(redis_url)


@app.route("/lemmatizations")
def lemmatizations():
    try:
        word = request.args.get('word')
        lemmas = get_lemmas(word)
        lcd = lcd_for_word(word, lemmas)
        return jsonify(success=True, lemmas=lemmas, lcd=lcd)
    except Exception as error:
        return jsonify(success=False, error=error.message)


@app.route("/wikipedia-links")
def wikipedia_links():
    try:
        search = request.args.get('search')
        links = wikipedia.page(search).links

        pool = Pool(10)
        results = pool.map(wikipedia_content, links)

        data = {}
        for (title, content) in zip(links, results):
            if content != None:
                data[title] = len(content)

        return jsonify(success=True, data=data)
    except Exception as error:
        return jsonify(success=False, error=error.message)


def wikipedia_content(title):
    try:
        cached = db.get(title)
        if cached != None:
            return cached.decode("utf-8")
        content = wikipedia.page(title).content
        clean = content.split("== See also")[0]
        db.set(title, clean)
        return clean
    except Exception as e:
        print("error fetching " + title, e)
        return None


def cached_wikipedia_content(titles):
    data = {}
    for title in titles:
        content = wikipedia_content(title)
        if content != None:
            try:
                data[title] = content
            except Exception:
                print("error decoding " + title)
    return data


@app.route("/predictive-corpus", methods=['GET', 'POST'])
def get_predictive_corpus():
    try:
        content = cached_wikipedia_content(request.json["wikipedia_titles"])
        content = "\n".join(content.values())
        data = predictive_corpus(content)
        return jsonify(success=True, data=data)
    except Exception as error:
        return jsonify(success=False, error=error.message)


@app.route("/wikipedia-passages", methods=['GET', 'POST'])
def wikipedia_passages():
    try:
        content = cached_wikipedia_content(request.json["wikipedia_titles"])
        words = request.json["search_words"]
        data = [find_passages(content[k], k, words) for k in content.keys()]
        flattened = list(itertools.chain.from_iterable(data))
        return jsonify(success=True, data=flattened)
    except Exception as error:
        print(error)
        return jsonify(success=False)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app=app, debug=True, host='0.0.0.0',
                 port=port, use_reloader=False)
