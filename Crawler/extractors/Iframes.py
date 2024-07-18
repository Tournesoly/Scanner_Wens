
from selenium.webdriver.common.by import By
from selenium.common.exceptions import StaleElementReferenceException

import traceback

import Classes


def extract_iframes(driver):
    # Search for <iframe>
    iframes = set()
    elem = driver.find_elements(By.TAG_NAME, "iframe")
    for el in elem:
        try:
            src = None
            i = None

            if el.get_attribute("src"):
                src = el.get_attribute("src")
            if el.get_attribute("id"):
                i = el.get_attribute("i")

            iframes.add( Classes.Iframe(i, src) )

        except StaleElementReferenceException as e:
            print("Stale pasta in from action")
        except:
            print("Failed to write element")
            print(traceback.format_exc())


    # Search for <frame>
    elem = driver.find_elements(By.TAG_NAME, "frame")
    for el in elem:
        try:
            src = None
            i = None

            if el.get_attribute("src"):
                src = el.get_attribute("src")
            if el.get_attribute("id"):
                i = el.get_attribute("i")

            iframes.add( Classes.Iframe(i, src) )

        except StaleElementReferenceException as e:
            print("Stale pasta in from action")
        except:
            print("Failed to write element")
            print(traceback.format_exc())

    
    return iframes
 
