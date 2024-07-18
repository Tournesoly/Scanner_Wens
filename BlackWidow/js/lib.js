/*
 * Simulate.js from https://github.com/airportyh/simulate.js
 */
!function() { // IIFE 主要作用是创建一个 Simulate 对象，并定义了它的各种方法，同时确保外界只能调用 Simulate 的方法，而不能直接访问 IIFE 里面定义的内部函数和变量。 
	function extend(dst, src) { // 将源对象src的属性复制到目标对象dst中。
		for ( var key in src)
			dst[key] = src[key]
		return src
	}
	var Simulate = {
		event : function(element, eventName) { // 用于触发常规的HTML事件。
			if (document.createEvent) {
				var evt = document.createEvent("HTMLEvents") // 创建事件
				evt.initEvent(eventName, true, true) // 初始化事件
				element.dispatchEvent(evt) //触发事件
			} else { // 如果浏览器不支持createEvent
				var evt = document.createEventObject() // 这应该还是创建吧
				element.fireEvent('on' + eventName, evt) // 这是触发事件吧
			}
		},
		keyEvent : function(element, type, options) {
			var evt, e = { // 定义一个默认的事件配置对象e
				bubbles : true,
				cancelable : true,
				view : window,
				ctrlKey : false,
				altKey : false,
				shiftKey : false,
				metaKey : false,
				keyCode : 0,
				charCode : 0
			}
			extend(e, options) // 将传入的options扩展到e中。
			if (document.createEvent) {
				try { // 尝试创建KeyEvents事件，
					evt = document.createEvent('KeyEvents')
					evt.initKeyEvent(type, e.bubbles, e.cancelable, e.view,
							e.ctrlKey, e.altKey, e.shiftKey, e.metaKey,
							e.keyCode, e.charCode)
					element.dispatchEvent(evt)
				} catch (err) { // 如果失败则创建常规事件并手动添加键盘事件属性。
					evt = document.createEvent("Events")
					evt.initEvent(type, e.bubbles, e.cancelable)
					extend(evt, {
						view : e.view,
						ctrlKey : e.ctrlKey,
						altKey : e.altKey,
						shiftKey : e.shiftKey,
						metaKey : e.metaKey,
						keyCode : e.keyCode,
						charCode : e.charCode
					})
					element.dispatchEvent(evt)
				}
			} // 使用dispatchEvent触发事件。 什么叫触发事件
		}
	}
	// 分别模拟keypress、keydown和keyup事件。三者流程非常相似
	Simulate.keypress = function(element, chr) {
		var charCode = chr.charCodeAt(0)
		this.keyEvent(element, 'keypress', {
			keyCode : charCode,
			charCode : charCode
		})
	}
	Simulate.keydown = function(element, chr) {
		var charCode = chr.charCodeAt(0)
		this.keyEvent(element, 'keydown', {
			keyCode : charCode,
			charCode : charCode
		})
	}
	Simulate.keyup = function(element, chr) {
		var charCode = chr.charCodeAt(0)
		this.keyEvent(element, 'keyup', {
			keyCode : charCode,
			charCode : charCode
		})
	}
	// 用于模拟change事件。
	Simulate.change = function(element) {
		var evt = document.createEvent("HTMLEvents");
		evt.initEvent("change", false, true);
		element.dispatchEvent(evt);

	}
	//Simulate.click = function(element){
	//	element.click();
	//}
	// 为常见的事件类型批量定义模拟方法。
	var events = ['click','focus', 'blur', 'dblclick', 'input', 'mousedown',
			'mousemove', 'mouseout', 'mouseover', 'mouseup', 'resize',
			'scroll', 'select', 'submit', 'load', 'unload', 'mouseleave' ]
	// 遍历events数组，使用立即执行函数为每个事件类型定义一个方法。
	for (var i = events.length; i--;) {
		var event = events[i]
		Simulate[event] = (function(evt) {
			return function(element) {
				this.event(element, evt) // 调用Simulate.event触发相应事件。
			}
		}(event))
	}
	// 根据不同的执行环境导出Simulate对象。
	// 检查module、window和define对象，分别处理CommonJS、浏览器和AMD模块环境。
	if (typeof module !== 'undefined') {
		module.exports = Simulate
	} else if (typeof window !== 'undefined') {
		window.Simulate = Simulate
	} else if (typeof define !== 'undefined') {
		define(function() {
			return Simulate
		})
	}
}();
/*
 * From down here
 * 
 *Copyright (C) 2015 Constantin Tschuertz
 * 
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * any later version.
 *
 *This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program.  If not, see <http://www.gnu.org/licenses/>.
 *
 */

// Test for send wrapper (TODO)
need_to_wait = false;
// 拦截XMLHttpRequest的open方法，以检测和记录HTTP请求。
// 保存原始的open方法，并替换为自定义方法。
var original = XMLHttpRequest.prototype['open'];
XMLHttpRequest.prototype['open'] = function() {
  // 在自定义方法中，将need_to_wait设置为true，然后调用原始open方法。
  need_to_wait = true;
  return original.apply(this, arguments); // 这里到处可见的arguments是什么
}
// End of test 

