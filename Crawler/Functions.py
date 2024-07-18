import logging
import json
import operator
import os
import copy
import traceback

from urllib.parse import urlparse
from selenium.webdriver.common.by import By
from selenium.webdriver.support.select import Select
from selenium.common.exceptions import StaleElementReferenceException, TimeoutException, UnexpectedAlertPresentException, NoSuchFrameException, NoAlertPresentException, ElementNotVisibleException, InvalidElementStateException
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys

import Classes
from extractors.Events import extract_events
from extractors.Forms import extract_forms, parse_form
from extractors.Urls import extract_urls
from extractors.Iframes import extract_iframes



# 通过 Webdriver 向 Chrome 发送 DevTools 命令
def send(driver, cmd, params={}):
    resource = "/session/%s/chromium/send_command_and_get_result" % driver.session_id
    url = driver.command_executor._url + resource # request 的 url

    body = json.dumps({'cmd': cmd, 'params': params}) # request 的请求体

    response = driver.command_executor._request('POST', url, body) # 发送请求
    if "status" in response:
        logging.error(response)


# 通过 Page.addScriptToEvaluateOnNewDocument 命令插入的脚本会在每次新文档（如页面刷新或导航到新页面）加载时自动执行。
def add_script(driver, script):
    send(driver, "Page.addScriptToEvaluteOnNewDocument", {"source": script})



def linkrank(link_edges, visited_list):
    tups = [] # 方便排序
    # 遍历要排序的边
    for edge in link_edges:
        # 注意 提取的是终结点的url
        url = edge.n2.value.url
        purl = urlparse(url)

        queries = len(purl.query.split("&")) # 参数数量
        depth = len(purl.path.split("/")) # 路径深度

        visited = 0
        # 如果已经被访问过了，那就置为1
        if purl.path in visited_list:
            visited = 1

        tups.append( (edge, (visited, depth, queries))) 
    
    tups.sort(key = operator.itemgetter(1)) # 排序关键字的优先级为：是否已访问、路径深度、查询参数数量。 未访问 深度浅 参数少的优先放前面

    return [edge for (edge, _) in tups]


def rec_find_path(graph, edge): # 找到祖辈的一个get就行？
    path = []
    method = edge.value.method
    parent = edge.parent


    if method == "get":
        return path + [edge] # + 是合并列表
    else:
        return rec_find_path(graph, parent) + [edge]
    
# 同源： 相同的协议 相同的主机 相同的端口号
def same_origin(u1, u2):
    par1 = urlparse(u1)
    par2 = urlparse(u2)

    #  比较两个解析后的 URL 的 scheme（协议，如 http 或 https）和 netloc（网络位置，如 example.com:80）
    return ( par1.scheme == par2.scheme
            and par1.netloc == par2.netloc )

def allow_edge(graph, edge): # tocheck 不懂这个函数的核心是做什么
    # 取 crawl_edge
    crawl_edge = edge.value

    if crawl_edge.method == "get":
        to_url = edge.n2.value.url
    elif crawl_edge.method == "form":
        to_url = crawl_edge.method_data.action # tocheck 什么玩意
    elif crawl_edge.method == "iframe":
        to_url = crawl_edge.method.src # tocheck 什么玩意
    elif crawl_edge.method == "event":
        ignore = ["onerror"]
        # 如果事件在忽略列表中，则不允许该边；否则允许。
        return not (crawl_edge.method_data.event in ignore) 
    else:
        return True

    from_url = graph.nodes[1].value.url # 这是最初的url

    # 将上面得到的 to_url 解析一下
    parsed_to_url = urlparse(to_url)
    # scheme 是 URL 的方案部分，例如 http, https, ftp, javascript 等。 对于相对链接，scheme 为空（即没有指定方案），例如 /path/to/resource。这种情况下，认为相对链接通常不会跳出当前网站的域名范围，因此返回 True，表示允许通过。
    if not parsed_to_url.scheme:
        return True
    # javascript: 链接通常不会导航到新页面，而是在当前页面上触发某些交互，例如执行一段 JavaScript 代码。
    if parsed_to_url.scheme == "javascript":
        return True
    so = same_origin(from_url, to_url)
    blacklisted_terms = [] # TODO 需要自行加些东西

    if to_url:
        # 检查 bt 这个子字符串是否存在于 to_url 字符串中
        bl = any([bt in to_url for bt in blacklisted_terms])
    else:
        bl = False

    if so and not bl: # 同源 且 to_url 里面没有黑名单term
        return True
    else:
        return False
    
