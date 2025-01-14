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
// window 对象，即全局对象,它表示浏览器窗口或框架。
timingCallbackWrap(window, "setTimeout", 0, timeoutWrapper);
timingCallbackWrap(window, "setInterval", 0, intervallWrapper);