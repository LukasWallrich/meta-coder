const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

// Exercise the shared edit guard independently of rendering or a browser.
const source = fs.readFileSync('meta_coder/static/app.js', 'utf8').split('// Theme toggle')[0];
function setup() {
  const listeners = {};
  const buttons = [{ disabled: false }, { disabled: true }];
  const hidden = new Map();
  let reloads = 0;
  const context = {
    document: {
      querySelectorAll: () => buttons,
      getElementById: id => ({ classList: {
        toggle: (_, value) => hidden.set(id, value),
        remove: () => hidden.set(id, false),
      }}),
      addEventListener: (name, callback) => { listeners[name] = callback; },
    },
    window: {
      addEventListener: (name, callback) => { listeners[name] = callback; },
      location: { reload: () => reloads++ },
    },
    queueMicrotask,
  };
  vm.createContext(context);
  vm.runInContext(source, context);
  return { edits: context.projectEdits, buttons, hidden, listeners, reloads: () => reloads };
}

test('unsaved edits block runs; undo restores only previously enabled actions', () => {
  const ui = setup();
  let changed = false;
  ui.edits.register({}, () => changed);
  changed = true;
  ui.edits.update();
  assert.deepEqual(ui.buttons.map(button => button.disabled), [true, true]);
  assert.equal(ui.hidden.get('unsaved-changes'), false);
  changed = false;
  ui.edits.update();
  assert.deepEqual(ui.buttons.map(button => button.disabled), [false, true]);
});

test('background completion preserves edits and offers an explicit refresh', () => {
  const ui = setup();
  ui.edits.register({}, () => true);
  ui.edits.refresh();
  assert.equal(ui.reloads(), 0);
  assert.equal(ui.hidden.get('background-update'), false);
  const clean = setup();
  clean.edits.refresh();
  assert.equal(clean.reloads(), 1);
});

test('saving a form excludes its edits, but protects changes in another form', async () => {
  const ui = setup();
  const manual = {};
  ui.edits.register(manual, () => true);
  ui.listeners.submit({ target: manual, defaultPrevented: false });
  await Promise.resolve();
  assert.equal(ui.edits.dirty(), false);
  ui.edits.register({}, () => true);
  let prevented = false;
  ui.listeners.beforeunload({ preventDefault: () => { prevented = true; } });
  assert.equal(prevented, true);
  assert.equal(ui.edits.dirty(), true);
});

test('asynchronous or cancelled submissions keep navigation protection', async () => {
  const ui = setup();
  const sheet = {};
  ui.edits.register(sheet, () => true);
  ui.listeners.submit({ target: sheet, defaultPrevented: true });
  await Promise.resolve();
  assert.equal(ui.edits.dirty(), true);
});

function setupLiveSearch() {
  const callbacks = {};
  const timers = new Map();
  const requests = [];
  const urls = [];
  let timerId = 0;
  const query = { value: '', addEventListener: (name, fn) => { callbacks['query:' + name] = fn; } };
  const sort = { value: 'newest', addEventListener: (name, fn) => { callbacks['sort:' + name] = fn; } };
  const results = {
    dataset: {}, attributes: {}, children: ['original'],
    setAttribute(name, value) { this.attributes[name] = value; },
    replaceChildren(...children) { this.children = children; },
  };
  const status = { textContent: '', classList: { add() {}, remove() {} } };
  const form = { action: 'http://localhost/test/', addEventListener: (name, fn) => { callbacks['form:' + name] = fn; } };
  const context = {
    document: {
      querySelector: () => form,
      getElementById: id => ({ 'project-search': query, 'project-sort': sort, 'project-search-results': results, 'project-search-status': status })[id],
    },
    window: { location: { href: 'http://localhost/test/?page=3' }, history: { replaceState: (_, __, url) => urls.push(String(url)) } },
    URL, AbortController,
    setTimeout: fn => { timers.set(++timerId, fn); return timerId; },
    clearTimeout: id => timers.delete(id),
    fetch: (url, options) => new Promise(resolve => requests.push({ url, options, resolve })),
    DOMParser: class { parseFromString(html) { return { getElementById: () => ({ childNodes: [html], dataset: { resultCount: '2' } }) }; } },
  };
  vm.createContext(context);
  const liveSource = fs.readFileSync('meta_coder/static/app.js', 'utf8').split('// Live project search')[1];
  vm.runInContext('// Live project search' + liveSource, context);
  return { callbacks, query, sort, results, status, requests, urls, timers,
    flush() { const pending = Array.from(timers.values()); timers.clear(); return pending.map(fn => fn()); },
  };
}

test('live search debounces typing, resets pagination, and ignores stale responses', async () => {
  const ui = setupLiveSearch();
  ui.query.value = 'm';
  ui.callbacks['query:input']({});
  ui.query.value = 'memory';
  ui.callbacks['query:input']({});
  assert.equal(ui.timers.size, 1);
  const first = ui.flush()[0];
  assert.equal(ui.requests[0].url.searchParams.get('q'), 'memory');
  assert.equal(ui.requests[0].url.searchParams.has('page'), false);
  ui.query.value = 'attention';
  ui.callbacks['query:input']({});
  assert.equal(ui.requests[0].options.signal.aborted, true);
  const second = ui.flush()[0];
  ui.requests[1].resolve({ ok: true, text: async () => 'attention results' });
  await second;
  ui.requests[0].resolve({ ok: true, text: async () => 'stale results' });
  await first;
  assert.deepEqual(ui.results.children, ['attention results']);
  assert.equal(ui.query.value, 'attention');
  assert.equal(ui.urls.length, 1);
  assert.equal(ui.results.attributes['aria-busy'], 'false');
});

test('sort refreshes results and a failed search keeps existing projects with retry feedback', async () => {
  const ui = setupLiveSearch();
  ui.sort.value = 'name';
  ui.callbacks['sort:change']();
  const pending = ui.flush()[0];
  assert.equal(ui.requests[0].url.searchParams.get('sort'), 'name');
  ui.requests[0].resolve({ ok: false });
  await pending;
  assert.deepEqual(ui.results.children, ['original']);
  assert.match(ui.status.textContent, /press Enter to retry/);
  assert.equal(ui.results.attributes['aria-busy'], 'false');
});
