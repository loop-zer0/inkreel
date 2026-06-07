/**
 * core.js — InkReel 微型响应式前端框架（~200行，零依赖）
 *
 * 三个模块：
 *   Store     — 基于 Proxy 的响应式状态，赋值自动通知订阅者
 *   Component — UI 组件注册 + 事件委托 + 批量渲染
 *   DOM       — 安全 HTML 构建器 + 元素快速创建
 */

// ══════════════════════════════════════════════════════════════
// 1. Store — 响应式状态
// ══════════════════════════════════════════════════════════════

const Store = {
  create(initial) {
    const listeners = new Map();

    function makeProxy(obj, path) {
      return new Proxy(obj, {
        set(target, key, value) {
          const old = target[key];
          target[key] = value;
          if (old !== value) {
            const fullKey = path ? `${path}.${key}` : String(key);
            // 精确监听
            notify(fullKey, value, old);
            // 父级监听（如监听 "novel" 时 "novel.title" 变化也通知）
            const parts = fullKey.split('.');
            for (let i = 0; i < parts.length; i++) {
              notify(parts.slice(0, i + 1).join('.'), value, old);
            }
            // 通配符
            notify('*', { key: fullKey, value, old });
          }
          return true;
        },
      });
    }

    function notify(key, value, old) {
      if (listeners.has(key)) {
        listeners.get(key).forEach(fn => fn(value, old, key));
      }
    }

    const store = makeProxy(initial, '');

    // 监听特定 key 的变化
    store.$on = function (key, fn) {
      if (!listeners.has(key)) listeners.set(key, new Set());
      listeners.get(key).add(fn);
      return () => listeners.get(key).delete(fn);  // 返回取消函数
    };

    // 批量更新（避免每行 set 都触发一次渲染）
    store.$batch = function (fn) {
      this._batching = true;
      fn(this);
      this._batching = false;
      // 批量更新完后统一通知
      notify('*', { key: '*', value: null, old: null });
    };

    return store;
  },
};


// ══════════════════════════════════════════════════════════════
// 2. Component — UI 组件注册 + 事件委托
// ══════════════════════════════════════════════════════════════

const Component = {
  _registry: [],

  // 注册组件: { id, mount, render(state), events?: { selector: handler } }
  register(def) {
    this._registry.push(def);
    return def;
  },

  // 渲染所有已注册组件
  renderAll(state) {
    for (const c of this._registry) {
      try {
        if (!c.el) c.el = document.getElementById(c.mount);
        if (!c.el) continue;
        if (c.shouldRender && !c.shouldRender(state)) continue;
        c.render(state);
      } catch (e) {
        console.error(`[Component] ${c.id} render error:`, e);
      }
    }
  },

  // 绑定所有组件的事件（在 DOM 加载后调用一次）
  bindEvents(root = document) {
    for (const c of this._registry) {
      if (!c.events) continue;
      for (const [selector, handlers] of Object.entries(c.events)) {
        const el = c.mount ? document.getElementById(c.mount) : root;
        if (!el) continue;
        // 使用事件委托
        for (const [eventType, fn] of Object.entries(handlers)) {
          el.addEventListener(eventType, function (e) {
            const target = e.target.closest(selector);
            if (target) {
              fn.call(c, e, target);
            }
          });
        }
      }
    }
  },
};


// ══════════════════════════════════════════════════════════════
// 3. DOM — 安全 HTML 构建 + 元素创建
// ══════════════════════════════════════════════════════════════

window.DOM = {
  // 转义 HTML
  esc(s) {
    if (s == null) return '';
    return String(s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  },

  // 快速创建元素: DOM.el('div', {class:'foo', id:'bar'}, child1, child2)
  el(tag, attrs, ...children) {
    const e = document.createElement(tag);
    if (attrs) {
      for (const [k, v] of Object.entries(attrs)) {
        if (k === 'class' || k === 'className') e.className = v;
        else if (k === 'html') e.innerHTML = v;
        else if (k.startsWith('on')) e.addEventListener(k.slice(2), v);
        else if (v === false) e.removeAttribute(k);
        else if (v != null) e.setAttribute(k, v);
      }
    }
    for (const child of children.flat(Infinity)) {
      if (child == null || child === false) continue;
      if (typeof child === 'string' || typeof child === 'number') {
        e.appendChild(document.createTextNode(String(child)));
      } else if (child instanceof Node) {
        e.appendChild(child);
      }
    }
    return e;
  },

  // 清空并填充容器
  fill(container, ...children) {
    while (container.firstChild) container.removeChild(container.firstChild);
    for (const child of children.flat(Infinity)) {
      if (child == null || child === false) continue;
      if (typeof child === 'string') {
        container.appendChild(document.createTextNode(child));
      } else if (child instanceof Node) {
        container.appendChild(child);
      }
    }
  },
};


// ══════════════════════════════════════════════════════════════
// 4. 默认设置：state 变化 → 自动渲染所有组件
// ══════════════════════════════════════════════════════════════

// 给 Store.create 的对象加默认的全局渲染绑定
const _origCreate = Store.create.bind(Store);
Store.create = function (initial) {
  const s = _origCreate(initial);
  s.$on('*', () => {
    // 如果正在批量更新则跳过单次渲染
    if (s._batching) return;
    requestAnimationFrame(() => Component.renderAll(s));
  });
  return s;
};
