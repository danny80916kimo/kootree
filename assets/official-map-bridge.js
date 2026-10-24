/* Only the same-origin embedded case map may change the selected record. */
window.addEventListener('message', function (event) {
  if (event.origin !== window.location.origin) return;
  const frame = document.getElementById('official_case_map');
  if (!frame || event.source !== frame.contentWindow) return;
  if (event.data && event.data.type === 'shu-tsan-case' && typeof event.data.id === 'string') {
    window.dash_clientside.set_props('official_case_select', {value: event.data.id});
  }
});
