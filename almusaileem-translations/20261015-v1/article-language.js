(function () {
  'use strict';
  var path = location.pathname;
  var manual = ['house-painting-cost-kuwait.html', 'flat-wood-marble-tv-wall-kuwait.html', 'gypsum-ceiling-planning-kuwait.html'];
  if (!/^\/\d{4}\/\d{2}\/[^/]+\.html$/.test(path) || manual.indexOf(path.split('/').pop()) !== -1) return;
  var root = document.getElementById('main');
  if (!root) return;
  var base = 'https://raw.githubusercontent.com/fahadtiktokkw-bit/OpenMontage/main/almusaileem-translations/20261015-v1/';
  var key = 'almusaileem-en-v1:' + path;
  var payload = null, pending = null, queued = false;
  var originals = new WeakMap(), attributes = new WeakMap(), languageAttributes = new WeakMap();
  var meta = document.querySelector('meta[name="description"]');
  var originalMeta = meta ? meta.content : null;
  var status = null;
  function norm(s) { return s.normalize('NFC').replace(/\s+/g, ' ').trim(); }
  function notify(message) {
    if (!status) {
      status = document.createElement('p');
      status.id = 'alm-translation-status';
      status.setAttribute('role', 'status');
      status.setAttribute('aria-live', 'polite');
      var heading = root.querySelector('h1');
      if (heading) heading.after(status); else root.prepend(status);
    }
    status.textContent = message;
  }
  function sync() {
    queued = false;
    if (!payload) return;
    var en = document.documentElement.lang === 'en';
    var walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT), node;
    while ((node = walker.nextNode())) {
      if (!node.parentElement || node.parentElement.closest('script,style,noscript,#alm-translation-status')) continue;
      var source = node.nodeValue, saved = originals.get(node), translated = payload.strings[norm(source)];
      if (en && typeof translated === 'string') {
        var next = source.replace(source.trim(), translated);
        if (next !== source) { originals.set(node, { ar: source, en: next }); node.nodeValue = next; }
      } else if (!en && saved && source === saved.en) {
        node.nodeValue = saved.ar;
      }
    }
    root.querySelectorAll('[alt],[aria-label],[title]').forEach(function (el) {
      var saved = attributes.get(el) || {};
      ['alt','aria-label','title'].forEach(function (attr) {
        var value = el.getAttribute(attr);
        if (!value) return;
        var translated = payload.strings[norm(value)];
        if (en && typeof translated === 'string' && translated !== value) {
          saved[attr] = { ar: value, en: translated }; el.setAttribute(attr, translated);
        } else if (!en && saved[attr] && value === saved[attr].en) el.setAttribute(attr, saved[attr].ar);
      });
      attributes.set(el, saved);
    });
    root.querySelectorAll('[lang]').forEach(function (el) {
      if (!languageAttributes.has(el)) languageAttributes.set(el, el.getAttribute('lang'));
      var value = en ? 'en' : languageAttributes.get(el);
      if (el.getAttribute('lang') !== value) el.setAttribute('lang', value);
    });
    var pageTitle = en ? payload.title + ' | Almusaileem' : payload.titleAr + ' | ' + '\u0627\u0644\u0645\u0633\u064a\u0644\u064a\u0645';
    if (document.title !== pageTitle) document.title = pageTitle;
    if (meta) {
      var description = en ? payload.description : originalMeta;
      if (description && meta.content !== description) meta.content = description;
    }
    if (status) { status.remove(); status = null; }
    root.dataset.englishTranslation = en ? 'ready' : 'original';
  }
  function schedule() {
    if (!queued && payload) { queued = true; requestAnimationFrame(sync); }
  }
  function accept(data) {
    if (!data || typeof data.strings !== 'object' || typeof data.title !== 'string') throw new Error('Invalid translation');
    var normalized = {};
    Object.keys(data.strings).forEach(function (k) { normalized[norm(k)] = data.strings[k]; });
    data.strings = normalized; payload = data; sync();
  }
  function load() {
    if (document.documentElement.lang !== 'en') { if (status) { status.remove(); status = null; } sync(); return; }
    if (payload) { sync(); return; }
    if (pending) return;
    try {
      var cached = sessionStorage.getItem(key);
      if (cached) { accept(JSON.parse(cached)); return; }
    } catch (_) {}
    notify('Preparing the English version...');
    pending = fetch(base + path.split('/').pop().replace(/\.html$/, '.json'), { credentials: 'omit', cache: 'force-cache' })
      .then(function (r) { if (!r.ok) throw new Error('Translation unavailable'); return r.json(); })
      .then(function (data) { accept(data); try { sessionStorage.setItem(key, JSON.stringify(data)); } catch (_) {} })
      .catch(function () { if (document.documentElement.lang === 'en') notify('The English version could not be loaded. Please refresh the page.'); })
      .finally(function () { pending = null; });
  }
  new MutationObserver(schedule).observe(root, { childList: true, characterData: true, subtree: true });
  new MutationObserver(load).observe(document.documentElement, { attributes: true, attributeFilter: ['lang'] });
  load();
})();
