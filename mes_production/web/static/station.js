/**
 * MES — Station detail page logic
 *
 * 1. Load stations → populate <select>.
 * 2. On select change → load orders on that station.
 * 3. Auto-refresh every 3 s when a station is selected.
 */
(function () {
    'use strict';

    var STATION_CONTENT = document.getElementById('stationContent');
    var STATION_SELECT   = document.getElementById('stationSelect');

    /* ── helpers ────────────────────────────────────────────── */

    /**
     * Return all orders whose current_station matches the given id.
     * current_station is 1-based; we filter on the client because the
     * existing GET /api/orders?status=production endpoint returns all
     * in-production orders and the server has no per-station filter yet.
     */
    function getOrdersForStation(stationId, callback) {
        MESUtils.fetchJson('/api/orders?status=production', function (orders) {
            if (!orders) return callback([]);
            var targetId = parseFloat(stationId);
            var filtered = orders.filter(function (o) {
                return o.current_station === targetId;
            });
            callback(filtered);
        });
    }

    /* ── render ─────────────────────────────────────────────── */

    function renderOrders(stationName, orders) {
        var html = '';

        html += '<div class="card station-header-bar">';
        html += '  <div class="station-header">';
        html += '    <span class="station-name">' + MESUtils.escapeHtml(stationName) + '</span>';
        html += '    <span class="station-order-count">' + orders.length + ' заказ(ов)</span>';
        html += '  </div>';
        html += '</div>';

        if (orders.length === 0) {
            html += '<div class="card station-empty">';
            html += '  <p>Нет заказов на этой станции</p>';
            html += '</div>';
        } else {
            html += '<div class="table-container"><table>';
            html += '<thead><tr>';
            html += '<th>№ заказа</th>';
            html += '<th>Партия</th>';
            html += '<th>Код товара</th>';
            html += '<th>Цвет</th>';
            html += '<th>Запущен</th>';
            html += '<th>Действия</th>';
            html += '</tr></thead><tbody>';

            orders.forEach(function (o) {
                html += '<tr>';
                html += '<td>' + MESUtils.escapeHtml(o.order_number) + '</td>';
                html += '<td>' + MESUtils.escapeHtml(o.batch) + '</td>';
                html += '<td>' + MESUtils.escapeHtml(o.product_code) + '</td>';
                html += '<td>' + MESUtils.escapeHtml(o.color) + '</td>';
                html += '<td>' + MESUtils.formatDate(o.started_at) + '</td>';
                html += '<td class="action-buttons">';
                html += '  <button class="btn btn-sm btn-success" onclick="MESStation.moveOrder(' + o.id + ')">Переместить →</button>';
                html += '  <button class="btn btn-sm btn-danger"   onclick="MESStation.cancelOrder(' + o.id + ')">Отмена</button>';
                html += '</td>';
                html += '</tr>';
            });

            html += '</tbody></table></div>';
        }

        STATION_CONTENT.innerHTML = html;
    }

    /* ── actions ────────────────────────────────────────────── */

    function reloadCurrentStation() {
        var opt = STATION_SELECT.options[STATION_SELECT.selectedIndex];
        if (!opt || !opt.value) return;
        var stationId = parseFloat(opt.value);
        var stationName = opt.text;

        getOrdersForStation(stationId, function (orders) {
            renderOrders(stationName, orders);
        });
    }

    /* Expose action functions on the global namespace so onclick works */
    window.MESStation = {};

    window.MESStation.moveOrder = function (orderId) {
        var ok = confirm('Переместить заказ на следующую станцию?');
        if (!ok) return;
        fetch('/api/orders/' + orderId + '/move', {
            method: 'POST',
            headers: MESUtils.authHeaders({ 'Content-Type': 'application/json' })
        })
        .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, data: d }; }); })
        .then(function (res) {
            if (res.ok) {
                MESUtils.showToast('Заказ перемещён', 'success');
            } else {
                MESUtils.showToast(res.data.message || res.data.error || 'Ошибка', 'error');
            }
            reloadCurrentStation();
        })
        .catch(function () { MESUtils.showToast('Ошибка соединения', 'error'); });
    };

    window.MESStation.cancelOrder = function (orderId) {
        var ok = confirm('Отменить заказ?');
        if (!ok) return;
        fetch('/api/orders/' + orderId + '/cancel', {
            method: 'POST',
            headers: MESUtils.authHeaders({ 'Content-Type': 'application/json' })
        })
        .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, data: d }; }); })
        .then(function (res) {
            if (res.ok) {
                MESUtils.showToast('Заказ отменён', 'success');
            } else {
                MESUtils.showToast(res.data.message || res.data.error || 'Ошибка', 'error');
            }
            reloadCurrentStation();
        })
        .catch(function () { MESUtils.showToast('Ошибка соединения', 'error'); });
    };

    /* ── init ───────────────────────────────────────────────── */

    function loadStations() {
        MESUtils.fetchJson('/api/stations', function (stations) {
            if (!stations) return;

            // Rebuild <select> options (preserve current selection)
            var currentValue = STATION_SELECT.value;
            STATION_SELECT.innerHTML = '<option value="" disabled>' +
                (currentValue ? '-- Станция --' : '-- Станция не выбрана --') + '</option>';

            stations.forEach(function (s) {
                var opt = document.createElement('option');
                opt.value = s.id;
                opt.textContent = s.id + '. ' + s.name;
                STATION_SELECT.appendChild(opt);
            });

            // Restore selection if still valid
            if (currentValue) {
                STATION_SELECT.value = currentValue;
            }
        });
    }

    function setupSelect() {
        STATION_SELECT.addEventListener('change', function () {
            reloadCurrentStation();
            // Start / restart auto-refresh
            window.MESRefresh.stop();
            window.MESRefresh.start(reloadCurrentStation, 3000);
        });
    }

    /* Run on DOM ready */
    document.addEventListener('DOMContentLoaded', function () {
        loadStations();
        setupSelect();
    });
})();