# 主要用于模糊比较两个表单对象，确定它们是否在 
# action、method 属性以及包含的输入元素上相等。
# 这个函数对于表单填充和提交的自动化测试非常有用，可以帮助确认两个表单是否结构相似，适合进行相同的处理。

def fuzzy_eq(form1, form2):
    if form1.action != form2.action:
        return False
    if form1.method != form2.method:
        return False
    for el1 in form1.inputs.keys():
        if not (el1 in form2.inputs):
            return False
    return True

# Returns None if the string is empty, otherwise just the string
def empty2none(s):
    if not s:
        return None
    else:
        return s
    

# 目的是生成文件路径并在某些情况下动态创建文件，以便在表单填充过程中使用。 tocheck 没怎么看懂

def form_fill_file(filename):
    dirname = os.path.dirname(__file__)
    path = os.path.join(dirname, 'form_files', filename)

    if filename != "jaekpot.jpg":
        path = os.path.join(dirname, 'form_files', 'dynamic', filename)
        dynamic_file = open(path, "w+")
        # Could it be worth to add a file content payload?
        dynamic_file.write(filename)
        dynamic_file.close()

    return path


# 使用 JavaScript 更新网页元素的值。
def update_value_with_js(driver, web_element, new_value):
    try:
        new_value = new_value.replace("'", "\\'")
        driver.execute_script("arguments[0].value = '"+new_value+"'", web_element)
    except Exception as e:
        logging.error(e)
        logging.error(traceback.format_exc())
        logging.error("faild to update with JS " + str(web_element)  )
    

