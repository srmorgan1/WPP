/**
 * Simple localStorage-based shutdown mechanism for WPP
 * Uses browser events and localStorage to signal shutdown to Python
 */

class SimpleShutdownManager {
    constructor() {
        this.isShuttingDown = false;
        this.heartbeatInterval = null;
        this.sessionId = 'wpp_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
        
        console.log('🚀 SimpleShutdownManager initialized with session ID:', this.sessionId);
        this.setupEventListeners();
        this.startHeartbeat();
        
        // Clear any old shutdown signals
        localStorage.removeItem('wpp_shutdown_signal');
        localStorage.setItem('wpp_session_id', this.sessionId);
    }

    setupEventListeners() {
        // Handle page close/reload
        window.addEventListener('beforeunload', (e) => {
            console.log('🚪 Before unload - triggering shutdown');
            this.triggerShutdown('page_beforeunload');
        });

        window.addEventListener('unload', (e) => {
            console.log('🚪 Page unload - triggering shutdown');
            this.triggerShutdown('page_unload');
        });

        // Handle visibility changes (tab switching, closing)
        document.addEventListener('visibilitychange', () => {
            if (document.hidden) {
                console.log('👁️ Page hidden - stopping heartbeat');
                this.stopHeartbeat();
                // Set a timer - if page stays hidden for 10 seconds, assume it's closed
                setTimeout(() => {
                    if (document.hidden && !this.isShuttingDown) {
                        console.log('🚪 Page hidden for 10s - assuming closure');
                        this.triggerShutdown('page_hidden_timeout');
                    }
                }, 10000);
            } else {
                console.log('👁️ Page visible - resuming heartbeat');
                this.startHeartbeat();
            }
        });

        // Handle page focus/blur
        window.addEventListener('focus', () => {
            console.log('👁️ Window focused');
            if (!this.heartbeatInterval && !this.isShuttingDown) {
                this.startHeartbeat();
            }
        });
    }

    startHeartbeat() {
        if (this.heartbeatInterval) {
            clearInterval(this.heartbeatInterval);
        }
        
        // Send heartbeat every 5 seconds
        this.heartbeatInterval = setInterval(() => {
            if (!this.isShuttingDown) {
                this.sendHeartbeat();
            }
        }, 5000);
        
        // Send initial heartbeat
        this.sendHeartbeat();
    }

    stopHeartbeat() {
        if (this.heartbeatInterval) {
            clearInterval(this.heartbeatInterval);
            this.heartbeatInterval = null;
        }
    }

    sendHeartbeat() {
        const timestamp = Date.now();
        console.log(`💓 Heartbeat at ${new Date(timestamp).toLocaleTimeString()}`);
        
        const heartbeatData = {
            type: 'heartbeat',
            sessionId: this.sessionId,
            timestamp: timestamp,
            url: window.location.href,
            visible: !document.hidden
        };
        
        localStorage.setItem('wpp_heartbeat', JSON.stringify(heartbeatData));
    }

    triggerShutdown(reason) {
        if (this.isShuttingDown) return;
        
        this.isShuttingDown = true;
        this.stopHeartbeat();
        
        console.log(`🚪 Triggering shutdown: ${reason}`);
        
        const shutdownData = {
            type: 'shutdown',
            sessionId: this.sessionId,
            reason: reason,
            timestamp: Date.now(),
            url: window.location.href
        };
        
        // Write shutdown signal to localStorage
        localStorage.setItem('wpp_shutdown_signal', JSON.stringify(shutdownData));
        
        console.log('📝 Shutdown signal written to localStorage');
    }
}

// Auto-initialize when script loads
let shutdownManager;
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        shutdownManager = new SimpleShutdownManager();
    });
} else {
    shutdownManager = new SimpleShutdownManager();
}

// Make it available globally for manual shutdown
window.shutdownWPP = function() {
    if (shutdownManager) {
        shutdownManager.triggerShutdown('manual_shutdown');
    }
};