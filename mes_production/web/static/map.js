/**
 * MES — SVG Pipeline Tracking Page (with sub-stations)
 *
 * Layout:
 *   Main stations on top row (y = MAIN_Y)
 *   Sub-stations below their parent (y = SUB_Y), connected with arrows
 *   Pipes connect stations horizontally (main → sub → main → sub → main)
 */
(function () {
    'use strict';

    var SVG_NS = 'http://www.w3.org/2000/svg';
    var svg, pipesGroup, nodesGroup, ordersGroup, labelsGroup;

    /* ── Layout constants ──────────────────────────────────── */

    var MAIN_Y = 120;             // y for main station row
    var SUB_Y  = 240;             // y for sub-station row
    var NODE_R = 30;              // node radius
    var SUB_NODE_R = 26;          // sub-station node radius
    var FIRST_X = 60;             // x of station 1
    var MAIN_SPACING = 108;       // horizontal gap between main station centres
    var SUB_OFFSET_X = 0;         // sub-station horizontal offset relative to parent
    var PIPE_H = 14;              // horizontal pipe height
    var PIPE_V_H = 10;            // vertical pipe height
    var BADGE_W = 60, BADGE_H = 22;
    var BADGE_GAP = 36;
    var ORDERS_MAIN_Y = 320;      // order badges below main stations
    var ORDERS_SUB_Y  = 340;      // order badges below sub-stations
    var ARROW_HEAD = 8;           // arrow head size

    /* ── Station data (sorted by id) ───────────────────────── */

    var stationData = [];

    /* ── Helpers ───────────────────────────────────────────── */

    function el(tag, attrs, text) {
        var e = document.createElementNS(SVG_NS, tag);
        if (attrs) Object.keys(attrs).forEach(function (k) { e.setAttribute(k, attrs[k]); });
        if (text !== undefined) e.textContent = text;
        return e;
    }

    function clearGroup(g) { while (g.firstChild) g.removeChild(g.firstChild); }

    function isSub(id) { return id !== Math.floor(id); }
    function formatId(id) { return id === Math.floor(id) ? String(Math.floor(id)) : String(id); }

    function nodeX(stationId) {
        // All stations (main + sub) get a position on the main horizontal axis
        // Main stations: FIRST_X + (id - 1) * MAIN_SPACING
        // Sub-stations: same x as parent
        var mainPart = Math.floor(stationId);
        return FIRST_X + (mainPart - 1) * MAIN_SPACING;
    }

    function nodeY(stationId) {
        return isSub(stationId) ? SUB_Y : MAIN_Y;
    }

    function nodeR(stationId) {
        return isSub(stationId) ? SUB_NODE_R : NODE_R;
    }

    /* ── Group sub-stations by parent ──────────────────────── */

    function groupStations(stations) {
        // Returns [{id, name, orders, subs: [{id, name, orders}]}]
        var groups = [];
        stations.forEach(function (s) {
            if (!isSub(s.id)) {
                groups.push({ id: s.id, name: s.name, orders: s.orders || [], subs: [] });
            }
        });
        stations.forEach(function (s) {
            if (isSub(s.id)) {
                var parent = Math.floor(s.id);
                for (var i = 0; i < groups.length; i++) {
                    if (groups[i].id === parent) {
                        groups[i].subs.push(s);
                        break;
                    }
                }
            }
        });
        // Sort subs within each group
        groups.forEach(function (g) { g.subs.sort(function (a, b) { return a.id - b.id; }); });
        return groups;
    }

    /* ── Render pipes (horizontal + vertical arrows) ───────── */

    function renderPipes(stations) {
        clearGroup(pipesGroup);

        var groups = groupStations(stations);

        groups.forEach(function (group, gi) {
            var px = nodeX(group.id);

            // ── Vertical pipes from main to sub-stations ──
            group.subs.forEach(function (sub, si) {
                var sx = px + (si - (group.subs.length - 1) / 2) * 60; // spread subs horizontally
                var startY = MAIN_Y + NODE_R;
                var endY = SUB_Y - SUB_NODE_R;
                var hasFlow = (sub.orders || []).length > 0;

                // Vertical pipe
                pipesGroup.appendChild(el('rect', {
                    x: sx - PIPE_V_H / 2, y: startY,
                    width: PIPE_V_H, height: endY - startY,
                    rx: PIPE_V_H / 2,
                    fill: 'var(--bg-secondary)',
                    opacity: '0.4'
                }));

                // Pipe fill
                pipesGroup.appendChild(el('rect', {
                    x: sx - PIPE_V_H / 2 + 2, y: startY + 2,
                    width: PIPE_V_H - 4, height: endY - startY - 4,
                    rx: (PIPE_V_H - 4) / 2,
                    fill: hasFlow ? 'var(--status-production)' : 'var(--status-buffer)',
                    opacity: hasFlow ? '0.6' : '0.2'
                }));

                // Arrow head (pointing down)
                pipesGroup.appendChild(el('polygon', {
                    points: sx + ',' + (endY + ARROW_HEAD) +
                            ',' + (sx - ARROW_HEAD / 2) + ',' + (endY - ARROW_HEAD / 3) +
                            ',' + (sx + ARROW_HEAD / 2) + ',' + (endY - ARROW_HEAD / 3),
                    fill: hasFlow ? 'var(--status-production)' : 'var(--status-buffer)',
                    opacity: hasFlow ? '0.7' : '0.3'
                }));
            });

            // ── Horizontal pipes to next main station ──
            if (gi + 1 < groups.length) {
                var nextGroup = groups[gi + 1];
                var x1 = px + NODE_R;
                var x2 = nodeX(nextGroup.id) - NODE_R;
                var fromHas = group.orders.length > 0 || group.subs.some(function (s) { return (s.orders || []).length > 0; });
                var toHas = nextGroup.orders.length > 0 || nextGroup.subs.some(function (s) { return (s.orders || []).length > 0; });
                var hasFlow = fromHas || toHas;

                // Background pipe
                pipesGroup.appendChild(el('rect', {
                    x: x1, y: MAIN_Y - PIPE_H / 2,
                    width: x2 - x1, height: PIPE_H,
                    rx: PIPE_H / 2,
                    fill: 'var(--bg-secondary)',
                    opacity: '0.4'
                }));

                // Fill
                var color = hasFlow ? 'var(--status-production)' : 'var(--status-buffer)';
                pipesGroup.appendChild(el('rect', {
                    x: x1, y: MAIN_Y - PIPE_H / 2 + 2,
                    width: x2 - x1, height: PIPE_H - 4,
                    rx: (PIPE_H - 4) / 2,
                    fill: color,
                    opacity: hasFlow ? '0.6' : '0.2'
                }));

                // Animated dash
                if (hasFlow) {
                    pipesGroup.appendChild(el('line', {
                        x1: x1 + 4, y1: MAIN_Y,
                        x2: x2 - 4, y2: MAIN_Y,
                        stroke: 'var(--bg-card)',
                        'stroke-width': '2',
                        'stroke-dasharray': '8 8',
                        class: 'flow-line',
                        opacity: '0.5'
                    }));
                }

                // Arrow head on horizontal pipe (pointing right)
                pipesGroup.appendChild(el('polygon', {
                    points: (x2 + ARROW_HEAD) + ',' + MAIN_Y +
                            ',' + (x2 - ARROW_HEAD / 3) + ',' + (MAIN_Y - ARROW_HEAD / 2) +
                            ',' + (x2 - ARROW_HEAD / 3) + ',' + (MAIN_Y + ARROW_HEAD / 2),
                    fill: color,
                    opacity: hasFlow ? '0.7' : '0.3'
                }));
            }
        });
    }

    /* ── Render station nodes ──────────────────────────────── */

    function renderNodes(stations) {
        clearGroup(nodesGroup);
        var groups = groupStations(stations);

        groups.forEach(function (group) {
            var cx = nodeX(group.id);
            var cy = MAIN_Y;
            var hasOrders = group.orders.length > 0;

            // ── Main station ──
            if (hasOrders) {
                nodesGroup.appendChild(el('circle', {
                    cx: cx, cy: cy, r: NODE_R + 8,
                    fill: 'none', stroke: 'var(--status-production)',
                    'stroke-width': '3', class: 'pulse-ring', opacity: '0.4'
                }));
            }

            nodesGroup.appendChild(el('circle', {
                cx: cx, cy: cy, r: NODE_R,
                fill: hasOrders ? 'url(#nodeProduction)' : 'url(#nodeEmpty)',
                stroke: 'var(--border-color)', 'stroke-width': '2',
                filter: 'url(#softShadow)'
            }));

            nodesGroup.appendChild(el('text', {
                x: cx, y: cy - 5,
                'text-anchor': 'middle', 'dominant-baseline': 'central',
                fill: hasOrders ? 'white' : 'var(--text-secondary)',
                'font-size': '19', 'font-weight': '700'
            }, formatId(group.id)));

            var name = group.name || '';
            if (name.length > 10) name = name.substring(0, 9) + '…';
            nodesGroup.appendChild(el('text', {
                x: cx, y: cy + 13,
                'text-anchor': 'middle', 'dominant-baseline': 'central',
                fill: hasOrders ? 'rgba(255,255,255,0.85)' : 'var(--text-secondary)',
                'font-size': '9', 'font-weight': '500'
            }, name));

            // Badge
            if (hasOrders) {
                nodesGroup.appendChild(el('circle', {
                    cx: cx + NODE_R - 2, cy: cy - NODE_R + 2,
                    r: 14, fill: 'var(--error)', stroke: 'var(--bg-card)',
                    'stroke-width': '2', filter: 'url(#softShadow)'
                }));
                nodesGroup.appendChild(el('text', {
                    x: cx + NODE_R - 2, y: cy - NODE_R + 2,
                    'text-anchor': 'middle', 'dominant-baseline': 'central',
                    fill: 'white', 'font-size': '12', 'font-weight': '700'
                }, String(group.orders.length)));
            }

            // ── Sub-stations ──
            group.subs.forEach(function (sub, si) {
                var sx = cx + (si - (group.subs.length - 1) / 2) * 60;
                var sy = SUB_Y;
                var subHas = (sub.orders || []).length > 0;

                if (subHas) {
                    nodesGroup.appendChild(el('circle', {
                        cx: sx, cy: sy, r: SUB_NODE_R + 6,
                        fill: 'none', stroke: 'var(--status-production)',
                        'stroke-width': '2', class: 'pulse-ring', opacity: '0.3'
                    }));
                }

                nodesGroup.appendChild(el('circle', {
                    cx: sx, cy: sy, r: SUB_NODE_R,
                    fill: subHas ? 'url(#nodeProduction)' : 'url(#nodeEmpty)',
                    stroke: 'var(--status-buffer)', 'stroke-width': '1.5',
                    'stroke-dasharray': '4 3',
                    filter: 'url(#softShadow)'
                }));

                nodesGroup.appendChild(el('text', {
                    x: sx, y: sy - 4,
                    'text-anchor': 'middle', 'dominant-baseline': 'central',
                    fill: subHas ? 'white' : 'var(--text-secondary)',
                    'font-size': '15', 'font-weight': '700'
                }, formatId(sub.id)));

                var sName = sub.name || '';
                if (sName.length > 12) sName = sName.substring(0, 11) + '…';
                nodesGroup.appendChild(el('text', {
                    x: sx, y: sy + 11,
                    'text-anchor': 'middle', 'dominant-baseline': 'central',
                    fill: subHas ? 'rgba(255,255,255,0.85)' : 'var(--text-secondary)',
                    'font-size': '8', 'font-weight': '500'
                }, sName));

                // Badge
                if (subHas) {
                    nodesGroup.appendChild(el('circle', {
                        cx: sx + SUB_NODE_R - 2, cy: sy - SUB_NODE_R + 2,
                        r: 12, fill: 'var(--error)', stroke: 'var(--bg-card)',
                        'stroke-width': '2', filter: 'url(#softShadow)'
                    }));
                    nodesGroup.appendChild(el('text', {
                        x: sx + SUB_NODE_R - 2, y: sy - SUB_NODE_R + 2,
                        'text-anchor': 'middle', 'dominant-baseline': 'central',
                        fill: 'white', 'font-size': '11', 'font-weight': '700'
                    }, String(sub.orders.length)));
                }
            });
        });
    }

    /* ── Render order badges ───────────────────────────────── */

    function renderOrders(stations) {
        clearGroup(ordersGroup);
        var groups = groupStations(stations);

        groups.forEach(function (group) {
            // Main station orders
            if (group.orders.length > 0) {
                var cx = nodeX(group.id);
                var sx = cx - (group.orders.length - 1) * BADGE_GAP / 2;
                group.orders.forEach(function (order, i) {
                    renderOrderBadge(sx + i * BADGE_GAP, ORDERS_MAIN_Y, order);
                });
            }

            // Sub-station orders
            group.subs.forEach(function (sub) {
                var orders = sub.orders || [];
                if (orders.length === 0) return;
                var scx = nodeX(group.id) + (group.subs.indexOf(sub) - (group.subs.length - 1) / 2) * 60;
                var ssx = scx - (orders.length - 1) * BADGE_GAP / 2;
                orders.forEach(function (order, i) {
                    renderOrderBadge(ssx + i * BADGE_GAP, ORDERS_SUB_Y, order);
                });
            });
        });
    }

    function renderOrderBadge(bx, by, order) {
        var bw = BADGE_W, bh = BADGE_H;
        ordersGroup.appendChild(el('rect', {
            x: bx - bw / 2, y: by,
            width: bw, height: bh,
            rx: '5', fill: 'var(--bg-card)',
            stroke: 'var(--status-production)', 'stroke-width': '1.5',
            filter: 'url(#softShadow)'
        }));
        var num = (order.order_number || '').replace('ORD-', '');
        ordersGroup.appendChild(el('text', {
            x: bx, y: by + bh / 2,
            'text-anchor': 'middle', 'dominant-baseline': 'central',
            fill: 'var(--text-primary)', 'font-size': '10', 'font-weight': '600'
        }, num));

        var prod = order.product_code || '';
        if (prod.length > 8) prod = prod.substring(0, 7) + '…';
        ordersGroup.appendChild(el('text', {
            x: bx, y: by + bh + 11,
            'text-anchor': 'middle', 'dominant-baseline': 'central',
            fill: 'var(--text-secondary)', 'font-size': '8'
        }, prod));
    }

    /* ── ViewBox ───────────────────────────────────────────── */

    function updateViewBox(stations) {
        var totalWidth = FIRST_X + (stations.filter(function (s) { return !isSub(s.id); }).length) * MAIN_SPACING + 60;
        var totalHeight = 400;
        svg.setAttribute('viewBox', '0 0 ' + totalWidth + ' ' + totalHeight);
    }

    /* ── Main render ───────────────────────────────────────── */

    function render(stations) {
        stationData = stations;
        updateViewBox(stations);
        renderPipes(stations);
        renderNodes(stations);
        renderOrders(stations);
        loadStatistics();
    }

    /* ── Statistics ────────────────────────────────────────── */

    function loadStatistics() {
        MESUtils.fetchJson('/api/statistics', function (stats) {
            if (!stats) return;
            document.getElementById('statTotal').textContent = stats.total || 0;
            document.getElementById('statBuffer').textContent = stats.buffer || 0;
            document.getElementById('statProduction').textContent = stats.in_production || 0;
            document.getElementById('statCompleted').textContent = stats.completed || 0;
        });
    }

    /* ── Load data ─────────────────────────────────────────── */

    function loadData() {
        MESUtils.fetchJson('/api/stations', function (stations) {
            if (stations) render(stations);
        });
    }

    /* ── Init ──────────────────────────────────────────────── */

    document.addEventListener('DOMContentLoaded', function () {
        svg = document.getElementById('pipelineSvg');
        pipesGroup = document.getElementById('pipesGroup');
        nodesGroup = document.getElementById('nodesGroup');
        ordersGroup = document.getElementById('ordersGroup');

        loadData();
        window.MESRefresh.start(loadData, 3000);
    });
})();