def form_fill(driver, target_form): # tocheck 我好像没搞懂 driver find出的 elements 和 target_form里面的元素的联系 
    # 确保在填form前 没有alert
    try:
        alert = driver.switch_to.alert
        alert.accept()
    except:
        # No alert removed (probably due to there not being any)
        pass

    # 从页面中找 通过 HTML 标签名来查找元素。在这里是 <form> 标签。
    elem = driver.find_elements(By.TAG_NAME, "form")

    for el in elem:
        # 从html元素到对象
        current_form = parse_form(el, driver) # tocheck 这是在解析吗

        submit_buttons = []

        # 如果不匹配则下一个
        if not fuzzy_eq(current_form, target_form):
            continue


        # 从上述遍历的元素中找input元素
        inputs = el.find_elements(By.TAG_NAME, "input")
        
        # 如果inputs 是空的，tocheck 调用插入的JavaScript脚本 去填充 inputs
        if not inputs:
            inputs = []

            resps = driver.execute_script("return get_forms()") # 这里执行的是 一开始插入的 JavaScript脚本
            js_forms = json.loads(resps)

            for js_form in js_forms:
                if js_form['method'] == target_form.method and js_form['action'] == target_form.action:
                    # 如果 js_form 和 target_form匹配
                    for js_el in js_form['elements']:
                        web_el = driver.find_elements(By.XPATH, js_el['xpath'])
                        inputs.append(web_el)
                    break # 从 js_forms 里面找到一个匹配的就可
        
        button = el.find_elements(By.TAG_NAME, "button")
        inputs.extend(button)

        for iel in inputs:
            try:
                iel_type = empty2none(iel.get_attribute("type"))
                iel_name = empty2none(iel.get_attribute("name"))
                iel_value = empty2none(iel.get_attribute("value"))
                # 逐类型 创建 form_iel
                if iel.get_attribute("type") == "radio":
                    form_iel = Classes.Form.RadioElement(
                                                    iel_type,
                                                    iel_name,
                                                    iel_value
                                                    )
                elif iel.get_attribute("type") == "checkbox":
                    form_iel = Classes.Form.CheckboxElement(
                                                     iel_type,
                                                     iel_name,
                                                     iel_value,
                                                     None)
                elif iel.get_attribute("type") == "submit":
                    form_iel = Classes.Form.SubmitElement(
                                                     iel_type,
                                                     iel_name,
                                                     iel_value,
                                                     None)
                else:
                    form_iel = Classes.Form.Element(
                                                     iel_type,
                                                     iel_name,
                                                     iel_value
                                                     )
                # 如果创建的 form_iel 在 target_form的inputs里面，就把对应的input取出，然后基于iel的type进行操作
                if form_iel in target_form.inputs:
                    # tocheck 为什么这里面直接把 i 的override_value 拿过来填充到iel里面了
                    i = target_form.inputs[form_iel]
                    
                    # 处理提交按钮和图像按钮
                    if iel.get_attribute("type") == "submit" or iel.get_attribute("type") == "image":
                        submit_buttons.append( (iel, i) )
                    # 处理文件输入 
                    elif iel.get_attribute("type") == "file":
                        if "/" in i.value:
                            pass
                        else:
                            try:
                                # 模拟用户上传文件路径
                                iel.send_keys( form_fill_file(i.value) ) # send_keys 是 Selenium WebDriver 提供的一个方法，用于向网页元素（如输入框、文本框等）发送键盘输入。这个方法可以模拟用户在键盘上输入字符，从而自动化填写表单。
                            except:
                                pass
                    # 处理单选按钮
                    elif iel.get_attribute("type") == "radio":
                        if i.override_value: # override_value 通常用于在自动化测试或表单填充中覆盖默认的输入值
                            update_value_with_js(driver, iel, i.override_value)
                        if i.click: # 这些 click是在哪设置的呢
                            iel.click()
                    # 处理复选框
                    elif iel.get_attribute("type") == "checkbox":
                        if i.override_value:
                            update_value_with_js(driver, iel, i.override_value)
                        if i.checked and not iel.get_attribute("checked"):
                            iel.click()
                    # 忽略隐藏输入 tocheck 为什么忽略
                    elif iel.get_attribute("type") == "hidden":
                        pass

                    # tocheck 感觉这里两步有问题 只 upate 了 但是有可能没提交
                    # 处理文本、电子邮件和 URL 输入：
                    elif iel.get_attribute("type") in ["text", "email", "url"]:
                        # 执行 JavaScript 移除长度限制属性，以便可以输入超过最大长度的值。
                        if iel.get_attribute("maxlength"):
                            try:
                                driver.execute_script("arguments[0].removeAttribute('maxlength')", iel)
                            except:
                                pass
                        try:
                            # 清除输入字段的当前值
                            iel.clear()
                            # 还是直接输入 i 的 value
                            iel.send_keys(i.value)
                        except: # 如果常规方法失败，使用 driver.execute_script("arguments[0].value = '"+str(i.value)+"'", iel) 通过执行 JavaScript 设置输入字段的值。
                            try:
                                driver.execute_script("arguments[0].value = '"+str(i.value)+"'", iel)
                            except:
                                pass
                    # 处理密码输入：
                    elif iel.get_attribute("type") == "password":
                        try:
                            iel.clear()
                            iel.send_keys(i.value)
                        except:
                            update_value_with_js(driver, iel, i.value)
                    else:
                        pass
                else:
                    pass
            except:
                pass


        # 从上述遍历元素中找 <select>
        selects = el.find_elements(By.TAG_NAME, "select")
        for select in selects:
            form_select = Classes.Form.SelectElement( "select", select.get_attribute("name") )
            if form_select in target_form.inputs: # 熟悉的 类似的判断，如果el中的元素 在 target_form里面存在 
                i = target_form.inputs[form_select]
                selenium_select = Select( select )
                options = selenium_select.options
                if i.override_value and options: # 用对方的值 改自己的值
                    update_value_with_js(driver, options[0], i.override_value)
                else: # 否则，遍历选项并选择匹配 i.selected 的值。尝试点击该选项，如果失败，使用 JavaScript 更新。
                    for option in options:
                        if option.get_attribute("value") == i.selected:
                            try:
                                option.click()
                            except:
                                update_value_with_js(driver, select, i.selected) 
                                # tocheck 后续还需要 类似 click吗
                            break
            else:
                pass

        # 从上述遍历元素中找 <textarea>
        textareas = el.find_elements(By.TAG_NAME, "textarea")
        for ta in textareas:
            form_ta = Classes.Form.Element( ta.get_attribute("type"),
                                            ta.get_attribute("name"),
                                            ta.get_attribute("value") )
            if form_ta in target_form.inputs: # 熟悉的 类似的判断，如果el中的元素 在 target_form里面存在
                i = target_form.inputs[form_ta]
                try:
                    ta.clear()
                    ta.send_keys(i.value)
                except:
                    update_value_with_js(driver, ta, i.value)
            else:
                pass

        # 从上述遍历元素中找 <iframes>
        iframes = el.find_elements(By.TAG_NAME, "iframe")
        for iframe in iframes:
            form_iframe = Classes.Form.Element("iframe", iframe.get_attribute("id"), "")
            if form_iframe in target_form.inputs: # 熟悉的 类似的判断，如果el中的元素 在 target_form里面存在
                i = target_form.inputs[form_iframe]
                try:
                    iframe_id =  i.name
                    driver.switch_to.frame(iframe_id) # 用于在主文档和 <iframe> 之间切换
                    iframe_body = driver.find_element(By.TAG_NAME, "body")
                    if(iframe_body.get_attribute("contenteditable") == "true"):
                        iframe_body.clear()
                        iframe_body.send_keys(i.value)
                    else:
                        pass

                    driver.switch_to.default_content() # 用于在主文档和 <iframe> 之间切换
                except:
                    pass
            else:
                pass


        # submit
        if submit_buttons:
            for submit_button in submit_buttons:
                (selenium_submit, form_submit) = submit_button

                # tocheck 逻辑不是很清楚 再就只有一个break？
                # 如果 form_submit.use 为真，表示这个提交按钮应该被使用。 tocheck 在哪里设置为真呢
                if form_submit.use:
                    try:
                        selenium_submit.click()
                        break
                    except ElementNotVisibleException as e:
                        driver.execute_script("arguments[0].click()", selenium_submit)

                        # Also try submitting the full form, shouldn't be needed
                        try:
                            el.submit()
                        except:
                            pass
                    except:
                        el.submit()

                # Some forms show an alert with a confirmation 处理确认弹窗
                try:
                    alert = driver.switch_to.alert
                    alertText = alert.text
                    alert.accept()
                except:
                    pass
        else:
            el.submit()



        # Check if submission caused an "are you sure" alert
        try:
            alert = driver.switch_to.alert
            alertText = alert.text
            alert.accept()
        except:
            pass
        # End of form fill if everything went well
        return True
    
    return False

