from langgraph.graph import MessagesState
from pydantic import BaseModel, Field
from usp.tree import sitemap_tree_for_homepage
import requests

class State(MessagesState):
    relevant: str
    count: int
    is_location_provided: str
    latitude: float
    longitude: float

class Location(BaseModel):
    latitude: str = Field(None, description="latitude of user's location")
    longitude: str = Field(None, description="longitude of user's location")

def is_valid_url(url):
    try:
        if url.find("/emagazine/tag/")!=-1:
            return False
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
