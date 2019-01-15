import os
from io import BytesIO
import io
import uuid
import inflect
import re
import urllib
import json
import time

from s3 import s3_client

from pdf2image import convert_from_bytes
try:
    from PIL import Image
except ImportError:
    import Image
import pytesseract

if os.getenv('IS_HEROKU'):
    pytesseract.pytesseract.tesseract_cmd = '/app/.apt/usr/bin/tesseract'

from cStringIO import StringIO
from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter
from pdfminer.converter import TextConverter
from pdfminer.layout import LAParams
from pdfminer.pdfpage import PDFPage

import chardet
import requests

import ebooklib
from ebooklib import epub

from nltk.tokenize import sent_tokenize

from data.number_to_word_mapping import number_to_word_mapping
from address import find_addresses_in_text

from rq import get_current_job

from elasticsearch import helpers
from es import es_client

API_URL = os.getenv('API_URL', "http://localhost:3002/graphql")

def index_text(filename, index, is_rob):
    try:
        obj = s3_client.get_object(Bucket='invisible-college-texts', Key=filename)
        text = obj['Body'].read()
        
        if filename.endswith("pdf"):
            text = extract_text_from_pdf(text)
        else:
            text = decode(text)

        text = clean(text)
        texts = tokenize(text, index, filename_to_title(filename))
        helpers.bulk(es_client, texts, routing=1)
        
        # mccully
        if is_rob:
            time.sleep(2)
            _id = texts[0]["_id"]
            beg = 'mutation { findAddresses(addresses: "'
            data = find_addresses_in_text(index, _id)
            end = '", index: "' + index + '", id: "' + _id + '") }'
            body = { "query" : beg + urllib.quote(json.dumps(data)) + end }
            requests.post(API_URL, json=body)
        
        return
    except Exception as error:
        job = get_current_job()
        job.meta['error'] = job.meta.get('error') or error.message
        job.save_meta()
        return

## OCR
#

def ocr_pdf(pdf):
    if os.path.exists("tmp") == False:
        os.makedirs("tmp")
    try:
        images = convert_from_bytes(pdf)
        counter = 0
        paths = []
        
        for image in images:
            counter += 1
            path = "tmp/" + str(counter) + ".jpg"
            image.save(path)
            paths.append(path)

        text = ""
        for page_number in range(0, len(paths)):
            if (page_number % 5 == 0) & (page_number > 0):
                print "\tprocessing", page_number
            text += "\n\n<page>" + str(page_number) + "</page>\n\n"
            text += pytesseract.image_to_string(Image.open(paths[page_number]))

        return text
    except Exception as error:
        print error
        raise

# File Conversion
#

def extract_text_from_pdf(pdf, max_pages=2000):
    output = BytesIO()
    manager = PDFResourceManager()
    converter = TextConverter(manager, output, laparams=LAParams())
    interpreter = PDFPageInterpreter(manager, converter)

    text = ""
    fp = StringIO(pdf)
    needs_ocr = True

    for page_number, page in enumerate(PDFPage.get_pages(fp)):        
        if page_number > max_pages:
            break
        if (page_number % 25 == 0) & (page_number > 0):
            print "\tprocessing", page_number
        
        interpreter.process_page(page)
        value = output.getvalue()

        if len(value) > 100:
            needs_ocr = False
        if (page_number == 15) & needs_ocr:
            text = ocr_pdf(pdf)
            break

        text += "\n\n<page>" + str(page_number) + "</page>\n\n"
        text += output.getvalue()

        output.truncate(0)
        output.seek(0)

    fp.close()
    converter.close()
    output.close()
    return text if needs_ocr else decode(text)


def convert_epub_to_text(path):
    book = epub.read_epub(path)
    html = ""
    for item in book.get_items():
        if item.get_type() == ebooklib.ITEM_DOCUMENT:
            html += item.get_content()
    text = re.sub('<[^<]+?>', '', html)
    return text

# Data cleaning
#

def filename_to_title(filename):
    remove_strings = [".pdf", ".epub", ".txt", "[", "]", "(b-ok.org)"]
    for s in remove_strings:
        filename = filename.replace(s, "")
    return filename.replace("_", " ").strip().title()

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


def decode(text):    
    try:
        encoding = chardet.detect(text)["encoding"]
        return text.decode(encoding)
    except Exception as error:
        job = get_current_job()
        job.meta['error'] = "Could not decode file."
        job.save_meta()
        raise

def clean(text):
    text = text.replace("-", " ")
    text = remove_multiple_spaces(text)
    text = attach_overrun_words(text)
    text = attach_paragraph(text)
    text = normalize_cardinals(text)
    text = cut_off_index(text)
    return text

# Format for ElasticSearch
#


def chunks(l, n):
    return [l[i:i + n] for i in xrange(0, len(l), n)]


def tokenize(text, index, title):
    documents = []    
    total_word_count = len(text.split())
    
    content = sent_tokenize(text)
    chunked = chunks(content, 20)
    _id = str(uuid.uuid4())

    job = get_current_job()
    job.meta['es_id'] = _id
    job.save_meta()

    passages = [] 
    word_count = 0

    for section, sentences in enumerate(chunked):
        word_count += len(" ".join(sentences).split())
        word_index_perc = round((float(word_count) / total_word_count) * 100, 2)
        found_at = str(word_count) + "/" + str(total_word_count) + " (" + str(word_index_perc) + "%)"
        passages.append({
            "_index": index,
            "_type": "_doc",
            "section": section,
            "title": title,
            "sentences": sentences,
            "found_at": found_at,
            "join_field": {
                "name": "passage",
                "parent": _id
            }
        })

    t = {
        "_index": index,
        "_type": "_doc",
        "_id": _id,
        "title": title,
        "word_count": total_word_count,
        "sections_count": len(chunked),
        "join_field": {
            "name": "book"
        }
    }

    documents.append(t)
    documents.extend(passages)
    return documents
