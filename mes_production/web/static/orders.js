/* MES Production System - Orders Page Logic */

(function() {
    const API_BASE = '';
    
    let currentFilter = 'all';
    let allOrders = [];
    
    // Modal handling
    function openModal(modalId) {
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.classList.add('active');
        }
    }
    
    function closeModal(modalId) {
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.classList.remove('active');
        }
    }
    
    // Create order form
    function setupCreateOrderForm() {
        const form = document.getElementById('createOrderForm');
        const modal = document.getElementById('createOrderModal');
        
        if (!form || !modal) return;
        
        form.addEventListener('submit', async function(e) {
            e.preventDefault();
            
            const formData = new FormData(form);
            const data = {
                batch: formData.get('batch'),
                product_code: formData.get('product_code'),
                color: formData.get('color'),
                quantity: parseInt(formData.get('quantity'))
            };
            
            try {
                const response = await fetch(`${API_BASE}/api/orders`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(data)
                });
                
                const result = await response.json();
                
                if (response.ok) {
                    const count = result.count || 1;
                    window.MESUtils.showToast(`Создано ${count} заказ(ов)`, 'success');
                    closeModal('createOrderModal');
                    form.reset();
                    loadOrders();
                } else {
                    window.MESUtils.showToast(result.error || 'Ошибка создания заказа', 'error');
                }
            } catch (error) {
                window.MESUtils.showToast('Ошибка соединения с сервером', 'error');
                console.error(error);
            }
        });
    }
    
    // Load and display orders
    async function loadOrders() {
        const tableBody = document.getElementById('ordersTableBody');
        if (!tableBody) return;
        
        try {
            const url = currentFilter === 'all' 
                ? `${API_BASE}/api/orders`
                : `${API_BASE}/api/orders?status=${currentFilter}`;
            
            const response = await fetch(url);
            allOrders = await response.json();
            
            renderOrders(allOrders);
            loadStatistics();
        } catch (error) {
            window.MESUtils.showToast('Ошибка загрузки заказов', 'error');
            console.error(error);
        }
    }
    
    async function loadStatistics() {
        try {
            const response = await fetch(`${API_BASE}/api/statistics`);
            const stats = await response.json();
            
            document.getElementById('statTotal').textContent = stats.total || 0;
            document.getElementById('statBuffer').textContent = stats.buffer || 0;
            document.getElementById('statProduction').textContent = stats.in_production || 0;
            document.getElementById('statCompleted').textContent = stats.completed || 0;
        } catch (error) {
            console.error('Error loading statistics:', error);
        }
    }
    
    function renderOrders(orders) {
        const tableBody = document.getElementById('ordersTableBody');
        if (!tableBody) return;
        
        if (orders.length === 0) {
            tableBody.innerHTML = '<tr><td colspan="10" style="text-align:center;">Нет заказов</td></tr>';
            return;
        }
        
        tableBody.innerHTML = orders.map(order => `
            <tr>
                <td>${escapeHtml(order.batch)}</td>
                <td>${escapeHtml(order.order_number)}</td>
                <td>${escapeHtml(order.product_code)}</td>
                <td>${escapeHtml(order.color)}</td>
                <td>${order.quantity}</td>
                <td>${window.MESUtils.getStatusBadge(order.status)}</td>
                <td>${window.MESUtils.getStationName(order.current_station)}</td>
                <td>${window.MESUtils.formatDate(order.created_at)}</td>
                <td>${window.MESUtils.formatDate(order.started_at)}</td>
                <td>${window.MESUtils.formatDate(order.completed_at)}</td>
                <td>
                    <div class="action-buttons">
                        ${renderActionButtons(order)}
                    </div>
                </td>
            </tr>
        `).join('');
    }
    
    function renderActionButtons(order) {
        const buttons = [];
        
        if (order.status === 'buffer') {
            buttons.push(`
                <button class="btn btn-primary btn-sm" onclick="MESOrders.launchOrder(${order.id})">
                    Запустить
                </button>
            `);
        }
        
        if (order.status === 'production') {
            buttons.push(`
                <button class="btn btn-secondary btn-sm" onclick="MESOrders.moveOrder(${order.id})">
                    Переместить
                </button>
                <button class="btn btn-success btn-sm" onclick="MESOrders.completeOrder(${order.id})">
                    Завершить
                </button>
            `);
        }
        
        if (order.status === 'buffer' || order.status === 'production') {
            buttons.push(`
                <button class="btn btn-danger btn-sm" onclick="MESOrders.cancelOrder(${order.id})">
                    Отменить
                </button>
            `);
        }
        
        return buttons.join('');
    }
    
    function escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    // Order actions
    async function launchOrder(orderId) {
        if (!confirm('Запустить заказ в производство?')) return;
        
        try {
            const response = await fetch(`${API_BASE}/api/orders/${orderId}/launch`, {
                method: 'POST'
            });
            
            const result = await response.json();
            
            if (result.success) {
                window.MESUtils.showToast('Заказ запущен в производство', 'success');
                loadOrders();
            } else {
                window.MESUtils.showToast(result.message || 'Ошибка запуска', 'error');
            }
        } catch (error) {
            window.MESUtils.showToast('Ошибка соединения с сервером', 'error');
        }
    }
    
    async function moveOrder(orderId) {
        if (!confirm('Переместить заказ на следующую станцию?')) return;
        
        try {
            const response = await fetch(`${API_BASE}/api/orders/${orderId}/move`, {
                method: 'POST'
            });
            
            const result = await response.json();
            
            if (result.success) {
                window.MESUtils.showToast(result.message || 'Заказ перемещён', 'success');
                loadOrders();
            } else {
                window.MESUtils.showToast(result.message || 'Ошибка перемещения', 'error');
            }
        } catch (error) {
            window.MESUtils.showToast('Ошибка соединения с сервером', 'error');
        }
    }
    
    async function completeOrder(orderId) {
        if (!confirm('Завершить заказ досрочно?')) return;
        
        try {
            const response = await fetch(`${API_BASE}/api/orders/${orderId}/complete`, {
                method: 'POST'
            });
            
            const result = await response.json();
            
            if (result.success) {
                window.MESUtils.showToast('Заказ завершён', 'success');
                loadOrders();
            } else {
                window.MESUtils.showToast(result.message || 'Ошибка завершения', 'error');
            }
        } catch (error) {
            window.MESUtils.showToast('Ошибка соединения с сервером', 'error');
        }
    }
    
    async function cancelOrder(orderId) {
        if (!confirm('Отменить заказ? Это действие нельзя отменить.')) return;
        
        try {
            const response = await fetch(`${API_BASE}/api/orders/${orderId}/cancel`, {
                method: 'POST'
            });
            
            const result = await response.json();
            
            if (result.success) {
                window.MESUtils.showToast('Заказ отменён', 'success');
                loadOrders();
            } else {
                window.MESUtils.showToast(result.message || 'Ошибка отмены', 'error');
            }
        } catch (error) {
            window.MESUtils.showToast('Ошибка соединения с сервером', 'error');
        }
    }
    
    // Filter handling
    function setupFilter() {
        const filterSelect = document.getElementById('statusFilter');
        if (!filterSelect) return;
        
        filterSelect.addEventListener('change', function() {
            currentFilter = this.value;
            loadOrders();
        });
    }
    
    // Initialize
    document.addEventListener('DOMContentLoaded', function() {
        setupCreateOrderForm();
        setupFilter();
        
        // Start auto-refresh
        window.MESRefresh.start(loadOrders, 3000);
    });
    
    // Expose to global scope
    window.MESOrders = {
        launchOrder,
        moveOrder,
        completeOrder,
        cancelOrder,
        openModal,
        closeModal,
        loadOrders
    };
})();
