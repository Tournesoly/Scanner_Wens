
from selenium.webdriver.common.by import By
from selenium.common.exceptions import StaleElementReferenceException
from urllib.parse import urlparse, urljoin

import json
import traceback
import re
import logging

import Classes

# If the url is from a form then the form method is used
# However, javascript overrides the form method.
def url_to_request(url, form_method=None):
    purl = urlparse(url)

    if form_method:
        method = form_method
    else:
        method = "get"

    if purl.scheme == "javascript":
        method = "javascript"
    return Classes.Request(url, method)


# Looks for a and form urls
def extract_urls(driver):
    urls = set()

    # Search for urls in <a>
    elem = driver.find_elements(By.TAG_NAME, "a")
    for el in elem:
        try:
            if (href := el.get_attribute("href")):
                urls.add(url_to_request(href))
        except StaleElementReferenceException as e:
            print("Stale pasta in action")
        except Exception:
            print("Failed to write element")
            print(traceback.format_exc())

    # Search for urls in <frame>
    elem = []  # Placeholder for <frame> elements if necessary
    for el in elem:
        try:
            if (src := el.get_attribute("src")):
                urls.add(url_to_request(src))
        except StaleElementReferenceException as e:
            print("Stale pasta in action")
        except Exception:
            print("Failed to write element")
            print(traceback.format_exc())

    # Search for urls in <iframe>
    elem = driver.find_elements(By.TAG_NAME, "iframe")
    for el in elem:
        try:
            if (src := el.get_attribute("src")):
                urls.add(url_to_request(src))
        except StaleElementReferenceException as e:
            print("Stale pasta in action")
        except Exception:
            print("Failed to write element")
            print(traceback.format_exc())

    # Search for urls in <meta>
    elem = driver.find_elements(By.TAG_NAME, "meta")
    for el in elem:
        try:
            if el.get_attribute("http-equiv") and el.get_attribute("content"):
                if el.get_attribute("http-equiv").lower() == "refresh":
                    m = re.search("url=(.*)", el.get_attribute("content"), re.IGNORECASE)
                    if m:
                        fresh_url = m.group(1)
                        full_fresh_url = urljoin(driver.current_url, fresh_url)
                        urls.add(url_to_request(full_fresh_url))
        except StaleElementReferenceException as e:
            print("Stale pasta in action")
        except Exception:
            print("Failed to write element")
            print(traceback.format_exc())

    resps = driver.execute_script("return JSON.stringify(window_open_urls)")
    window_open_urls = json.loads(resps)
    for window_open_url in window_open_urls:
        full_window_open_url = urljoin(driver.current_url, window_open_url)
        urls.add(url_to_request(full_window_open_url))

    logging.debug("URLs from extract_urls %s" % str(urls))

    return urls
