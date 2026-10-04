// The local server caches the public GitHub check; rendering never waits for it.
(function () {
  var notice = document.getElementById('update-notice');
  if (!notice) return;
  fetch(notice.dataset.checkUrl)
    .then(function (response) { return response.ok ? response.json() : null; })
    .then(function (data) {
      if (!data || !/^\d+\.\d+\.\d+$/.test(data.version || '')) return;
      notice.querySelector('[data-update-version]').textContent = data.version;
      notice.hidden = false;
    })
    .catch(function () { /* Update checks must not interrupt local work. */ });
})();
