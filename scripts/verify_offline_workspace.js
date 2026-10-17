/* CI-only journey over the maintained generic saved-result fixture. */
(async () => {
  const options = window.priorityxCheckOptions;
  document.currentScript?.remove();
  const $ = id => document.getElementById(id);
  const checks = [];
  const assert = (condition, name) => {
    if (!condition) throw Error(name);
    checks.push(name);
  };
  const tick = () => new Promise(resolve => setTimeout(resolve, 25));
  const ready = async () => {
    for (let i = 0; i < 400; i++) {
      if (window.priorityxWorkspace?.ready) return;
      await tick();
    }
    throw Error('Workspace did not become ready: ' + $('render-status').textContent);
  };
  const change = async (id, value) => {
    $(id).value = value;
    $(id).dispatchEvent(new Event('change', {bubbles: true}));
    await ready();
  };
  let result;
  try {
    await ready();
    const app = window.priorityxWorkspace;
    const original = JSON.stringify(app.source);
    assert(location.protocol === 'file:', 'direct file URL');
    assert(!app.service, 'offline mode without Python service');
    const brand = document.querySelector('h1');
    const symbol = brand.querySelector('svg');
    const name = brand.querySelector('.brand-name');
    assert(brand.getAttribute('aria-label') === 'PriorityX', 'accessible brand name');
    assert(name?.textContent === 'PriorityX' && getComputedStyle(name).opacity === '1', 'intact visible brand name');
    assert(symbol?.getBoundingClientRect().width >= 16 && symbol.closest('[aria-hidden="true"]') && symbol.getBoundingClientRect().right <= name.getBoundingClientRect().left, 'visible decorative symbol precedes name');
    const favicon = document.querySelector('link[rel="icon"]')?.getAttribute('href');
    assert(favicon?.startsWith('data:image/svg+xml,'), 'favicon embedded without a network asset');
    const faviconSvg = new DOMParser().parseFromString(decodeURIComponent(favicon.slice(favicon.indexOf(',') + 1)), 'image/svg+xml');
    assert(!faviconSvg.querySelector('parsererror') && faviconSvg.querySelector('path,circle'), 'embedded favicon is a valid vector');
    assert($('savePng').disabled && $('saveSvg').disabled, 'Python print controls disabled offline');
    assert(app.state.cadence === 'quarterly', 'Quarterly opening/restored cadence');
    assert($('type').selectedOptions[0].textContent === 'Work units', 'caller type label preserved');
    for (const family of ['matrix', 'timeline', 'paths']) {
      assert($('pl-' + family + '-inner').data?.length > 0, family + ' rendered');
    }
    const panels = [...document.querySelectorAll('.panel')].map(p => p.getBoundingClientRect());
    assert(panels.every(p => Math.abs(p.width - panels[0].width) < 1 && Math.abs(p.height - panels[0].height) < 1), 'equal chart panels');
    assert(app.data().periods.join(',') === '2025-Q1,2025-Q2,2025-Q3,2025-Q4', 'complete YTD periods');
    assert(app.windowData(app.data()).events.length === 1, 'saved YTD event retained');
    const event = app.windowData(app.data()).events[0];
    assert(event.entity === '001' && event.source === '2' && event.destination === '1' && event.suffix === '*XY', 'exact saved event values');
    if (options.phase === 'reopen') {
      assert(app.state.member === '001' && app.state.panel_height === 480, 'selection and layout survive export/reopening');
      assert(app.state.views[app.data().key].data_tab === 'paths' && $('pathsScope').value === 'all', 'data tab and scope survive reopening');
      const range = $('pl-matrix-inner')._fullLayout.xaxis.range;
      assert(Math.abs(range[0] + 2) < 1e-6 && Math.abs(range[1] - 3) < 1e-6, 'actual zoom survives reopening');
      assert(!document.querySelector('dialog[open],.export-menu[open],.action-menu[open]'), 'transient controls reopen closed');
    }
    await change('member', '001');
    assert(app.state.member === '001', 'linked entity selection');
    await change('cadence', 'monthly');
    assert(app.state.member === '001' && app.data().periods.length === 12, 'Monthly cadence preserves selection and YTD');
    await change('cadence', 'quarterly');
    $('clear').click();
    await ready();
    assert(app.state.member === '', 'clear selection restores automatic group');
    await change('member', '001');
    await Plotly.relayout($('pl-matrix-inner'), {'xaxis.range': [-2, 3], 'yaxis.range': [-3, 4]});
    $('reset').click();
    await ready();
    assert($('pl-matrix-inner')._fullLayout.xaxis.range[0] !== -2, 'reset view restores fitted range');
    $('layoutLink').click();
    $('panelHeight').value = '480';
    $('panelHeight').dispatchEvent(new Event('input', {bubbles: true}));
    $('layout-form').dispatchEvent(new Event('submit', {bubbles: true, cancelable: true}));
    await ready();
    $('layout-settings').close();
    assert(app.state.panel_height === 480, 'layout regeneration applies offline');
    $('data-panel').open = true;
    $('tab-paths').click();
    await change('pathsScope', 'all');
    await Plotly.relayout($('pl-matrix-inner'), {'xaxis.range': [-2, 3], 'yaxis.range': [-3, 4]});
    app.capture();
    assert(JSON.stringify(app.source) === original, 'saved analytical values unchanged');
    assert(window.priorityxNetworkAttempts.length === 0, 'zero network requests while offline');
    assert(!document.querySelector('script[src],link[rel="stylesheet"]'), 'all executable/style assets inline');
    assert(performance.getEntriesByType('resource').every(r => !/^https?:/.test(r.name)), 'no external resource loads');
    let exported;
    if (options.phase === 'first') {
      document.querySelector('[data-ci-policy]')?.remove();
      const createObjectURL = URL.createObjectURL;
      const click = HTMLAnchorElement.prototype.click;
      let blob;
      URL.createObjectURL = value => { blob = value; return createObjectURL(value); };
      HTMLAnchorElement.prototype.click = function () {};
      try {
        await app.exportHtml();
        assert(blob instanceof Blob, 'actual HTML export produced');
        exported = await blob.text();
      } finally {
        URL.createObjectURL = createObjectURL;
        HTMLAnchorElement.prototype.click = click;
      }
    }
    result = {status: 'pass', phase: options.phase, checks, browser: navigator.userAgent, exported};
  } catch (error) {
    result = {status: 'fail', phase: options.phase, checks, error: error.stack || String(error)};
  }
  const receipt = document.createElement('pre');
  receipt.id = 'priorityx-ci-result';
  receipt.textContent = JSON.stringify(result);
  document.body.append(receipt);
})();
