import os
from flask import Flask, Response, jsonify, render_template, request

from word_forms.word_forms import get_word_forms

app = Flask(__name__)


@app.route("/lemmas")
def lemmas():
    try:
        word = request.args.get('word')
        word_forms = get_word_forms(word).values()
        data = list(set([i for l in [list(x)
                                     for x in word_forms] for i in l if i != word]))
        return jsonify(success=True, data=data)
    except Exception as error:
        return jsonify(success=False, error=error.message)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
