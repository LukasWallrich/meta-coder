const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const { JSDOM } = require('jsdom');
const script = new vm.Script(fs.readFileSync('meta_coder/static/updates.js', 'utf8'), { filename: path.resolve('meta_coder/static/updates.js') });
const flush = () => new Promise(resolve => setImmediate(resolve));

for (const [name, response, visible] of [
  ['new release', { ok: true, json: async () => ({ version: '1.2.3' }) }, true],
  ['current release', { ok: true, json: async () => ({ version: null }) }, false],
  ['invalid version', { ok: true, json: async () => ({ version: '<script>' }) }, false],
  ['HTTP failure', { ok: false }, false],
  ['invalid JSON', { ok: true, json: async () => { throw Error('bad JSON'); } }, false],
  ['network failure', null, false],
]) {
  test(`update notice: ${name}`, async () => {
    const dom = new JSDOM('<div id="update-notice" data-check-url="/token/updates" hidden><span data-update-version></span></div>', { runScripts: 'outside-only' });
    dom.window.fetch = async url => {
      assert.equal(url, '/token/updates');
      if (response === null) throw Error('offline');
      return response;
    };
    script.runInContext(dom.getInternalVMContext());
    await flush();
    const notice = dom.window.document.getElementById('update-notice');
    assert.equal(notice.hidden, !visible);
    assert.equal(notice.textContent, visible ? '1.2.3' : '');
    dom.window.close();
  });
}
test('update script tolerates pages without a notice', () => {
  const dom = new JSDOM('', { runScripts: 'outside-only' });
  dom.window.fetch = () => { throw Error('must not fetch'); };
  script.runInContext(dom.getInternalVMContext());
  dom.window.close();
});
