// 原始 window.alert：被传入 IIFE 但未被使用，存储在 proxied 变量中。新 window.alert：被重写为空函数，这意味着在页面中任何地方调用 alert 都不会有任何效果。
(function(proxied) {
  window.alert = function() { };
})(window.alert);

// 原始 window.confirm：被传入 IIFE 但未被使用，存储在 proxied 变量中。 新 window.confirm：被重写为一个总是返回 true 的函数，这意味着在页面中任何地方调用 confirm 都会直接返回 true，就像用户总是点击“确定”按钮一样。
(function(proxied) {
  window.confirm = function() { return true; };
})(window.confirm);

// 好怪哦