from urllib.parse import urlparse
from selenium.webdriver.common.by import By

import random
import string
import time

from Functions import *
from extractors.Events import extract_events
from extractors.Forms import extract_forms, parse_form
from extractors.Urls import extract_urls
from extractors.Iframes import extract_iframes
from extractors.Ui_forms import extract_ui_forms

class Request:
    def __init__(self, url, method):
        self.url = url
        self.method = method

class Graph:
    def __init__(self):
        self.nodes = []
        self.edges = []

        self.data = {} # 杂货铺？ 存一些需要的数据
    
    class Node:
        def __init__(self, value):
            self.value = value
            self.visited = False

    class Edge:
        def __init__(self, n1, n2, value, parent):
            self.n1 = n1
            self.n2 = n2
            self.value = value
            self.parent = parent
            self.visited = False


    # 向图中加结点
    def add(self, value):
        node = self.Node(value)
        if not node in self.nodes:
            self.nodes.append(node)
    def connect(self, v1, v2, value, parent=None):
        n1 = self.Node(v1)
        n2 = self.Node(v2)
        edge = self.Edge(n1, n2, value, parent)

        if ( n1 in self.nodes and
                n2 in self.nodes and
                not edge in self.edges ):
            self.edges.append(edge)

    def visit_node(self, value):
        node = self.Node(value)
        if node in self.nodes:
            target = self.nodes[self.nodes.index(node)]
            target.visited = True
            return True
        return False
    
    def visit_edge(self, edge):
        if edge in self.edges:
            target = self.edges[self.edges.index(edge)]
            target.visited = True
            return True
        return False

    def unvisit_edge(self, edge):
        if(edge in self.edges):
            target = self.edges[self.edges.index(edge)]
            target.visited = False
            return True
        return False

class Form:
    def __init__(self):
        self.action = None
        self.method = None
        self.inputs = {}

    # tocheck 各种变量的含义
    class Element:
        def __init__(self, itype, name, value):
            self.itype =  itype
            self.name  =  name
            self.value =  value



    # tocheck 各种变量的含义
    class SubmitElement:
        def __init__(self, itype, name, value, use):
            self.itype =  itype
            self.name  =  name
            self.value =  value
            # If many submit button are available, one must be picked.
            self.use   =  use



    # tocheck 各种变量的含义
    class RadioElement:
        def __init__(self, itype, name, value):
            self.itype   = itype
            self.name    = name
            self.value   = value
            # Click is used when filling out the form
            self.click   = False
            # User for fuzzing
            self.override_value = ""



    # tocheck 各种变量的含义
    class SelectElement:
        def __init__(self, itype, name):
            self.itype     = itype
            self.name      = name
            self.options   = []
            self.selected  = None
            self.override_value = ""



    # tocheck 各种变量的含义
    class CheckboxElement:
        def __init__(self, itype, name, value, checked):
            self.itype   = itype
            self.name    = name
            self.value   = value
            self.checked = checked
            self.override_value = ""



class Iframe:
    def __init__(self, i, src):
        self.id = i
        self.src = src


    

