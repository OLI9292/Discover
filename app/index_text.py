from io import BytesIO
from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter
from pdfminer.converter import TextConverter
from pdfminer.layout import LAParams
from pdfminer.pdfpage import PDFPage

import ebooklib
from ebooklib import epub

from nltk.tokenize import sent_tokenize
import uuid

import inflect
import re

from elasticsearch import Elasticsearch
from elasticsearch import helpers

es = Elasticsearch(
    ["https://ee2174119d634def91a0a4b2a91c19e4.us-east-1.aws.found.io:9243"],
    http_auth=('elastic', '3y44M8nGXMrppI9OQWikcxZZ')
)


def index_text(path, filename, index):
    text = ""

    if filename.endswith(".pdf"):
        text = convert_pdf_to_text(path, 50)
    if filename.endswith(".epub"):
        text = convert_epub_to_text(path)

    text = clean(text)
    texts = tokenize(text, index, filename)
    helpers.bulk(es, texts, routing=1)
    print "Success"
    return

# File Conversion
#


def convert_pdf_to_text(path, max_pages=2000):
    output = BytesIO()
    manager = PDFResourceManager()
    converter = TextConverter(manager, output, laparams=LAParams())
    interpreter = PDFPageInterpreter(manager, converter)

    text = ""
    infile = file(path, 'rb')
    for page_number, page in enumerate(PDFPage.get_pages(infile)):
        if page_number > max_pages:
            break
        if page_number % 5 == 0:
            print "\t", page_number
        interpreter.process_page(page)
        text += output.getvalue()
        text += "\n\n<page>" + str(page_number) + "</page>\n\n"
        output.truncate(0)
        output.seek(0)

    infile.close()
    converter.close()
    output.close()
    return text


def convert_epub_to_text(filename):
    book = epub.read_epub(filename)
    html = ""
    for item in book.get_items():
        if item.get_type() == ebooklib.ITEM_DOCUMENT:
            html += item.get_content()
    text = re.sub('<[^<]+?>', '', html)
    return text

# Data cleaning
#


p = inflect.engine()
number_to_word_mapping = {}
word_to_number_mapping = {}

for i in range(1, 250):
    word_form = p.number_to_words(i)
    ordinal_word = p.ordinal(word_form)
    ordinal_number = p.ordinal(i)
    number_to_word_mapping[ordinal_number] = ordinal_word.replace(
        "-", " ").title()
    word_to_number_mapping[ordinal_word.replace(
        "-", " ").title()] = ordinal_number


def convert_word_to_cardinal(data, extension):
    keys = word_to_number_mapping.keys()
    keys.sort(lambda x, y: cmp(len(y), len(x)))
    for key in keys:
        if key in data:
            pattern = re.compile(key, re.IGNORECASE)
            replacement = word_to_number_mapping[key] if extension else re.sub(
                "[^0-9]", "", word_to_number_mapping[key])
            data = pattern.sub(replacement, data)
    return data


def normalize_cardinals(data):
    keys = number_to_word_mapping.keys()
    keys.sort(lambda x, y: cmp(len(y), len(x)))

    lowered = data.lower()

    for key in keys:
        if key in lowered:
            pattern = re.compile(key)
            data = pattern.sub(number_to_word_mapping[key], data)

    values = number_to_word_mapping.values()
    for value in values:
        if value.lower() in lowered:
            pattern = re.compile(value, re.IGNORECASE)
            data = pattern.sub(value, data)

    return data


def remove_multiple_spaces(text):
    return re.sub(' +', ' ', text)


def attach_overrun_words(text):
    indices = [m.start(0) for m in re.finditer("[a-z]-\n[a-z]", text)]
    for count, idx in enumerate(indices):
        start = idx + 1 - (count * 2)
        end = start + 2
        text = text[:start] + text[end:]
    return text


def attach_paragraph(text):
    indices = [m.start(0) for m in re.finditer("[^\n]\n[^\n]", text)]
    for idx in indices:
        text = text[:idx + 1] + " " + text[idx + 2:]
    return text


step = 5
minus_amount = 0.02
float_range = [float(x) / 1000 for x in range(600, 1000, step)]


def cut_off_percent(string):
    string = re.sub(r'\W+', '', string)
    length = len(string)

    center_string = string[int(length * 0.3):int(length * 0.5)]
    center_avg = round(
        len([x for x in center_string if x.isalpha()]) / float(len(center_string)), 2)

    count = 0
    return_percent = 0

    for x in float_range:
        end_idx = int(x * length)
        recent_idx = int((x - (float(step) / 100)) * length)

        recent = list(string[recent_idx:end_idx])
        recent_char_perc = round(
            len([x for x in recent if x.isalpha()]) / float(len(recent)), 2)

        percent = round(float(end_idx) / length, 3)

        too_many_numbers = center_avg > recent_char_perc + 0.02

        if too_many_numbers:
            count += 1
            if count == 1:
                return_percent = percent - minus_amount
            if count == 3:
                return return_percent
        else:
            count = 0

    return None


def cut_off_index(text):
    text_length = len(text)

    string = "this page intentionally left blank"
    for match in re.finditer(string, text.lower()):
        idx = match.start()
        percent = float(idx) / text_length
        if percent > 0.9:
            print "cutting off at percent " + \
                str(round(percent, 3) * 100) + "% (" + string + ")"
            return text[:idx]

    percent = cut_off_percent(text)
    if percent != None:
        print "cutting off at percent " + \
            str(percent * 100) + "% (too many numbers)"
        return text[:int(percent * text_length)]

    return text


def clean(text):
    text = text.replace("-", " ")
    text = remove_multiple_spaces(text)
    text = attach_overrun_words(text)
    text = attach_paragraph(text)
    text = normalize_cardinals(text)
    text = cut_off_index(text)
    text = text.decode('utf-8')
    return text

# Format for ElasticSearch
#


def chunks(l, n):
    return [l[i:i + n] for i in xrange(0, len(l), n)]


def tokenize(text, index, title):
    documents = []
    content = sent_tokenize(text)
    chunked = chunks(content, 20)
    _id = str(uuid.uuid4())

    t = {
        "_index": index,
        "_type": "_doc",
        "_id": _id,
        "title": title,
        "sections_count": len(chunked),
        "join_field": {
            "name": "book"
        }
    }

    documents.append(t)

    passages = [{
        "_index": index,
        "_type": "_doc",
        "section": section,
        "title": title,
        "sentences": sentences,
        "join_field": {
            "name": "passage",
            "parent": _id
        }
    } for section, sentences in enumerate(chunked)]

    documents.extend(passages)
    return documents
