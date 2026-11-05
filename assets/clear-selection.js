/* Clear the employment spreadsheet's selection after a click outside it.
 * Dash's supported set_props API updates the DataTable's React state, rather
 * than just hiding a border. The delay lets a pending cell edit commit on blur.
 */
(function () {
  'use strict';

  document.addEventListener('pointerdown', function (event) {
    const table = document.getElementById('forecast-table');
    if (!table || table.contains(event.target)) return;

    window.setTimeout(function () {
      const currentTable = document.getElementById('forecast-table');
      if (!currentTable || currentTable.contains(document.activeElement)) return;

      const dash = window.dash_clientside;
      if (dash && typeof dash.set_props === 'function') {
        dash.set_props('forecast-table', {
          active_cell: null,
          selected_cells: [],
          start_cell: null,
          end_cell: null
        });
      }
    }, 50);
  });
})();
