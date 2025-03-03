from langgraph.graph import MessagesState
from usp.tree import sitemap_tree_for_homepage
import requests

class State(MessagesState):
    relevant: str
    count: int

def is_valid_url(url):
    try:
        response = requests.get(url, timeout=5, headers={"User-Agent": "Mozilla/5.0"})
        return response.status_code == 200
    except requests.exceptions.RequestException:
        return False

def getPagesFromSitemap(fullDomain):
    listPagesRaw = []
    tree = sitemap_tree_for_homepage(fullDomain)
    for page in tree.all_pages():
        if page.url in listPagesRaw:
            pass
        else:
            if is_valid_url(page.url):
                listPagesRaw.append(page.url)
    return listPagesRaw
