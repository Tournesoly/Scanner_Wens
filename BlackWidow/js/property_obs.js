/*
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
 */


function catch_properties(){// 该函数的目的是捕捉页面上所有元素的事件处理函数。

  resps = [] // 用于存储所有捕获到的事件信息的数组。
  var elems = document.getElementsByTagName('*') // 获取页面上的所有元素。
  // console.log(elems.length + " elems found...")
  for (my_counter_i = 0; my_counter_i < elems.length; my_counter_i++) {
    events = [] // 存储当前元素的事件处理函数。
    tag = elems[my_counter_i].tagName // 当前元素的标签名
    dom_address = "" // 当前元素的 XPATH路径
    id = elems[my_counter_i].id // 当前元素的ID
    // 检查当前元素是否定义了某些事件处理函数，如果定义了，将这些事件处理函数的信息（事件类型和函数）添加到 events 数组中。
    if (elems[my_counter_i].onclick != null) {
      events.push({"method": "onclick", "func": elems[my_counter_i].onclick})
    }
    if (elems[my_counter_i].onmouseover != null) {
      events.push({"method": "onmouseover", "func": elems[my_counter_i].onmouseover})
    }
    if (elems[my_counter_i].onabort != null) {
      events.push({"method": "onabort", "func": elems[my_counter_i].onabort})
    }
    if (elems[my_counter_i].onblur != null) {
      events.push({"method": "onblur", "func": elems[my_counter_i].onblur})
    }
    if (elems[my_counter_i].onchange != null) {
      events.push({"method": "onchange", "func": elems[my_counter_i].onchange})
    }
    if (elems[my_counter_i].oninput != null) {
      events.push({"method": "oninput", "func": elems[my_counter_i].oninput})
    }
    if (elems[my_counter_i].ondblclick != null) {
      events.push({"method": "ondblclick", "func": elems[my_counter_i].ondblclick})
    }
    if (elems[my_counter_i].onerror != null) {
      events.push({"method": "onerror", "func": elems[my_counter_i].onerror})
    }
    if (elems[my_counter_i].onfocus != null) {
      events.push({"method": "onfocus", "func": elems[my_counter_i].onfocus})
    }
    if (elems[my_counter_i].onkeydown != null) {
      events.push({"method": "onkeydown", "func": elems[my_counter_i].onkeydown})
    }
    if (elems[my_counter_i].onkeypress != null) {
      events.push({"method": "onkeypress", "func": elems[my_counter_i].onkeypress})
    }
    if (elems[my_counter_i].onkeyup != null) {
      events.push({"method": "onkeyup", "func": elems[my_counter_i].onkeyup})
    }
    if (elems[my_counter_i].onmousedown != null) {
      events.push({"method": "onmousedown", "func": elems[my_counter_i].onmousedown})
    }
    if (elems[my_counter_i].onmousemove != null) {
      events.push({"method": "onmousemove", "func": elems[my_counter_i].onmousemove})
    }
    if (elems[my_counter_i].onmouseout != null) {
      events.push({"method": "onmouseout", "func": elems[my_counter_i].onmouseout})
    }
    if (elems[my_counter_i].onmouseup != null) {
      events.push({"method": "onmouseup", "func": elems[my_counter_i].onmouseup})
    }
    //console.log("We have: " + events.length + " events");
    if (events.length > 0) {
      elem = elems[my_counter_i]
      dom_adress = getXPath(elem);
      html_class = elems[my_counter_i].className;
      for (my_counter_j = 0; my_counter_j < events.length; my_counter_j++) {
        //function_id = MD5(events[my_counter_j].func.toString() )
        function_id = MD5(events[my_counter_j].func.toString() + dom_adress )

        f = events[my_counter_j].func.toString()
        e = events[my_counter_j].event_type // 疑似没用
        //clickable = JSON.parse(events[j])
        tut1 = events[my_counter_j]; // 疑似没用
        resp = {
          "function_id" : function_id,
          "event" : events[my_counter_j].method,
          "func" : events[my_counter_j].func.toString(),
          "id" : id,
          "tag" : tag,
          "addr" : dom_adress,
          "class" : html_class
        }
        //resp = JSON.stringify(resp);
        resps.push(resp);
      }
    }

  }
  return JSON.stringify(resps);
}