#  xpath_row_to_cell 函数的主要作用是将一个指向表格行（<tr>）的 XPath 转换为指向该行中的第一个单元格（<td>）。这是因为直接点击 <tr> 元素通常不会触发事件，而点击 <td> 元素可以触发事件。tocheck
def xpath_row_to_cell(addr):
    # It seems impossible to click (and do other actions)
    # on a <tr> (Table row).
    # Instead, the onclick applies to all cells in the row.
    # Therefore, we pick the first cell.
    parts = addr.split("/")
    if(parts[-1][:2] == "tr"):
        addr += "/td[1]"
    return addr

# execute_event 函数的目的是根据传入的事件类型，在网页上触发相应的事件
def execute_event(driver, do):
    # 将地址转换为适当的 XPath 表达式。
    do.addr = xpath_row_to_cell(do.addr)

    try:
        # 基于event的类型
        # 点击事件： 可见不可见
        if   do.event == "onclick" or do.event == "click":
            web_element =  driver.find_element(By.XPATH,do.addr)
        
            if web_element.is_displayed():
                web_element.click()
            else:
                driver.execute_script("arguments[0].click()", web_element)
        # 双击事件：用actionchains
        elif do.event == "ondblclick" or do.event == "dblclick":
            web_element =  driver.find_element(By.XPATH, do.addr)
            ActionChains(driver).double_click(web_element).perform()
        # 鼠标移出事件：
        elif do.event == "onmouseout":
            driver.find_element(By.XPATH, do.addr).click()
            el = driver.find_element(By.XPATH, do.addr)
            # TODO find first element in body
            body = driver.find_element(By.XPATH, "/html/body")
            ActionChains(driver).move_to_element(el).move_to_element(body).perform()
        # 鼠标悬停事件
        elif do.event == "onmouseover":
            el = driver.find_element(By.XPATH, do.addr)
            ActionChains(driver).move_to_element(el).perform()
        # 鼠标按下事件
        elif  do.event == "onmousedown":
            driver.find_element(By.XPATH, do.addr).click()
        # 鼠标释放事件：
        elif  do.event == "onmouseup":
            el = driver.find_element(By.XPATH, do.addr)
            ActionChains(driver).move_to_element(el).release().perform()
        # 变化事件：
        # tocheck 为什么输入者东西 "jAEkPot"
        elif  do.event == "change" or do.event == "onchange":
            el = driver.find_element(By.XPATH, do.addr)
            if el.tag_name == "select":
                # If need to change a select we try the different
                # options
                opts = el.find_elements(By.TAG_NAME, "option")
                for opt in opts:
                    try:
                        opt.click()
                    except UnexpectedAlertPresentException:
                        alert = driver.switch_to.alert
                        alert.dismiss()
            else:
                # If ot a <select> we try to write
                el = driver.find_element(By.XPATH, do.addr)
                el.clear()
                el.send_keys("jAEkPot")
                el.send_keys(Keys.RETURN)
        # 输入事件：
        elif  do.event == "input" or do.event == "oninput":
            el = driver.find_element(By.XPATH, do.addr)
            el.clear()
            el.send_keys("jAEkPot")
            el.send_keys(Keys.RETURN)
        # 组合开始事件：
        elif  do.event == "compositionstart":
            el = driver.find_element(By.XPATH, do.addr)
            el.clear()
            el.send_keys("jAEkPot")
            el.send_keys(Keys.RETURN)
        # 未处理的事件： tocheck 进一步处理
        else:
            pass
    except:
        pass