// 回调函数包装器 调传入的函数，然后执行原来的函数
function callbackWrap(object, property, argumentIndex, wrapperFactory) {
	// 保存原来的方法
	var original = object[property];
	// 定义新的方法
	object[property] = function() {
		// 先调用 wrapperFactory函数 然后调用原始方法
		wrapperFactory(this, arguments);
		return original.apply(this, arguments);
	}
	return original;
}

var max_waiting_time = 65000
var min_waiting_time = 0

// 计数器包装器 检查时间+调用传入的函数+调用原来的函数
function timingCallbackWrap(object, property, argumentIndex, wrapperFactory) {
	var original = object[property];

	object[property] = function() {
		// 新方法检查等待时间，如果超过max_waiting_time则限制时间。
		if (arguments[1] > max_waiting_time) {
			arguments[1] = max_waiting_time
		}
		wrapperFactory(this, arguments);
		return original.apply(this, arguments);
	}
	return original;
}

// 计时和间隔计时器包装 只调用传入的函数
function callInterceptionWrapper(object, property, argumentIndex,
		wrapperFactory) {
	var original = object[property];
	object[property] = function() {
		wrapperFactory(this, arguments);
		return null;
	}
	return original;
}

// 记录XMLHttpRequest的请求信息。
function XMLHTTPObserverOpen(elem, args) {
	// 创建请求信息对象resp，包含请求的URL和方法。
	resp = {
		"url" : args[1],
		"method" : args[0]
	};
	// 生成一个随机数作为唯一标识符，并赋值给请求对象。
	random_num =  Math.floor((Math.random() * 10000) + 1);
	//console.log("Uniq Id set: " + random_num);
	elem.jaeks_id = random_num;
	//resp = JSON.stringify(resp);
	// 将请求信息记录在timeouts数组中。
	timeouts.push(resp); // 怎么不同类型的东西 都添加到了timeouts里面
	console.log("Observer " + resp);
	//jswrapper.xmlHTTPRequestOpen(resp)
}

// 记录XMLHttpRequest的发送参数
function XMLHTTPObserverSend(elem, args) {
	// 收集所有参数并存储在elems数组中。
	elems = []
	for (i = 0; i < args.length; i++) {
		elems.push(args[i])
	}
	// 创建包含参数的请求信息对象resp。
	resp = {
		"parameters" : elems
	};
	//console.log("Uniq Id: " + elem.jaeks_id);
	resp = JSON.stringify(resp)
  	console.log("Send " + resp);
	//jswrapper.xmlHTTPRequestSend(resp)
}

// 记录窗口打开的URL。
// 将URL添加到window_open_urls数组中。
window_open_urls = []
function openWrapper(elem, args) {
    window_open_urls.push(args[0])
}

// 记录超时函数的信息。
timeouts = Array();
function timeoutWrapper(elem, args) {
	// 使用MD5生成函数ID。
	function_id = MD5(args[0].toString());
	//创建包含函数ID、函数名和时间的对象resp。
	resp = {
		"function_id" : function_id,
		"function_name" : args[0].name,
		"time" : args[1]
	};
	//resp = JSON.stringify(resp)
	// 将记录信息添加到timeouts数组中。
	timeouts.push(resp); // 怎么不同类型的东西 都添加到了timeouts里面
	//jswrapper.timeout(resp)
}

// 记录间隔函数的信息。 没任何后续影响
function intervallWrapper(elem, args) {
	function_id = MD5(args[0].toString());
	resp = {
		"function_id" : function_id,
		"time" : args[1]
	};
	resp = JSON.stringify(resp)
	//jswrapper.intervall(resp)
}

// 获取元素的XPath路径。
function getXPath(element) {
	try {
		var xpath = '';
		// Updated by Benjamin
		if (element.id) { // 如果元素有ID，直接返回基于ID的XPath。
			return '//*[@id="'+element.id+'"]';
		}
		// 
		for (; element && element.nodeType == 1; element = element.parentNode) { // 否则，遍历元素的父节点，构建XPath路径。
			var sibblings = element.parentNode.childNodes; // 当前元素的父节点的所有子节点
			var same_tags = []
			for (var i = 0; i < sibblings.length; i++) { // collecting same
				if (element.tagName === sibblings[i].tagName) { // 找到所有与当前元素标签名相同的兄弟节点
					same_tags[same_tags.length] = sibblings[i]
				}
			}

			var id = same_tags.indexOf(element) + 1; // 当前元素的索引
			id > 1 ? (id = '[' + id + ']') : (id = ''); // 两种形式 [index] 和 空。
			// 拼接路径
			xpath = '/' + element.tagName.toLowerCase() + id + xpath;
		}
		return xpath;
	} catch (e) {
		console.log("Error: " + e)
		return "";
	}
}



