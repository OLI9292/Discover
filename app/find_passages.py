from nltk import word_tokenize
from nltk.tokenize import sent_tokenize
import itertools

MAX_CONTEXT = 10


def clean_sentence(sentence):
    return " ".join(sentence.strip().split())


def make_header(string):
    if "." in string:
        return string
    return "== " + string + " =="


def separate_headers(sentence):
    split_str = "===" if "===" in sentence else "=="
    return [make_header(x) for x in filter(None, [s.strip() for s in sentence.split(split_str)])]


def find_passages(content, title, search_words):
    sentences = map(clean_sentence, sent_tokenize(content))
    sentences = list(itertools.chain.from_iterable(
        [separate_headers(s) for s in sentences]))

    latest_end_idx = 0
    passages = []

    for idx in range(0, len(sentences)):
        words = word_tokenize(sentences[idx].lower())
        matches = [w for w in words if any(s in w for s in search_words)]
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
