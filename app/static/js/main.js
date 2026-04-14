/**
 * 公共 JavaScript 代码
 * 处理一些全局的交互效果
 */

// Flash 消息 5 秒后自动消失
document.addEventListener('DOMContentLoaded', function() {
    setTimeout(function() {
        var alerts = document.querySelectorAll('.alert-dismissible');
        alerts.forEach(function(alert) {
            var bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
        });
    }, 5000);
});
