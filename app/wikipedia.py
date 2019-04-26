import time
import pprint
import json
import requests

pp = pprint.PrettyPrinter(indent=1)

SUFFIXES = ['diagram','illustration']
API_URL = 'https://commons.wikimedia.org/w/api.php'

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

# https://www.mediawiki.org/w/api.php?action=help&modules=query
def wikipedia_image_search(words, suffixes, page_limit = 5):
  start = time.time()
  results = []

  if len(suffixes) == 0:
      suffixes.append(None)

  for word in words:
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
      params = find_images_params(files_for_word[0:50])
      result = requests.get(API_URL, params=params).json()
      if 'error' in result:
        raise Exception(result['error']['info'])
      pages = [p for p in pages_for_(result) if 'imageinfo' in p and len(p['imageinfo'])]
      for page in pages:
        results.append({
          'word': word,
          'title': page['title'],
          'url': page['imageinfo'][0]['url'],
          'descriptionUrl': page['imageinfo'][0]['descriptionurl']
        })

  print("Found " + str(len(results)) + " results")
  pp.pprint(results)
  end = time.time()
  print(end - start)
  return results
