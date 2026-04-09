/* MES Production System - Main Frontend Logic */

(function() {
    const API_BASE = '';
    
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
    
    // Expose utilities globally
    window.MESUtils = {
        showToast,
        formatDate,
        getStatusBadge,
        getStationName
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
