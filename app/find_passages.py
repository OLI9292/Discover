from nltk import word_tokenize
from nltk.tokenize import sent_tokenize
import itertools

from wikipedia import wikipedia_content

MAX_CONTEXT = 10


def clean_sentence(sentence):
    return " ".join(sentence.strip().split())


def make_header(string):
    if "." in string:
        return string
    return "== " + string + " =="


def is_header(sentence):
    return "== " in sentence


def separate_headers(sentence):
    split_str = "===" if "===" in sentence else "=="
    return [make_header(x) for x in filter(None, [s.strip() for s in sentence.split(split_str)])]


def find_passages(args):
    return find_passages_unpacked(*args)


def find_passages_unpacked(title, search_words):
    content = wikipedia_content(title)

    sentences = map(clean_sentence, sent_tokenize(content))
    sentences = list(itertools.chain.from_iterable(
        [separate_headers(s) for s in sentences]))

    latest_end_idx = 0
    passages = []

    search_phrases = [word for word in search_words if word.count(" ") > 0]
    search_words = list(set(search_words) - set(search_phrases))

    for idx in range(0, len(sentences)):
        sentence = sentences[idx].lower()
        if is_header(sentence):
            continue

        words = word_tokenize(sentence)
        word_matches = [w for w in words if any(s in w for s in search_words)]
        phrase_matches = [p for p in search_phrases if p in sentence]
        matches = word_matches + phrase_matches

        if len(matches) > 0:
            start_idx = max(0, idx - MAX_CONTEXT)
            if start_idx < latest_end_idx:
                continue
            end_idx = min(idx + MAX_CONTEXT, len(sentences))
            latest_end_idx = end_idx
            passages.append({
                "title": title,
                "context": sentences[start_idx:end_idx],
                "matchIdx": idx - start_idx,
                "startIdx": start_idx,
                "endIdx": end_idx,
                "matches": matches
            })

    remove = ["startIdx", "endIdx"]

    return [{key: passage[key] for key in passage if key not in remove} for passage in passages]
