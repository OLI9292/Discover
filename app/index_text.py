import os
from io import BytesIO
import io
import uuid
import re
import urllib
import json
import time
import concurrent.futures
from concurrent.futures import as_completed

from s3 import s3_client

from pdf2image import convert_from_path
try:
    from PIL import Image
except ImportError:
    import Image
import pytesseract

if os.getenv('IS_HEROKU'):
    pytesseract.pytesseract.tesseract_cmd = '/app/.apt/usr/bin/tesseract'

from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter
from pdfminer.converter import TextConverter
from pdfminer.layout import LAParams
from pdfminer.pdfpage import PDFPage

from PyPDF2 import PdfFileWriter, PdfFileReader

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

def add_to_current_job(key, message, override=True):
    job = get_current_job()
    if override:
        job.meta[key] = message
    else:
        job.meta[key] = job.meta.get(key) or message
    job.save_meta() 

def index_text(filename, index, is_rob):
    try:
        print("fetching file from s3")
        obj = s3_client.get_object(Bucket='invisible-college-texts', Key=filename)
        print("reading file")
        text = obj['Body'].read()

        print("cleaning text")
        if filename.endswith("pdf"):
            print("extracting text from pdf")
            text = extract_text_from_pdf(text)
        else:
            text = decode(text)

        text = clean(text)
        print("tokenizing text")
        texts = tokenize(text, index.replace("-","_"), filename_to_title(filename))
        add_to_current_job('progress', 0.925)
        print("indexing " + str(len(texts)) + " documents in elasticsearch")
        helpers.bulk(es_client, texts, routing=1)
        add_to_current_job('progress', 0.95)
        print("success")

        if is_rob:
            time.sleep(7)
            add_to_current_job('progress', 0.975)
            _id = texts[0]["_id"]
            beg = 'mutation { findAddresses(addresses: "'
            data = find_addresses_in_text(index, _id)
            end = '", index: "' + index + '", id: "' + _id + '") }'
            body = { "query" : beg + urllib.quote(json.dumps(data)) + end }
            requests.post(API_URL, json=body)
        
        return
    except Exception as error:
        print("ERR:", error)
        add_to_current_job('error', error)
        return

## OCR
#

def ocr(path):
    page_number = path.replace("tmp/", "").replace(".jpg","")
    return [page_number, pytesseract.image_to_string(Image.open(path))]

def pdf_to_image(path):
    page = float(path.replace(".pdf","").replace("tmp/",""))
    image = convert_from_path(path)[0]   
    return image.save(path.replace(".pdf", ".jpg"))

def ocr_pdf(pdf):
    if os.path.exists("tmp") == False:
        os.makedirs("tmp")
    try:
        path = "tmp/pdf.jpg"
        with open(path, "wb") as outputStream:
            outputStream.write(pdf)

        print("splitting pdf")
        add_to_current_job('progress', 0.05)
        counter = 0
        paths = []
        inputpdf = PdfFileReader(open(path, "rb"))
        pages_count = inputpdf.numPages
        for i in range(pages_count):
            counter += 1
            progress = max(0.1, (0.15 * float(counter) / float(pages_count)))
            add_to_current_job('progress', progress)

            output = PdfFileWriter()
            output.addPage(inputpdf.getPage(i))
            path = "tmp/" + str(counter) + ".pdf"
            paths.append(path)
            with open(path, "wb") as outputStream:
                output.write(outputStream)
        
        print("converting pdf to images")
        with concurrent.futures.ProcessPoolExecutor(max_workers=4) as executor:
            jobs = [executor.submit(pdf_to_image, path) for path in paths]
            counter = 0
            for out in as_completed(jobs):
                counter += 1
                progress = max(0.1, 0.1 + (0.35 * float(counter) / float(pages_count)))
                add_to_current_job('progress', progress)

        print("running ocr on images")
        text = ""
        with concurrent.futures.ProcessPoolExecutor(max_workers=4) as executor:
            jobs = [executor.submit(ocr, path.replace("pdf", "jpg")) for path in paths]
            counter = 0
            for out in as_completed(jobs):
                counter += 1
                progress = max(0.3, 0.3 + (0.6 * float(counter) / float(len(paths))))
                add_to_current_job('progress', progress)
                [page_number, text_result] = out.result()
                text += "\n\n<page>" + page_number + "</page>\n\n"
                text += text_result

        return text
    except Exception as error:
        print(error)
        raise

# File Conversion
#

def extract_text_from_pdf(pdf, max_pages=2000):
    output = BytesIO()
    manager = PDFResourceManager()
    converter = TextConverter(manager, output, laparams=LAParams())
    interpreter = PDFPageInterpreter(manager, converter)

    text = ""
    fp = BytesIO(pdf)
    needs_ocr = True

    page_count = len(list(PDFPage.get_pages(fp)))
    for page_number, page in enumerate(PDFPage.get_pages(fp)):
        if page_number > max_pages:
            break
        if (page_number % 25 == 0) & (page_number > 0):
            print("\tprocessing", page_number)
        
        interpreter.process_page(page)
        value = output.getvalue()

        if len(value) > 100:
            needs_ocr = False
        if (page_number == 15) & needs_ocr:
            text = ocr_pdf(pdf)
            break
        if page_number > 15:
            add_to_current_job('progress', float(page_number) / float(page_count))

        text += "\n\n<page>" + str(page_number) + "</page>\n\n"
        text += output.getvalue().decode("utf-8") 

        output.truncate(0)
        output.seek(0)

    fp.close()
    converter.close()
    output.close()
    
    return text


def convert_epub_to_text(path):
    try:
        book = epub.read_epub(path)
        html = ""
        items = book.get_items()
        for page_number, item in enumerate(items):
            print("Converting page", page_number)
            if item.get_type() == ebooklib.ITEM_DOCUMENT:
                html += item.get_content().decode("utf-8") 
        text = re.sub('<[^<]+?>', '', html)
        return text
    except Exception as error:
        print("ERR:", error)
        raise    


# Data cleaning
#

def filename_to_title(filename):
    remove_strings = [".pdf", ".epub", ".txt", "[", "]", "(b-ok.org)"]
    for s in remove_strings:
        filename = filename.replace(s, "")
    return filename.replace("_", " ").strip().title()

def cmp(a, b):
    return (a > b) - (a < b) 

def normalize_cardinals(data):
    keys = list(number_to_word_mapping.keys())
    keys.sort(key=lambda args: cmp(len(args[1]), len(args[0])))

    lowered = data.lower()

    for key in keys:
        if key in lowered:
            pattern = re.compile(key)
            data = pattern.sub(number_to_word_mapping[key], data)

    values = list(number_to_word_mapping.values())
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
            print("cutting off at percent " + str(round(percent, 3) * 100) + "% (" + string + ")")
            return text[:idx]

    percent = cut_off_percent(text)
    if percent != None:
        print("cutting off at percent " + str(percent * 100) + "% (too many numbers)")
        return text[:int(percent * text_length)]

    return text


def decode(text):    
    try:
        encoding = chardet.detect(text)["encoding"]
        return text.decode(encoding)
    except Exception as error:
        add_to_current_job('error', "Could not decode file.")
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
    return [l[i:i + n] for i in range(0, len(l), n)]


def tokenize(text, index, title):
    documents = []    
    total_word_count = len(text.split())
    
    content = sent_tokenize(text)
    chunked = chunks(content, 20)
    _id = str(uuid.uuid4())

    add_to_current_job('es_id', _id)

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