def remove_alerts(driver):
    # Try to clean up alerts
    try:
        alert = driver.switch_to.alert
        alert.dismiss()
    except NoAlertPresentException:
        pass

# ui_form_fill 函数的目的是使用 Selenium WebDriver 自动填充和提交一个用户界面表单。
def ui_form_fill(driver, target_form): # 这个form 是边上记录的 所以对应着提交？
    # Ensure we don't have any alerts before filling in form 类似form_fill
    try:
        alert = driver.switch_to.alert
        alert.accept()
    except:
        pass


    for source in target_form.sources:
        # source 是边上的，然后找到对应的driver上的元素，将值填入 tocheck 那怎么有的要填入的值呢 
        web_element =  driver.find_element(By.XPATH, source['xpath'])

        # 同样是去掉长度限制
        if web_element.get_attribute("maxlength"):
            try:
                driver.execute_script("arguments[0].removeAttribute('maxlength')", web_element)
            except:
                pass
        # tocheck 还是不懂 为什么从driver上find的
        input_value = source['value']
        try:
            web_element.clear()
            web_element.send_keys(input_value)
        except:
            try:
                # 类似的 这也是执行JavaScript去赋值？
                # arguments[0] 是一个占位符，用于引用传递给 execute_script 方法的第一个参数。 对应 web_element
                driver.execute_script("arguments[0].value = '"+input_value+"'", web_element)
            except:
                pass


    # 找到表单 提交表单
    submit_element =  driver.find_element(By.XPATH, target_form.submit)
    submit_element.click()

#  enter_iframe 函数的主要目的是找到一个特定的 <iframe> 或 <frame> 元素，并将 Selenium WebDriver 的上下文切换到该框架中。
def enter_iframe(driver, target_frame):
    # 找iframe 并拓展到 Frame tocheck
    elem = driver.find_elements(By.TAG_NAME, "iframe")
    elem.extend( driver.find_elements(By.TAG_NAME, "frame") )

    for el in elem:
        try:
            src = None
            i = None

            if el.get_attribute("src"):
                src = el.get_attribute("src")
            if el.get_attribute("id"):
                i = el.get_attribute("i")

            current_frame = Classes.Iframe(i, src)
            # 还是挺类似的 要从 driver中找到的元素中 找到那个对应target_form的的
            if current_frame == target_frame:
                # 切换 返回
                driver.switch_to.frame(el)
                return True
        except:
            return False
    return False


