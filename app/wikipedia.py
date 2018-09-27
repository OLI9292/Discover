import os
import redis

from mediawiki import MediaWiki
wikipedia = MediaWiki()


redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
db = redis.from_url(redis_url)


def wikipedia_links(title):
    page = wikipedia.page(title)
    if page == None:
        return []
    return page.links


def wikipedia_content(title):
    try:
        cached = db.get(title)
        if cached != None:
            return cached.decode("utf-8")
        content = wikipedia.page(title).content
        clean = content.split("== See also")[0]
        db.set(title, clean)
        return clean
    except Exception as e:
        print("error fetching " + title, e)
        return None
