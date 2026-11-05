/* Excel-style COPY fill handle for the monthly forecast DataTable.
 * This is interface-only code: the forecasting backend is not involved.
 * A drag sends the source/target row indices to a Dash Store. Python copies
 * the original cell value verbatim across the intervening rows.
 */
(function () {
  'use strict';
  let drag = null;
  let scheduled = false;

  function valueCells() {
    return document.querySelectorAll('#forecast-table td[data-dash-column="value"]');
  }

  function rowNumber(cell) {
    if (!cell) return null;
    const index = Number(cell.getAttribute('data-dash-row'));
    return Number.isInteger(index) && index >= 0 ? index : null;
  }

  function clearPreview() {
    document.querySelectorAll('#forecast-table .fill-preview').forEach(
      cell => cell.classList.remove('fill-preview')
    );
  }

  function showPreview(source, target) {
    clearPreview();
    for (const cell of valueCells()) {
      const row = rowNumber(cell);
      if (row !== null && row >= Math.min(source, target) && row <= Math.max(source, target)) {
        cell.classList.add('fill-preview');
      }
    }
  }

  function cellAt(x, y) {
    const element = document.elementFromPoint(x, y);
    return element && element.closest('#forecast-table td[data-dash-column="value"]');
  }

  function onPointerMove(event) {
    if (!drag) return;
    const cell = cellAt(event.clientX, event.clientY);
    const row = rowNumber(cell);
    if (row !== null) {
      drag.target = row;
      showPreview(drag.source, row);
    }
  }

  function onPointerUp(event) {
    if (!drag) return;
    const cell = cellAt(event.clientX, event.clientY);
    const row = rowNumber(cell);
    if (row !== null) drag.target = row;
    const { source, target } = drag;
    drag = null;
    document.body.classList.remove('is-fill-dragging');
    clearPreview();
    window.removeEventListener('pointermove', onPointerMove);
    window.removeEventListener('pointerup', onPointerUp);
    window.removeEventListener('pointercancel', onPointerCancel);
    if (source === target) return;
    if (window.dash_clientside && typeof window.dash_clientside.set_props === 'function') {
      window.dash_clientside.set_props('fill-event', {
        data: { source, target, nonce: Date.now() }
      });
    }
  }

  function onPointerCancel() {
    drag = null;
    document.body.classList.remove('is-fill-dragging');
    clearPreview();
    window.removeEventListener('pointermove', onPointerMove);
    window.removeEventListener('pointerup', onPointerUp);
    window.removeEventListener('pointercancel', onPointerCancel);
  }

  function addHandles() {
    scheduled = false;
    for (const cell of valueCells()) {
      // The fill handle should only be available for a confirmed numeric value.
      const raw = cell.textContent.trim().replace(/,/g, '');
      const hasValue = raw !== '' && Number.isFinite(Number(raw));
      cell.classList.toggle('has-forecast-value', hasValue);
      if (cell.querySelector(':scope > .forecast-fill-handle')) continue;
      const handle = document.createElement('span');
      handle.className = 'forecast-fill-handle';
      handle.title = 'Drag to copy this value to other months';
      handle.setAttribute('aria-label', 'Drag to fill months with this value');
      handle.addEventListener('pointerdown', function (event) {
        if (event.button !== 0 || drag) return;
        const source = rowNumber(cell);
        if (source === null || !cell.classList.contains('has-forecast-value')) return;
        event.preventDefault();
        event.stopPropagation();
        drag = { source, target: source };
        document.body.classList.add('is-fill-dragging');
        showPreview(source, source);
        window.addEventListener('pointermove', onPointerMove);
        window.addEventListener('pointerup', onPointerUp);
        window.addEventListener('pointercancel', onPointerCancel);
      });
      cell.appendChild(handle);
    }
  }

  function scheduleHandles() {
    if (!scheduled) {
      scheduled = true;
      requestAnimationFrame(addHandles);
    }
  }

  function start() {
    scheduleHandles();
    new MutationObserver(scheduleHandles).observe(document.body, { childList: true, subtree: true });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start);
  else start();
})();