# Execute the path necessary to reach the state
def find_state(driver, graph, edge): # tocheck find_state是做啥的呢
    path = rec_find_path(graph, edge) # 找到edge的路径
    for edge_in_path in path:
        method = edge_in_path.value.method
        method_data = edge_in_path.value.method_data
        if allow_edge(graph, edge_in_path): # 判断是否还能继续沿着这条边继续爬取
            if method == "get":
                driver.get(edge_in_path.n2.value.url)
            elif method == "form":
                form = method_data
                try:
                    form_fill(driver, form) # 调用 form_fill(driver, form) 函数填充并提交表单 不报错就继续
                except:
                    return False
            elif method == "ui_form":
                ui_form = method_data
                try:
                    ui_form_fill(driver, ui_form) # 调用 ui_form_fill(driver, ui_form) 函数填充并提交 UI 表单 不报错就继续
                except:
                    return False
            elif method == "event":
                event = method_data
                execute_event(driver, event) # 调用 execute_event(driver, event) 函数执行事件
                remove_alerts(driver)
            elif method == "iframe":
                enter_status = enter_iframe(driver, method_data) # 调用 enter_iframe(driver, method_data) 函数进入 iframe。 进入了就继续
                if not enter_status:
                    return False
            elif method == "javascript":
                # The javascript code is stored in the to-node
                # "[11:]" gives everything after "javascript:"
                js_code = edge_in_path.n2.value.url[11:]
                try:
                    driver.execute_script(js_code) # 提取 JavaScript 代码并调用 driver.execute_script(js_code) 执行 不报错就继续
                except:
                    return False
            else:
                pass

    return True


# 函数的主要目标是按照边的定义执行相应的动作，并尝试找到新的网页状态。 to_check
def follow_edge(driver, graph, edge):
    method = edge.value.method
    method_data = edge.value.method_data
    if method == "get":
        driver.get(edge.n2.value.url)
    # 其他的都是调用find_state 那为什么execute_path 里面没有全调用 find_state tocheck
    elif method == "form":
        if not find_state(driver, graph, edge):
            edge.visited = True
            return None
    elif method == "event":
        if not find_state(driver, graph, edge):
            edge.visited = True
            return None
    elif method == "iframe":
        if not find_state(driver, graph, edge):
            edge.visited = True
            return None
    elif method == "javascript":
        if not find_state(driver, graph, edge):
            edge.visited = True
            return None
    elif method == "ui_form":
        if not find_state(driver, graph, edge):
            edge.visited = True
            return None
    else:
        pass
    # Success
    return True


# 计算给定边（edge）在 DOM 树中的深度。具体来说，它通过沿着父节点向上遍历，直到没有父节点或当前边的方法不是 event 为止。
# DOM 深度指的是从网页的根节点（通常是 <html> 元素）到某个特定节点之间经过的层级数量。它表示了一个节点在 DOM 树中的嵌套层次。DOM 深度越大，表示该节点离根节点越远，嵌套层次越多。
# 这里只考虑了 event 通过限制 event 方法的深度，可以防止在处理深度嵌套的事件时陷入无限循环或超出预期的复杂度。这样有助于提高脚本的性能和稳定性。
# “event” 通常指的是用户或浏览器与网页元素交互时触发的事件。这些事件可以包括点击、悬停、表单提交、页面加载等。
def dom_depth(edge):
    depth = 1
    while edge.parent and edge.value.method == "event":
        depth = depth + 1
        edge = edge.parent
    return depth

#  check_edge 函数的目的是根据各种条件决定是否应遵循特定的边（edge）进行下一步操作。这些条件包括同源策略（SOP）、请求次数限制、DOM 深度等
# Check if we should follow edge
# Could be based on SOP, number of reqs, etc.
def check_edge(driver, graph, edge):
    method = edge.value.method
    method_data = edge.value.method_data

    # 根据不同类型
    # TODO use default FALSE/TRUE
    if method == "get":
        if allow_edge(graph, edge): # 同源so 和黑名单bl
            # 限制访问次数 所以 data['urls'] 就是用来限制访问次数的
            purl = urlparse(edge.n2.value.url)
            if not purl.path in graph.data['urls']:
                graph.data['urls'][purl.path] = 0
            graph.data['urls'][purl.path] += 1

            if graph.data['urls'][purl.path] > 120: # 访问次数限制 不能大于120
                return False
            else:
                return True
        else:
            return False
    elif method == "form":
        # 类似限制访问次数 这里限制表单提交次数
        purl = urlparse(method_data.action)
        if not purl.path in graph.data['form_urls']:
            graph.data['form_urls'][purl.path] = 0
        graph.data['form_urls'][purl.path] += 1

        if graph.data['form_urls'][purl.path] > 10: # 表单提交不能大于10
            return False
        else:
            return True
    elif method == "event":
        # 类似的 限制DOM深度 event深度
        if dom_depth(edge) > 10: # Dom深度不能超过10
            return False
        else:
            return True
    else:
        return True
    

