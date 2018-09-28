import nltk
from nltk import FreqDist, ne_chunk, pos_tag, word_tokenize
from nltk.collocations import *
from nltk.tree import Tree

from wikipedia import wikipedia_content

import numpy

import string

bigram_measures = nltk.collocations.BigramAssocMeasures()
trigram_measures = nltk.collocations.TrigramAssocMeasures()

ascii_all = set(string.ascii_lowercase + string.ascii_lowercase)
translate_table = dict((ord(char), None) for char in string.punctuation)
stopwords = ['see', 'also', 'eg', 'all', 'just', 'being', 'over', 'both', 'through', 'yourselves', 'its', 'before', 'herself', 'had', 'should', 'to', 'only', 'under', 'ours', 'has', 'do', 'them', 'his', 'very', 'they', 'not', 'during', 'now', 'him', 'nor', 'did', 'this', 'she', 'each', 'further', 'where', 'few', 'because', 'doing', 'some', 'are', 'our', 'ourselves', 'out', 'what', 'for', 'while', 'does', 'above', 'between', 't', 'be', 'we', 'who', 'were', 'here', 'hers', 'by', 'on', 'about', 'of', 'against', 's',
             'or', 'own', 'into', 'yourself', 'down', 'your', 'from', 'her', 'their', 'there', 'been', 'whom', 'too', 'themselves', 'was', 'until', 'more', 'himself', 'that', 'but', 'don', 'with', 'than', 'those', 'he', 'me', 'myself', 'these', 'up', 'will', 'below', 'can', 'theirs', 'my', 'and', 'then', 'is', 'am', 'it', 'an', 'as', 'itself', 'at', 'have', 'in', 'any', 'if', 'again', 'no', 'when', 'same', 'how', 'other', 'which', 'you', 'after', 'most', 'such', 'why', 'a', 'off', 'i', 'yours', 'so', 'the', 'having', 'once']


def merge_two_dicts(x, y):
    z = x.copy()
    z.update(y)
    return z


def predictive_corpus(content):
    return merge_two_dicts(
        get_ner(content),
        get_ngrams(content)
    )


def get_ner(content):
    tokenized = word_tokenize(content)
    return get_continuous_chunks(tokenized)


def get_continuous_chunks(tokenized):
    chunked = ne_chunk(pos_tag(tokenized))
    continuous_chunk = []
    current_chunk = []
    names = []

    for i in chunked:
        if type(i) == Tree:
            label = i.label()
            name = " ".join([token for token, pos in i.leaves()])
            current_chunk.append((label, name))
        elif current_chunk:
            label = current_chunk[0][0]
            name = " ".join([x[1] for x in current_chunk])
            if name not in names:
                continuous_chunk.append((label, name))
                names.append(name)
                current_chunk = []
        else:
            continue

    results = {"people": [], "places": [], "organizations": []}

    for chunk in continuous_chunk:
        if chunk[1].count(" ") > 1:
            if chunk[0] == "PERSON":
                results["people"].append(chunk[1])
            elif chunk[0] == "ORGANIZATION":
                results["organizations"].append(chunk[1])
            elif chunk[0] == "LOCATION":
                results["places"].append(chunk[1])

    return results


def get_ngrams(content):
    tokenized = clean_and_tokenize(content)
    words = frequent_words(tokenized)
    ngrams = frequent_ngrams(tokenized)
    return {"words": words, "ngrams": ngrams}


def clean_and_tokenize(content):
    lowered = content.lower()
    stripped = lowered.translate(translate_table)
    return word_tokenize(stripped)


def frequent_words(tokenized, count=20):
    filtered = filter(lambda word: not word.lower() in stopwords, tokenized)
    words = [word[0]
             for word in FreqDist(filtered).most_common(count) if word[1] > 1]
    return words


def frequent_ngrams(tokenized, count=20):
    grams_list = []

    finder = BigramCollocationFinder.from_words(tokenized)
    finder.apply_word_filter(lambda w: w in stopwords)
    grams_list.extend(finder.nbest(bigram_measures.pmi, 10))
    grams_list.extend(finder.nbest(bigram_measures.raw_freq, 10))

    finder = TrigramCollocationFinder.from_words(tokenized)
    finder.apply_word_filter(lambda w: w in stopwords)
    grams_list.extend(finder.nbest(trigram_measures.pmi, 10))
    grams_list.extend(finder.nbest(trigram_measures.raw_freq, 10))

    grams_list = [' '.join(map(str, e)) for e in grams_list if all(
        ascii_all.issuperset(word) for word in e)]
    grams_list = list(set(grams_list))
    grams_list.sort()
    return grams_list
