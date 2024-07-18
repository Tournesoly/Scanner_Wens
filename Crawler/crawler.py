import argparse
from selenium import webdriver
from selenium.webdriver.remote.webdriver import WebDriver


from Classes import *

# 处理命令行参数 1. --url 设置网址
parser = argparse.ArgumentParser(description='This is a Crawler based on paper BlackWidow')
parser.add_argument("--url", help="The url to crawl")
args = parser.parse_args() # 提取出参数对象？


# 拓展webdriver类，添加add_script，用于在网页插入JavaScript脚本
WebDriver.add_script = add_script

#配一下Chrome Webdriver 实例的 option
chrome_options = webdriver.ChromeOptions()

# 禁用Chrome浏览器的同源策略（Same-Origin Policy）
chrome_options.add_argument("--disable-web-security")

# 禁用Chrome浏览器的XSS审核器（XSS Auditor）
chrome_options.add_argument("--disable-xss-auditor")

# 在没有显示环境中运行时，使用 --headless 参数。
chrome_options.add_argument("--headless")

# launch Chrome
driver = webdriver.Chrome(options= chrome_options)

# 插入的JavaScript脚本：
# ## JS libraries from JaK crawler, with minor improvements
# driver.add_script( open("js/lib.js", "r").read() )
# driver.add_script( open("js/property_obs.js", "r").read() )
# driver.add_script( open("js/md5.js", "r").read() )
# driver.add_script( open("js/addeventlistener_wrapper.js", "r").read() )
# driver.add_script( open("js/timing_wrapper.js", "r").read() )
# driver.add_script( open("js/window_wrapper.js", "r").read() )
# # Black Widow additions
# driver.add_script( open("js/forms.js", "r").read() )
# driver.add_script( open("js/xss_xhr.js", "r").read() )
# driver.add_script( open("js/remove_alerts.js", "r").read() )


# 启动爬虫
url = args.url
if url:
    Crawler(driver, url).start()
else:
    print("Please use --url")