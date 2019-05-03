import json
import requests
from functools import wraps
from bs4 import BeautifulSoup
import uuid

from index_text import add_to_current_job
from s3 import s3_resource

API_URL = 'https://commons.wikimedia.org/w/api.php'
IMAGE_BUCKET = 'invisible-college-images'

def upload_images_to_s3(*argv):
  images = []
  counter = 0

  for image in argv:
    print "uploading " + image["url"]
    counter +=1
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
    'page': page 
  }
  
def find_images_params(filenames):
  return {
    'action': 'query',
    'format': 'json',
    'prop': 'imageinfo', 
    'titles': '|'.join(filenames), 
    'iiprop': 'url|metadata'
  }

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
    print "ERR:",e
  

def unpack(func):
    @wraps(func)
    def wrapper(arg_tuple):
        return func(*arg_tuple)
    return wrapper

# https://www.mediawiki.org/w/api.php?action=help&modules=query
@unpack
def wikipedia_image_search(word, suffixes):
  page_limit = 2
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
      result = requests.get(API_URL, params=params).json()
      if 'error' in result:
        raise Exception(result['error']['info'])
      titles = [p['title'] for p in pages_for_(result)] 
      files_for_word += [t for t in titles if 'File' in t and 'svg' not in t and 'pdf' not in t]
      if 'continue' not in result or counter >= page_limit:
        break
      else:
        params.update(result['continue'])
        
  if len(files_for_word):
    params = find_images_params(files_for_word[0:25])
    result = requests.get(API_URL, params=params).json()
    if 'error' in result:
      raise Exception(result['error']['info'])
    pages = [p for p in pages_for_(result) if 'imageinfo' in p and len(p['imageinfo'])]
    
    for page in pages:
      data = {}

      data.update({
        'word': word,
        'title': page['title'],
        'url': page['imageinfo'][0]['url'],
        'descriptionUrl': page['imageinfo'][0]['descriptionurl']
      })

      raw_page = requests.get(API_URL, params=raw(page['title'])).json()
      if "parse" in raw_page:
        metadata = parse_raw_page(raw_page["parse"]["text"]["*"])
        data.update(metadata)
        
      results.append(data)

  return results
