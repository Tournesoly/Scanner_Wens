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


// This JS-Script wrapps the addEventListener-Function, that is used by JQuery
// 包装（wrap）addEventListener 方法，以便在元素和文档对象上添加事件监听器时，执行一些额外的操作或记录。
callbackWrap(Element.prototype, "addEventListener", 1, addEventListenerWrapper);// 表示所有 DOM 元素的原型。
callbackWrap(Document.prototype, "addEventListener", 1,
bodyAddEventListenerWrapper);// 文档对象的原型。

// 当脚本嵌入到网页中并加载时，这几行代码会立即执行。这种执行是一次性的，也就是说，包装动作只会进行一次，但其效果是持续的。

// DOM元素或文档对象在调用上述 addEventListener时 实际会调用整个包装