added_events = Array(); // 创建一个空数组 added_events，用于存储添加的事件监听器的信息。
// 定义一个包装函数 addEventListenerWrapper，用于拦截和处理元素的 addEventListener 方法。
function addEventListenerWrapper(elem, args) {
	// 提取元素的标签名、ID 和类名，
	// 初始化 dom_address 变量用于存储元素的 XPath 路径。
	tag = elem.tagName
	dom_adress = "";
	id = elem.id;
	html_class = elem.className;
	//console.log("AddEventLIstenerWrapper: " + tag + " - Event: " + args[0] + " ID " + id)
	dom_adress = getXPath(elem);

	if( !dom_adress ) { // 如果XPath为空，使用元素的outerHTML生成一个假ID，进而生成 XPath 路径。
		console.log("No dom_adress, using fake-id")
		elem.id = MD5(elem.outerHTML);
		dom_adress = '//*[@id="'+elem.id+'"]';
	}

	function_id = MD5(args[1].toString())// 使用 MD5 哈希函数生成事件处理函数的唯一标识符 function_id。
	// 创建一个对象 resp，包含事件类型、函数 ID、XPath 路径、元素 ID、标签名和类名等信息。
	resp = {
		"event" : args[0],
		"function_id" : function_id,
		"addr" : dom_adress,
		"id" : id,
		"tag" : tag,
		"class" : html_class
	}
  	added_events.push( resp ) // 将事件信息对象 resp 添加到 added_events 数组中。
	// 特别处理 change 事件，递归处理表单元素的子元素，确保所有相关事件都被记录。
	if (args[0] == "change") {
		// 使用 querySelectorAll 方法查询当前元素 elem 下的所有 input、select 和 option 元素。
		inputs = elem.querySelectorAll("input");
		selects = elem.querySelectorAll("select");
		options = elem.querySelectorAll("option");

		for (i = 0; i < inputs.length; i++) {
			e = inputs[i];
			// 处理类型为 radio 或 checkbox 的元素。
			if (e.getAttribute("type") == "radio"
					|| e.getAttribute("type") == "checkbox") {
				tag = e.tagName
				id = e.id;
				html_class = e.className;
				dom_adress = getXPath(e);
				function_id = "";
				// 生成一个包含事件类型、函数 ID、XPath 路径、元素 ID、标签名和类名的对象 resp。
				resp = {
					"event" : "change",
					"function_id" : function_id,
					"addr" : dom_adress,
					"id" : id,
					"tag" : tag,
					"class" : html_class
				}
				resp = JSON.stringify(resp)
				// 调用 jswrapper.add_eventListener_to_element 方法，将事件信息记录下来。
				jswrapper.add_eventListener_to_element(resp)
			}
		}
		// 类似
		for (i = 0; i < selects.length; i++) {
			s = selects[i];
			tag = s.tagName
			id = s.id;
			html_class = s.className;
			dom_adress = getXPath(s);
			function_id = "";
			resp = {
				"event" : "change",
				"function_id" : function_id,
				"addr" : dom_adress,
				"id" : id,
				"tag" : tag,
				"class" : html_class
			}
			resp = JSON.stringify(resp)
			jswrapper.add_eventListener_to_element(resp)
		}
		// 类似
		for (xx = 0; xx < options.length; xx++) {
			element = options[i]
			tag = element.tagName
			id = element.id;
			html_class = element.className;
			dom_adress = getXPath(element);
			function_id = "";
			resp = {
				"event" : "change",
				"function_id" : function_id,
				"addr" : dom_adress,
				"id" : id,
				"tag" : tag,
				"class" : html_class
			}
			resp = JSON.stringify(resp)
			jswrapper.add_eventListener_to_element(resp)
		}
	}
	// 检查当前元素是否为 TABLE，并且事件类型是否为 click。
    if (tag == "TABLE" && args[0] == "click"){
        candidates = elem.querySelectorAll("button");// 所有button元素
        for( xx = 0; xx < candidates.length; xx++) {
            var element = candidates[xx];
            tag = element.tagName;
            id = element.id;
            html_class = element.className;
            dom_adress = getXPath(element);
            function_id = "";
            resp = {// 生成一个包含事件类型、函数 ID、XPath 路径、元素 ID、标签名和类名的对象 resp。
                "event": "click",
                "function_id": function_id,
                "addr": dom_adress,
                "id": id,
                "tag": tag,
                "class": html_class
            };
            //resp = JSON.stringify(resp);
            added_events.push( resp )
            //console.log("Hello " + resp)
            //console.log(element.click)
            //jswrapper.add_eventListener_to_element(resp);
        };
    }
}

// 定义一个包装函数 bodyAddEventListenerWrapper，用于拦截和处理 body 元素的 addEventListener 方法。
function bodyAddEventListenerWrapper(elem, args) {
	tag = "body"
	dom_adress = "";
	id = elem.id;
	html_class = elem.className;
	function_id = MD5(args[1].toString())
	dom_adress = "/html/body"
	// 创建一个对象 resp，包含事件的相关信息
	resp = {
		"event" : args[0],
		"function_id" : function_id,
		"addr" : dom_adress,
		"id" : id,
		"tag" : tag,
		"class" : html_class
	}
	resp = JSON.stringify(resp)
  console.log(resp)
  //jswrapper.add_eventListener_to_element(resp)

}

