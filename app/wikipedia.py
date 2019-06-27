import json
import requests
from functools import wraps
from bs4 import BeautifulSoup
import uuid
import hashlib

from index_text import add_to_current_job
from s3 import s3_resource

API_URL = 'https://commons.wikimedia.org/w/api.php'
IMAGE_BUCKET = 'invisible-college-images'


def enrich_wiki_image(data):
    raw_page = requests.get(API_URL, params=raw(data['title'])).json()

    if "parse" in raw_page:
      metadata = parse_raw_page(raw_page["parse"]["text"]["*"])
      data.update(metadata)
        
    return data

def upload_images_to_s3(*argv):
  images = []
  counter = 0

  for image in argv:
    image = enrich_wiki_image(image)
    key = str(uuid.uuid4()) + ".jpg"
    data = requests.get(image["url"], stream=True).raw.read()
    s3_resource.Bucket(IMAGE_BUCKET).put_object(Key=key, Body=data)
    image["url"] = IMAGE_BUCKET + "/" + key
    images.append(image)
    add_to_current_job('progress', max(counter / float(len(argv)),0.95))
  
  add_to_current_job('images', images)
  return

def search_images_params(search_term):
  return {
    'action': 'query',
    'format': 'json',
    'generator': 'search', 
    'gsrnamespace': '',
    'gsrsearch': search_term, 
  }

def raw(page):
  return {
    'action': 'parse',
    'format': 'json',
    'page': "File:" + page
  }
  
# def find_images_params(filenames):
#   return {
#     'action': 'query',
#     'format': 'json',
#     'prop': 'imageinfo', 
#     'titles': '|'.join(filenames), 
#     'iiprop': 'url|metadata'
#   }

def pages_for_(result):
  if 'query' in result and 'pages' in result['query']:
    return result['query']['pages'].values()
  return []

def parse_raw_page(html):
  try:
    permission = "public domain" if "public domain" in html else "creative commons"
    soup = BeautifulSoup(html, 'html.parser')
    descriptions = soup.findAll("td", {"class": "description"})
    caption = "; ".join([d.text.strip() for d in descriptions])
    authors = "; ".join([t.findNext('td').text for t in soup.findAll("td", {"id": "fileinfotpl_aut"})])
    sources = "; ".join([t.findNext('td').text for t in soup.findAll("td", {"id": "fileinfotpl_src"})])
    return {
      "permission": permission,
      "caption": caption,
      "author": authors,
      "source": sources
    }
  except Exception as e:
    print("ERR:",e)
  
def good_image_file(title):
  undesired = ['.svg', '.pdf', '.gif', '.tif', '.ogv', '.webm', 'Deletion requests', 'Featured picture candidates']
  return 'File:' in title and not any(substring in title for substring in undesired)

def add_urls_for(title, word):
  title = title.replace(" ", "_").replace("File:", "")
  md5 = hashlib.md5()
  md5.update(title.encode('utf-8'))
  path = md5.hexdigest()[0] + "/" + md5.hexdigest()[0:2] + "/"
  url = "https://upload.wikimedia.org/wikipedia/commons/" + path + title
  thumbnail = url.replace("commons/","commons/thumb/") + "/200px-" + url.split("/")[-1]

  return {
    "url": url,
    "thumbnail": thumbnail,
    "title": title,
    "word": word
  }


def unpack(func):
    @wraps(func)
    def wrapper(arg_tuple):
        return func(*arg_tuple)
    return wrapper  

# https://www.mediawiki.org/w/api.php?action=help&modules=query
@unpack
def wikipedia_image_search(word, data):
  print("Searching images for " + word)

  requests_counter = 0

  suffixes = data[0]
  word_count = data[1]
  page_limit = 10
  results = []

  # just search the base term if no suffixes given
  if len(suffixes) == 0:
      suffixes.append(None)

  files_for_word = []
      
  for suffix in suffixes:
    search_term = word
    
    if suffix:
        search_term += " " + suffix

    params = search_images_params(search_term)
    counter = 0

    while True:
      counter += 1
      requests_counter += 1
      result = requests.get(API_URL, params=params).json()
      
      if 'error' in result:
        raise Exception(result['error']['info'])

      files_for_word += [p['title'] for p in pages_for_(result) if good_image_file(p['title'])]

      if 'continue' not in result or counter >= page_limit:
        break

      else:
        params.update(result['continue'])

  print("Completed " + word)
  return [add_urls_for(f, word) for f in files_for_word]