#  find_login_form 函数的目的是在给定的网页中查找登录表单 从forms里挑一个form
def find_login_form(driver, graph, early_state=False):
    forms = extract_forms(driver) 
    for form in forms:
        for form_input in form.inputs:
            # 如果输入字段的类型是 password，则认为该表单可能是登录表单。
            if form_input.itype == "password":
                max_input_for_login = 10
                # 登录表单通常不会有太多的输入字段。
                if len(form.inputs) > max_input_for_login:
                    continue
                # We need to make sure that the form is part of the graph
                return form


#  set_standard_values 函数的目的是为表单中的每个输入元素设置标准值。
def set_standard_values(old_form):
    form = copy.deepcopy(old_form)
    first_radio = True

    for form_el in form.inputs.values():
        if form_el.itype == "file":
            form_el.value = "jaekpot.jpg"
        elif form_el.itype == "radio":
            if first_radio:
                form_el.click = True
                first_radio = False
            # else dont change the value
        elif form_el.itype == "checkbox":
            # Just activate all checkboxes
            form_el.checked = True
        elif form_el.itype == "submit" or form_el.itype == "image":
            form_el.use = False
        elif form_el.itype == "select":
            if form_el.options:
                form_el.selected = form_el.options[0]
        elif form_el.itype == "text":
            if form_el.value and form_el.value.isdigit():
                form_el.value = 1
            elif form_el.name == "email":
                form_el.value = "jaekpot@localhost.com"
            else:
                form_el.value = "jAEkPot"
        elif form_el.itype == "textarea":
            form_el.value = "jAEkPot"
        elif form_el.itype == "email":
            form_el.value = "jaekpot@localhost.com"
        elif form_el.itype == "hidden":
            pass
        elif form_el.itype == "password":
            form_el.value = "jAEkPot"
            #form_el.value = "jAEkPot1"
        elif form_el.itype == "number":
            # TODO Look at min/max/step/maxlength to pick valid numbers
            form_el.value = "1"
        elif form_el.itype == "iframe":
            form_el.value = "jAEkPot"
        elif form_el.itype == "button":
            pass
        else:
            form_el.value = "jAEkPot"

    return form



# set_submits 函数的主要目的是处理表单中的提交按钮（包括类型为 submit 和 image 的按钮）。
# 确保每个表单中只有一个提交按钮被激活（即 use 属性被设置为 True）
def set_submits(forms):
    new_forms = set()
    for form in forms:
        submits = set()
        for form_el in form.inputs.values():
            if form_el.itype == "submit" or form_el.itype == "image":
                submits.add(form_el)

        if len(submits) > 1:
            for submit in submits:
                # tocheck 这里add的事上面的form_el
                # 多个按钮 每个创建一个实例 use 一个
                new_form = copy.deepcopy(form)
                for new_form_el in new_form.inputs.values():
                    if new_form_el.itype == "submit" and new_form_el == submit:
                        new_form_el.use = True

                new_forms.add(new_form)
        elif len(submits) == 1:
            # 这里add的是 上面的 form
            submits.pop().use = True
            new_forms.add(form)

    return new_forms


#  set_checkboxes 函数的目的是处理表单中的复选框元素，并生成新的表单集合
def set_checkboxes(forms):
    new_forms = set()
    for form in forms:
        new_form = copy.deepcopy(form)
        # 同样是遍历 checkbox类的输入， tocheck 为什么form 和 new_form都add进去
        for new_form_el in new_form.inputs.values():
            if new_form_el.itype == "checkbox":
                new_form_el.checked = False
                new_forms.add(form)
                new_forms.add(new_form)
    return new_forms


#  set_form_values 函数的目的是为表单设置标准值，并处理提交按钮和复选框等输入元素。
def set_form_values(forms): # tocheck 我怎么感觉传进来的 forms 只有一个元素
    new_forms = set()
    # Set values for forms.
    # Could also create copies of forms to test different values
    for old_form in forms:
        new_forms.add( set_standard_values(old_form) ) # 使用 set_standard_values 函数为每个表单设置标准值

    # Handle submits
    new_forms = set_submits(new_forms) # 调用 set_submits 函数处理新表单集合中的提交按钮。
    new_checkbox_forms = set_checkboxes(new_forms) # 调用 set_checkboxes 函数处理新表单集合中的复选框。
    for checkbox_form in new_checkbox_forms:
        new_forms.add(checkbox_form)

    return new_forms
