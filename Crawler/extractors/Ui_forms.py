
from selenium.webdriver.common.by import By

import logging


import Classes


def extract_ui_forms(driver):
    sources = []
    submits =  []
    ui_forms = []

    toggles = driver.find_elements(By.XPATH,"//input")
    for toggle in toggles:
        try:
            input_type = toggle.get_attribute("type")
            if (not input_type) or input_type == "text":
                in_form = toggle.find_elements(By.XPATH, ".//ancestor::form")
                if not in_form:
                    xpath = driver.execute_script("return getXPath(arguments[0])", toggle)
                    sources.append( {'xpath': xpath, 'value': 'jAEkPotUI'} )
        except:
            logging.warning("UI form error")

    toggles = driver.find_elements(By.XPATH, "//textarea")
    for toggle in toggles:
        try:
            in_form = toggle.find_elements(By.XPATH, ".//ancestor::form")
            if not in_form:
                xpath = driver.execute_script("return getXPath(arguments[0])", toggle)
                sources.append( {'xpath': xpath, 'value': 'jAEkPotUI'} )
        except:
            logging.warning("UI form error")


    if sources:
        buttons = driver.find_elements(By.XPATH, "//button")
        for button in buttons:
            try:
                in_form = button.find_elements(By.XPATH, ".//ancestor::form")
                if not in_form:
                    xpath = driver.execute_script("return getXPath(arguments[0])", button)
                    ui_forms.append( Classes.Ui_form(sources, xpath))
            except:
                logging.warning("UI form error")



    return ui_forms


