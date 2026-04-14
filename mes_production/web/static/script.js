/* MES Production System - Main Frontend Logic */

(function() {
    const API_BASE = '';
    
    // Get API key from meta tag (set by server template)
    function getApiKey() {
        const meta = document.querySelector('meta[name="api-key"]');
        return meta ? meta.content : null;
    }
    
    // Build headers for API requests
    function authHeaders(extraHeaders = {}) {
        const headers = { ...extraHeaders };
        const apiKey = getApiKey();
        if (apiKey) {
            headers['X-API-Key'] = apiKey;
        }
        return headers;
    }
    
    // Utility functions
    function showToast(message, type = 'info') {
        const container = document.getElementById('toastContainer');
        if (!container) return;
        
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        toast.textContent = message;
        container.appendChild(toast);
        
        setTimeout(() => {
            toast.remove();
        }, 3000);
    }
    
    function formatDate(dateString) {
        if (!dateString) return '-';
        const date = new Date(dateString);
        return date.toLocaleString('ru-RU', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit'
        });
    }
    
    function getStatusBadge(status) {
        const statusMap = {
            'buffer': 'badge-buffer',
            'production': 'badge-production',
            'completed': 'badge-completed',
            'cancelled': 'badge-cancelled'
        };
        const statusLabels = {
            'buffer': 'Буфер',
            'production': 'В производстве',
            'completed': 'Завершён',
            'cancelled': 'Отменён'
        };
        return `<span class="badge ${statusMap[status] || ''}">${statusLabels[status] || status}</span>`;
    }
    
    function getStationName(stationId) {
        const stations = [
            'Приёмка', 'Сортировка', 'Подготовка', 'Сборка', 'Пайка',
            'Контроль', 'Тестирование', 'Упаковка', 'Маркировка', 'Отгрузка'
        ];
        return stationId ? stations[stationId - 1] || `Станция ${stationId}` : '-';
    }
    
    // Escape HTML to prevent XSS
    function escapeHtml(text) {
        var div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // Generic JSON fetch helper
    function fetchJson(url, callback) {
        fetch(url)
            .then(function (r) { return r.json(); })
            .then(function (data) { callback(data); })
            .catch(function () { callback(null); });
    }

    // Expose utilities globally
    window.MESUtils = {
        showToast,
        formatDate,
        getStatusBadge,
        getStationName,
        getApiKey,
        authHeaders,
        fetchJson,
        escapeHtml
    };
    
    // Auto-refresh functionality
    let refreshInterval = null;
    
    window.MESRefresh = {
        start: function(callback, interval = 3000) {
            if (refreshInterval) clearInterval(refreshInterval);
            callback();
            refreshInterval = setInterval(callback, interval);
        },
        stop: function() {
            if (refreshInterval) {
                clearInterval(refreshInterval);
                refreshInterval = null;
            }
        }
    };
})();
