from mediawiki import MediaWiki
wikipedia = MediaWiki()

from cache import get_variable, set_variable


def wikipedia_links(title):
    page = wikipedia.page(title)
    if page == None:
        return []
    return page.links


def wikipedia_content(title, return_content=False):
    try:
        cached = get_variable(title)
        if cached != None:
            return cached.decode("utf-8")
        content = wikipedia.page(title).content
        clean = content.split("== See also")[0]
        set_variable(title, clean)
        return clean if return_content else len(clean)
    except Exception as e:
        print("error fetching " + title, e)
        return None
