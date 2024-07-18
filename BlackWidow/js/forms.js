// 功能是遍历页面中的所有表单，并提取每个表单及其包含的表单元素的相关信息，然后将这些信息以 JSON 字符串的形式返回。
function get_forms() {
  var forms = document.forms;// 获取页面中所有的表单, 包含页面中所有的 <form> 元素。
  var obj_forms = [];// 存储每个表单的信息对象。
  for(var i = 0; i < forms.length; i++) {
      // 为每个表单创建一个对象，
      form = {"action": forms[i].action, // action 属性
              "method": forms[i].method, // method属性
              "elements": []}; // 用于存储表单元素的信息。
      els = forms[i].elements;
      for(var j = 0; j < els.length; j++) {
        // 记录元素信息 
        form.elements.push( {"name": els[j].name,//name
                             "type": els[j].type, // type
                             "xpath": getXPath(els[j])} ); // xpath
      }
      obj_forms.push(form); // 对象 form 添加到 obj_forms 数组中。
  }
  return JSON.stringify(obj_forms);
}
