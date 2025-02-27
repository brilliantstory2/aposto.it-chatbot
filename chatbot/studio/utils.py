from langgraph.graph import MessagesState
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from urllib.parse import urlparse

class State(MessagesState):
    relevant: str
    count: int

def get_all_urls(base_url: str) -> list:
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")

    driver = webdriver.Chrome(options=chrome_options)
    driver.get(base_url)

    # Parse the base domain
    base_domain = urlparse(base_url).netloc

    # Find all anchor elements with href containing '/'
    elements_by_xpath = driver.find_elements(By.XPATH, "//a[contains(@href,'/')]")

    unique_urls = set()
    for link in elements_by_xpath:
        href = link.get_attribute("href")
        if href:
            parsed_href = urlparse(href)
            if parsed_href.netloc == base_domain and 'uploads' not in parsed_href.path:
                unique_urls.add(href)

    driver.quit()
    return list(unique_urls)