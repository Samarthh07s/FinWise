// Auto-dismiss messages after 5 seconds
document.addEventListener('DOMContentLoaded', function() {
    const messages = document.querySelectorAll('.alert');
    messages.forEach(function(message) {
        setTimeout(function() {
            message.style.animation = 'slideOut 0.3s';
            setTimeout(function() {
                message.remove();
            }, 300);
        }, 5000);
    });
});

// Animation for slide out
const style = document.createElement('style');
style.textContent = `
    @keyframes slideOut {
        to {
            transform: translateX(400px);
            opacity: 0;
        }
    }
`;
document.head.appendChild(style);