class Crawler:
    def __init__(self, driver, url):
        self.driver = driver
        self.url = url

        self.graph = Graph()

        
        # 优化：连续执行多个事件而不重新加载页面。
        self.events_in_row = 0
        self.max_events_in_row = 15

        # start with gets 不懂
        self.early_gets = 0
        self.max_early_gets = 100

        # 不要对同一个表单攻击过多次
        # 字典的键是表单的哈希值（hash），值是该表单已经被攻击的次数
        self.attacked_forms = {}

        # tocheck 为什么又有 payload 又有 tracker

        # Used to track injections. Each injection will have unique key. 用于记录插入的payload？
        self.attack_lookup_table = {}

        # input / output graph 用于记录插入的tracker？
        self.io_graph = {}


    def start(self):
        # 根结点
        self.root_req = Request("ROOTREQ", "get")
        self.graph.add(self.root_req)
        # url结点
        req = Request(self.url, "get")
        self.graph.add(req)

        # 将两个结点相连
        self.graph.connect(self.root_req, req, CrawlEdge("get", None, None)) # tocheck 为什么是 get none none


        # 这一段应该是非debug模式下才执行的
        # 分解url
        purl = urlparse(self.url)
        if purl.path:
            path_builder = ""
            for d in purl.path.split("/")[: -1]:
                if d:
                    path_builder += d + "/"
                    temp_url = purl._replace(path = path_builder)
                    req = Request(temp_url.geturl(), "get")
                    self.graph.add(req)
                    self.graph.connect(self.root_req, req, CrawlEdge("get", None, None))# tocheck 为什么每一个都要和root链接起来


        self.graph.data['urls'] = {}
        self.graph.data['form_urls'] = {}
        # open("run.flag", "w+").write("1")
        # open("queue.txt", "w+").write("")
        # open("command.txt", "w+").write("")

        random.seed( 6 ) # chosen by fair dice roll

        still_work = True
        while still_work:
            try:
                # 调试信息

                try:
                    still_work = self.rec_crawl()
                except Exception as e:
                    print(e)
            except KeyboardInterrupt:
                print("CTRL-C, abort mission")
        
        print("Done crawling, ready to attack")
        self.attack()


    def get_payloads(self):
        # %RAND 会在后续被替代，用于track
        alert_text = "%RAND"
        xss_payloads = ["<script>xss("+alert_text+")</script>",
                        "\"'><script>xss("+alert_text+")</script>",
                        '<img src="x" onerror="xss('+alert_text+')">',
                        '<a href="" jaekpot-attribute="'+alert_text+'">jaekpot</a>',
                        'x" jaekpot-attribute="'+alert_text+'" fix=" ',
                        'x" onerror="xss('+alert_text+')"',
                        "</title></option><script>xss("+alert_text+")</script>",
                        ] # 7元素数组？
        
        return xss_payloads
    
    def arm_payload(self, payload_template):
        lookup_id = str(random.randint(1, 100000000))
        payload = payload_template.replace("RAND", lookup_id)

        return (lookup_id, payload)
    
    def use_payload(self, lookup_id, tuple_with_payload):
        # tuple is (form, parameter, payload)
        self.attack_lookup_table[str(lookup_id)] = {
            "injected": tuple_with_payload,
            "reflected": set()
        }

    def fix_form(self, form, payload_template, safe_attack):
        # 遍历表单中的每个输入参数，如果存在类型在 only_aggressive 列表中的输入，设置 need_aggressive 为 True 并跳出循环。tocheck 所以有什么用呢
        only_aggressive = ["hidden", "radio", "checkbox", "select", "file"]
        need_aggressive = False
        for parameter in form.inputs: # 应该是 只要是form类型，就会有inputs这个属性
            if parameter.itype in only_aggressive:
                need_aggressive = True
                break

        # 遍历每个输入
        for parameter in form.inputs:
            # 对每一个参数 生成一个唯一负载。 将模版中的 变量 替换为真实的值
            (lookup_id, payload) = self.arm_payload(payload_template) 
            # 安全攻击模式 针对的parameter类型少
            if safe_attack:
                if parameter.itype in ["text", "textarea", "password", "email"]:
                    # 将 表单 该参数的 input值改为 上述负载
                    form.inputs[parameter].value = payload
                    # 将这次注入添加到爬虫的 attack_lookup_table里面
                    self.use_payload(lookup_id, (form, parameter, payload))
                else:
                    # 忽略
                    pass
            # 激进攻击模式 且 激进参数为True 则针对的parameter的参数要多一些
            elif need_aggressive:
                if parameter.itype in ["text", "textarea", "password", "email", "hidden"]:
                    form.inputs[parameter].value = payload
                    self.use_payload(lookup_id, (form, parameter, payload))
                elif parameter.itype in ["radio", "checkbox", "select"]:
                    # 将form 中 parameter对应的input的override_value 置为负载
                    form.inputs[parameter].value = payload
                    self.use_payload(lookup_id, (form, parameter, payload))
                elif parameter.itype == "file":
                    # file 类型 用 file的template
                    file_payload_template = "<img src=x onerror=xss(%RAND)>"
                    (lookup_id, payload) = self.arm_payload(file_payload_template)

                    form.input[parameter].value = payload
                    self.use_payload(lookup_id, (form, parameter, payload))
        # 填充好之后 返回表单
        return form

    # 如果找到了相应的 lookup_id，它会将当前的 URL 和位置添加到 attack_lookup_table 中对应条目的 "reflected" 集合中；
    def reflected_payload(self, lookup_id, edge):
        if str(lookup_id) in self.attack_lookup_table:
            self.attack_lookup_table[str(lookup_id)]["reflected"].add((self.driver.current_url, edge))
        

    def inspect_attack(self, edge):
        successful_xss = set()

        # 使用 XPath 查找页面中所有带有 jaekpot-attribute 属性的元素。感觉是和注入的负载有关 但是似乎只能检查那后几种
        attribute_injects = self.driver.find_elements(By.XPATH, "//*[@jaekpot-attribute]")
        # 遍历这些元素
        for attribute in attribute_injects:
            lookup_id = attribute.get_attribute("jaekpot-attribute")
            successful_xss.add(lookup_id)
            # 找到了汇 修改attack_lookup_table
            self.reflected_payload(lookup_id, edge)

        xsses_json = self.driver.execute_script("return JSON.stringfy(xss_array)") # 该数组中包含所有成功注入的 lookup_id。但是还不清楚哪里会写入xss_array 这个xss_array不是个全局吗，不会有影响吗，页A也能看到页B的

        lookup_ids = json.loads(xsses_json)

        for lookup_id in lookup_ids:
            successful_xss.add(lookup_id)
            self.reflected_payload(lookup_id, edge)

        return successful_xss


    def execute_path(self, driver, path): # 执行 path emmm
        graph = self.graph

        # 遍历 path 中的边
        for edge in path:
            method = edge.value.method
            method_data = edge.value.method_data

            # 针对 method 分情况讨论
            if method == "get":
                # 如果allow 则导航至对应网页 然后inspect tocheck 但是为什么要 allow 才 get+inspect呢
                if allow_edge(graph, edge):
                    driver.get(edge.n2.value.url)
                    self.inspect_attack(edge)
                else:
                    # not allow
                    return False

            elif method == "form":
                form = method_data
                try:
                    # form 是填充表单 
                    # 检测
                    fill_result = form_fill(driver, form)
                    self.inspect_attack(edge)
                    if not fill_result: # tocheck 为什么不先 if 然后再inspect呢
                        return False
                except:
                    return False
            elif method == "event":
                event = method_data
                # event 是执行事件 消除警告窗 
                # 检查攻击
                execute_event(event)
                remove_alerts(driver)
                self.inspect_attack(edge)
            elif method == "iframe":
                # iframe 是 find_state
                if not find_state(driver, graph, edge):
                    return False
                self.inspect_attack(edge)
            elif method == "javascript":
                # JavaScript脚本存在了 to-node 上
                # "[11:]" 对应 "javascript:" 之后的数据
                js_code = edge.n2.value.url[11:]
                try:
                    driver.excute_script(js_code)
                    self.inspect_attack(edge)
                except:
                    return False
                
        return True


    def path_attack_form(self, driver, tar_edge, check_edge=None):
        successful_xss = set()

        graph = self.graph
        path = rec_find_path(graph, tar_edge)# 找到从祖辈第一个get到该 结点/边 的路径

        forms = []
        # 将这条路径上的所有的`表单`都找出来
        for edge in path:
            if edge.value.method == "form":
                forms.append(edge.value.method_data)

        # 安全修复表单并注入负载
        payloads = self.get_payloads()
        for payload_template in payloads:
            for form in forms:
                form = self.fix_form(form, payload_template, True)

            # 执行？ tocheck 不是很清楚是做啥的 应该是针对每一个负载模板，执行path上的各种事件？        
            execute_result = self.execute_path(driver, path)
            if not execute_result:
                return False
            
            # tocheck 不懂这个follow_edge是用来做什么的
            if check_edge:
                follow_edge(driver, graph, check_edge)

            inspect_result = self.inspect_attack(tar_edge)
            if inspect_result:
                successful_xss = successful_xss.union(inspect_result)  # 合并 inspect_result 中的元素到 successful_xss
                return successful_xss 
            
    
        # 激进修复表单并注入负载
        payloads = self.get_payloads()
        for payload_template in payloads:
            for form in forms:
                form = self.fix_form(form, payload_template, False)

            # 感觉是和上面类似的
            execute_result = self.execute_path(driver, path)
            if not execute_result:
                return False
            
            if check_edge:
                follow_edge(driver, graph, check_edge)

            inspect_result = self.inspect_attack(tar_edge)
            if inspect_result:
                successful_xss = successful_xss.union(inspect_result)  # 合并 inspect_result 中的元素到 successful_xss
                break

        #如果没有执行失败过，也没有检查成功过
        return successful_xss

    def attack_ui_form(self, driver, tar_edge, check_edge=None):
        # 不像上面path attack 针对整个路径上的form，这里只针对这条边的ui_form
        successful_xss = set()

        graph = self.graph

        payloads  = self.get_payloads()
        for payload_template in payloads:
            (lookup_id, payload) = self.arm_payload(payload_template)

            ui_form = tar_edge.value.method.data

            self.use_payload(lookup_id, (tar_edge, ui_form, payload))

            # tochekc 又是follow_edge
            follow_edge(driver, self.graph, tar_edge)

            try:
                # 遍历表单的所有源，将负载值注入到每个源中。
                for source in ui_form.sources:
                    source['value'] = payload
                
                # 填充并提交表单。
                ui_form_fill(driver, ui_form)
            except:
                pass

            # 类似的 又是inspect
            inspect_result = self.inspect_attack(tar_edge)
            if inspect_result:
                successful_xss = successful_xss.union(inspect_result)
                break
        
        return successful_xss

    # 追踪器字符串由8个随机的小写字母组成。
    def get_tracker(self):
        letters = string.ascii_lowercase
        return ''.join(random.choice(letters) for i in range(8))
    
    # 记录一个特定的追踪器字符串（tracker）及其相关的注入向量和反射信息。 到io_graph
    def use_tracker(self, tracker, vector_with_payload): # vector_with_load 是 (form_edge,parameter,tracker)
        self.io_graph[tracker] = {"injected": vector_with_payload,
                                  "reflected": set()}
        

    # 检查当前页面的文本内容，寻找之前注入的追踪器字符串，以确定这些追踪器是否被反射回了页面中。
    def inspect_tracker(self, edge):
        try:
            body_text = self.driver.find_element(By.TAG_NAME, "body").text

            # 遍历 io_graph 中记录的 tracker
            for tracker in self.io_graph:
                if tracker in body_text:
                    # 这条边里有，将这条边加进去 加边还是加点 tocheck 有点乱
                    self.io_graph[tracker]['reflected'].add(edge)

                    # 这个prev_edge 代表什么呢 tocheck
                    prev_edge = self.io_graph[tracker]['injected'][0]
                    # 不懂这里的逻辑 tocheck
                    attackable =  prev_edge.value.method_data.attackable() # 可能是一开始插入的脚本进行赋值？
                    if attackable:
                        self.path_attack_form(self.driver, prev_edge, edge)
        except:
            pass



    # 注入追踪器（tracker）到表单字段中，并执行相关路径以检测跨站脚本（XSS）漏洞。
    def track_form(self, driver, edge):


        graph = self.graph
        path = rec_find_path(graph, edge)

        # 找到所有的 form边
        form_edges = []
        for edge in path:
            if edge.value.method=="form":
                form_edges.append(edge)

        for form_edge in form_edges:
            form = form_edge.value.method_data
            tracker = self.get_tracker()
            for parameter in form.inputs:
                # List all injectable input types text, textarea, etc.
                if parameter.itype == "text" or parameter.itype == "textarea":
                # 如果输入类型是 text 或 textarea，将追踪器作为该参数对应的值。
                    # Arm the payload
                    form.inputs[parameter].value = tracker
                    self.use_tracker(tracker, (form_edge,parameter,tracker))

        # 执行之后检测
        self.execute_path(driver, path)

        self.inspect_tracker(edge)


    def next_unvisited_edge(self, driver, graph):
        # 从queue文件中提取用户提供的url
        user_url = open("queue.txt", "r").read()
        if user_url:
            # 暂时先不管
            pass
        
        # 先拿出iframe
        list_to_use = [edge for edge in self.graph.edges if edge.value.method == "iframe" and edge.visited == False]

        # 同样的应该是在非debug模式下，优先处理早期的 get 请求
        if True:
            if self.early_gets < self.max_early_gets: # tocheck 这两个参数不是很懂，感觉是用来解决无限爬取的
                list_to_use = [edge for edge in self.graph.edges if edge.value.method == "gets" and edge.visited == False]

                # 对边（链接）进行排序
                list_to_use = linkrank(list_to_use, graph.data['urls'])

                if list_to_use:
                    self.early_gets += 1
                else:
                    pass
            if self.early_gets == self.max_early_gets:# tocheck 如果相等就重置
                # 边都 unvisit
                for edge in self.graph.edges:
                    graph.unvisit_edge(edge)
                
                graph.data['urls'] = {}
                graph.data['form_urls'] = {}
                self.early_gets += 1
            
        # tocheck 无可用边 且 data 里面有 prev_edge 这个操作好像只是为了变化 然后再选next_unvisited边
        if not list_to_use and 'prev_edge' in graph.data:
            # 判断 prev_edge 的类型
            prev_edge = graph.data['prev_edge']

            # 如果是表单
            if prev_edge.value.method == "form":
                # 取form
                prev_form = prev_edge.value.method_data
                # 如果这个form没有被攻击过
                if not (prev_form in self.attacked_forms):
                    # 尝试在路径中的表单行注入恶意负载 tocheck 为什么爬虫里面会有攻击
                    self.path_attack_form(driver, prev_edge)

                    # tocheck 怎么又判断一次
                    if not prev_form in self.attacked_forms:
                        self.attacked_forms[prev_form] = 0
                    self.attacked_forms[prev_form] += 1

                    # 在路径的表单中注入追踪器检查表单中存在的潜在漏洞 tocheck 为什么爬虫里面会有攻击
                    self.track_form(driver, prev_edge)
                else: # Form already done
                    pass
            # 如果是 ui_form 可能是指用户界面的表单
            elif prev_edge.value.method == "ui_form":
                # 疑似尝试在路径的用户表单中注入恶意负载 tocheck 为什么爬虫里面会有攻击
                self.attack_ui_form(driver, prev_edge)
            else:
                self.events_in_row = 0 # tocheck 这是个什么变量

        # data 没有 prev_edge 但是没有可用边 则随机选择不同类型的边
        if not list_to_use:
            random_int = random.randint(0,100)
            if not list_to_use:
                if random_int >= 0 and random_int < 50: # [0 50) form
                    list_to_use = [edge for edge in graph.edges if edge.value.method == "form" and edge.visited == False]
                elif random_int >= 50 and random_int < 80: # [50, 80) get
                    list_to_use = [edge for edge in graph.edges if edge.value.method == "get" and edge.visited == False]
                    list_to_use = linkrank(list_to_use, graph.data['urls'])
                else: # [80, 100) event 先click 没有再其他event
                    list_to_use = [edge for edge in graph.edges if edge.value.method == "event" and ("click" in edge.value.method_data.event) and edge.visited == False]
                    if not list_to_use:
                        list_to_use = [edge for edge in graph.edges if edge.value.method == "event" and edge.visited == False]

        # 经过上述操作之后 仍然没有可用边 尝试退回处理GET
        if not list_to_use:
            list_to_use = [edge for edge in graph.edges if edge.value.method == "get" and edge.visited == False]
            # 熟悉的排序
            list_to_use = linkrank(list_to_use, graph.data['urls'])

        # 之后遍历得到的 list_to_use 里面的边 这里就有可能return了
        for edge in list_to_use:
            if edge.visited == False:
                # 这个主要是看有米有超限制次数 超过就置为已访问 tocheck 为什么这种情况下置为已访问
                if not check_edge(driver, graph, edge):
                    edge.visited = True
                else:
                    # 按照边的定义执行相应的动作，并尝试找到新的网页状态。
                    successful = follow_edge(driver, graph, edge)
                    if successful:
                        return edge
                    
        # 如果在上面的遍历中没有return 则遍历所有边
        for edge in graph.edges:
            if edge.visited == False:
                # 这个主要是看有米有超限制次数 超过就置为已访问 tocheck 为什么这种情况下置为已访问
                if not check_edge(driver, graph, edge):
                    edge.visited = True
                else:
                    successful = follow_edge(driver, graph, edge)
                    if successful:
                        return edge
        # 最后还有一次判断，判断是否还处于early explorer mode，如果是就关闭，然后再自调用一次 to check 什么是 early explorer mode
        if self.early_gets < self.max_early_gets:
            self.early_gets = self.max_early_gets
            return self.next_unvisited_edge(driver, graph)
        
        # 最后啥也没有返回空
        return None

    def load_page(self, driver, graph):
        edge = self.next_unvisited_edge(driver, graph)
        # 如果 next_unvisited_edge 不存在 直接返回
        if not edge:
            return None
        
        graph.data['prev_edge'] = edge
        request = edge.n2.value # node 的 value 确实是request

        return (edge, request)

    def rec_crawl(self):
        driver = self.driver
        graph = self.graph

        todo = self.load_page(driver, graph)

        if not todo:
            return False

        # 解析出 edge 和 request
        (edge, request) = todo
        graph.visit_node(request)
        graph.visit_edge(edge)


        # 如果next边是get类型
        if edge.value.method == "get":
            for e in graph.edges:
                # 将指向同一状态的 get边置为已访问
                if (edge.n2 == e.n2) and (edge != e) and (e.value.method == "get"):
                    graph.visit_edge(e)

        # Wait if needed 处理等待
        try:
            # tocheck 为什么可以问 need_to_wait这个变量
            wait_json = driver.execute_script("return JSON.stringify(need_to_wait)") # need_to_wait 疑似是一个bool值
            wait = json.loads(wait_json)
            if wait:
                time.sleep(1)
        except UnexpectedAlertPresentException:
            alert = driver.switch_to.alert
            alert.dismiss()

            # Check if double check is needed...
            try:
                wait_json = driver.execute_script("return JSON.stringify(need_to_wait)")
                wait = json.loads(wait_json)
                if wait:
                    time.sleep(1)
            except:
                pass
        except:
            pass

        # Timeouts 处理超时
        try:
            resps = driver.execute_script("return JSON.stringify(timeouts)")
            todo = json.loads(resps)
            for t in todo:
                try:
                    if t['function_name']:
                        driver.execute_script(t['function_name'] + "()")
                except:
                    pass
        except:
            pass


        # 处理登录表单
        early_state = self.early_gets < self.max_early_gets
        login_form = find_login_form(driver, graph, early_state)

        if login_form:
            new_form = set_form_values(set([login_form])).pop()
            try:
                # 这里应该是 上面填完登录表单后 执行表单？
                form_fill(driver, new_form)
            except:
                pass

        
        # Extract urls, forms, elements, iframe etc
        reqs = extract_urls(driver)
        forms = extract_forms(driver)
        forms = set_form_values(forms) # 赋值在这里
        ui_forms = extract_ui_forms(driver)
        events = extract_events(driver)
        iframes = extract_iframes(driver)

        # Check if we need to wait for asynch 检查是否需要等待
        try:
            wait_json = driver.execute_script("return JSON.stringify(need_to_wait)")
        except UnexpectedAlertPresentException:
            alert = driver.switch_to.alert
            alert.dismiss()
        wait_json = driver.execute_script("return JSON.stringify(need_to_wait)")
        wait = json.loads(wait_json)
        if wait:
            time.sleep(1)

        # Add findings to the graph 将新发现的如 URL、表单等添加到图中
        # 我推测是 当前边的n2（下一个结点）  到下下个结点
        current_cookies = driver.get_cookies() # tocheck 不懂这个cookies有什么用

        for req in reqs:
            new_edge = graph.create_edge(request, req, CrawlEdge(req.method, None, current_cookies), edge )
            if allow_edge(graph, new_edge):
                graph.add(req)
                graph.connect(request, req, CrawlEdge(req.method, None, current_cookies), edge )

        for form in forms:
            req = Request(form.action, form.method)
            new_edge = graph.create_edge( request, req, CrawlEdge("form", form, current_cookies), edge )
            if allow_edge(graph, new_edge):
                graph.add(req)
                graph.connect(request, req, CrawlEdge("form", form, current_cookies), edge )


        for event in events:
            req = Request(request.url, "event")
            new_edge = graph.create_edge( request, req, CrawlEdge("event", event, current_cookies), edge )
            if allow_edge(graph, new_edge):
                graph.add(req)
                graph.connect(request, req, CrawlEdge("event", event, current_cookies), edge )


        for iframe in iframes:
            req = Request(iframe.src, "iframe")
            new_edge = graph.create_edge( request, req, CrawlEdge("iframe", iframe, current_cookies), edge )
            if allow_edge(graph, new_edge):
                graph.add(req)
                graph.connect(request, req, CrawlEdge("iframe", iframe, current_cookies), edge )


        for ui_form in ui_forms:
            req = Request(driver.current_url, "ui_form")
            new_edge = graph.create_edge( request, req, CrawlEdge("ui_form", ui_form, current_cookies), edge )
            if allow_edge(graph, new_edge):
                graph.add(req)
                graph.connect(request, req, CrawlEdge("ui_form", ui_form, current_cookies), edge )


        # Try to clean up alerts
        try:
            alert = driver.switch_to.alert
            alert.dismiss()
        except NoAlertPresentException:
            pass

        # Check for successful attacks
        time.sleep(0.1)
        self.inspect_attack(edge)
        self.inspect_tracker(edge)

        # if "3" in open("run.flag", "r").read():
        #     logging.info("Run set to 3, pause each step")
        #     input("Crawler in stepping mode, press enter to continue. EDIT run.flag to run")

        # # Check command
        # found_command = False
        # if "get_graph" in open("command.txt", "r").read():
        #     f = open("graph.txt", "w+")
        #     f.write(str(self.graph))
        #     f.close()
        #     found_command = True
        # # Clear commad
        # if found_command:
        #     open("command.txt", "w+").write("")

        return True


class CrawlEdge:
    def __init__(self, method, method_data, cookies):
        self.method = method
        self.method_data = method_data
        self.cookies = cookies

