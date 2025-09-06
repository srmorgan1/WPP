/**
 * WPP Application Lifecycle Management
 * Handles page close detection and server shutdown using file-based communication
 */

class AppLifecycleManager {
    constructor() {
        this.isShuttingDown = false;
        this.heartbeatInterval = null;
        this.visibilityTimer = null;
        this.apiPort = window.WPP_API_PORT;
        
        if (!this.apiPort) {
            console.error('❌ WPP_API_PORT not set - API server may not be running');
            console.log('Will retry finding API port in 2 seconds...');
            setTimeout(() => {
                this.apiPort = window.WPP_API_PORT || 8503;
                console.log(`Retry: Using API port: ${this.apiPort}`);
                if (this.apiPort) {
                    this.startHeartbeat();
                }
            }, 2000);
        } else {
            console.log(`AppLifecycleManager initialized with API port: ${this.apiPort}`);
        }
        
        this.setupEventListeners();
        this.registerPageLoad();
        
        // Only start heartbeat if we have a port
        if (this.apiPort) {
            this.startHeartbeat();
        }
    }

    /**
     * Setup event listeners for page lifecycle events
     */
    setupEventListeners() {
        // Handle page close/reload - most reliable for actual page closing
        window.addEventListener('beforeunload', (e) => {
            console.log('Before unload event triggered');
            this.handlePageClose();
        });

        // Handle page unload - backup for page close with immediate beacon
        window.addEventListener('unload', (e) => {
            console.log('Unload event triggered - using beacon for immediate shutdown');
            // Use beacon for immediate delivery during unload
            if (navigator.sendBeacon) {
                const data = JSON.stringify({ 
                    reason: 'unload_event', 
                    timestamp: Date.now(),
                    immediate: true
                });
                navigator.sendBeacon(`http://localhost:${this.apiPort}/wpp-shutdown`, data);
            }
            this.handlePageClose();
        });

        // Handle page visibility change (tab switching, minimizing, closing)
        document.addEventListener('visibilitychange', () => {
            if (document.hidden) {
                console.log('Page visibility changed to hidden - pausing heartbeats');
                // Stop heartbeats when hidden to let server timeout handle it
                this.stopHeartbeat();
            } else {
                console.log('Page visibility changed to visible - resuming heartbeats');
                // Cancel any closure detection timer
                if (this.visibilityTimer) {
                    clearTimeout(this.visibilityTimer);
                    this.visibilityTimer = null;
                }
                // Resume heartbeats immediately
                if (!this.isShuttingDown) {
                    this.startHeartbeat();
                }
            }
        });

        // Handle manual shutdown button
        window.addEventListener('wpp-shutdown', (e) => {
            this.forceShutdown();
        });

        // Additional detection: focus/blur events
        window.addEventListener('blur', () => {
            console.log('Window blur event');
        });

        window.addEventListener('focus', () => {
            console.log('Window focus event');
        });
    }

    /**
     * Register that the page has loaded
     */
    registerPageLoad() {
        this.sendShutdownSignal('page_loaded');
        
        // Test API connectivity after a short delay to ensure server is fully started
        setTimeout(() => {
            this.testAPIConnectivity();
        }, 1000);
    }
    
    /**
     * Test if the shutdown API server is reachable
     */
    testAPIConnectivity() {
        console.log(`🔍 Testing API connectivity on port ${this.apiPort}...`);
        
        // First try a simple GET request to test basic connectivity
        fetch(`http://localhost:${this.apiPort}/wpp-status`, {
            method: 'GET',
            timeout: 5000
        }).then(response => {
            if (response.ok) {
                console.log(`✅ API server is reachable on port ${this.apiPort} (GET test)`);
                return response.json();
            } else {
                console.error(`❌ API server GET test failed: ${response.status}`);
                throw new Error(`HTTP ${response.status}`);
            }
        }).then(data => {
            console.log('API GET test response:', data);
            
            // If GET works, try POST heartbeat
            return fetch(`http://localhost:${this.apiPort}/wpp-heartbeat`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ 
                    type: 'connectivity_test',
                    timestamp: Date.now()
                })
            });
        }).then(response => {
            if (response && response.ok) {
                console.log(`✅ API server POST heartbeat test successful`);
                return response.json();
            } else if (response) {
                console.error(`❌ API server POST test failed: ${response.status}`);
                throw new Error(`HTTP ${response.status}`);
            }
        }).then(data => {
            if (data) {
                console.log('API POST test response:', data);
            }
        }).catch(error => {
            console.error(`❌ API server is NOT reachable on port ${this.apiPort}:`, error);
            console.error('The shutdown API server may not be running properly');
            console.error('Check the server console for API startup messages');
        });
    }

    /**
     * Handle page close event
     */
    handlePageClose() {
        if (this.isShuttingDown) return;
        
        this.isShuttingDown = true;
        this.stopHeartbeat();
        
        // Clean up visibility timer
        if (this.visibilityTimer) {
            clearTimeout(this.visibilityTimer);
            this.visibilityTimer = null;
        }
        
        console.log('🚪 Page closing, sending shutdown signal...');

        // Try multiple shutdown approaches
        this.sendShutdownSignal('page_closed');
        this.sendShutdownViaBeacon('page_closed_beacon');
        this.sendShutdownViaImage('page_closed_image');
    }

    /**
     * Send shutdown signal via API call to shutdown server
     */
    sendShutdownSignal(reason) {
        try {
            console.log(`📡 Sending shutdown signal via fetch: ${reason}`);
            // Use fetch with keepalive to ensure it's sent even during page close
            fetch(`http://localhost:${this.apiPort}/wpp-shutdown`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ 
                    reason: reason, 
                    timestamp: Date.now(),
                    user_agent: navigator.userAgent
                }),
                keepalive: true
            }).then(response => {
                console.log(`✅ Shutdown signal sent successfully: ${response.status}`);
            }).catch((error) => {
                console.log('❌ Primary shutdown API failed:', error);
            });
        } catch (error) {
            console.log('❌ Error sending shutdown signal:', error);
        }
    }

    /**
     * Send shutdown via beacon (more reliable during page close)
     */
    sendShutdownViaBeacon(reason) {
        try {
            console.log(`📡 Sending shutdown signal via beacon: ${reason}`);
            if (navigator.sendBeacon) {
                const data = JSON.stringify({ reason: reason, timestamp: Date.now() });
                const success = navigator.sendBeacon(`http://localhost:${this.apiPort}/wpp-shutdown`, data);
                console.log(`${success ? '✅' : '❌'} Beacon shutdown signal: ${success ? 'sent' : 'failed'}`);
                return success;
            }
        } catch (error) {
            console.log('❌ Error sending beacon shutdown:', error);
        }
        return false;
    }

    /**
     * Send shutdown via image request (fallback method)
     */
    sendShutdownViaImage(reason) {
        try {
            console.log(`📡 Sending shutdown signal via image: ${reason}`);
            const img = new Image();
            img.onload = () => console.log('✅ Image shutdown signal sent');
            img.onerror = () => console.log('❌ Image shutdown signal failed');
            img.src = `http://localhost:${this.apiPort}/wpp-shutdown?reason=${encodeURIComponent(reason)}&timestamp=${Date.now()}`;
        } catch (error) {
            console.log('❌ Error sending image shutdown:', error);
        }
    }

    /**
     * Start sending periodic heartbeats to keep server alive
     */
    startHeartbeat() {
        // Send heartbeat every 10 seconds (server timeout is 30 seconds, so plenty of margin)
        this.heartbeatInterval = setInterval(() => {
            if (!this.isShuttingDown) {
                this.sendHeartbeat();
            }
        }, 10000);
        
        // Send initial heartbeat immediately
        this.sendHeartbeat();
    }

    /**
     * Send heartbeat to server
     */
    sendHeartbeat() {
        const timestamp = Date.now();
        console.log(`Sending heartbeat to http://localhost:${this.apiPort}/wpp-heartbeat at ${new Date(timestamp).toLocaleTimeString()}`);
        
        try {
            fetch(`http://localhost:${this.apiPort}/wpp-heartbeat`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ 
                    timestamp: timestamp,
                    type: 'heartbeat',
                    url: window.location.href,
                    visible: !document.hidden
                }),
                timeout: 5000  // 5 second timeout
            }).then(response => {
                if (response.ok) {
                    console.log(`✅ Heartbeat acknowledged at ${new Date().toLocaleTimeString()}`);
                    return response.json();
                } else {
                    console.error(`❌ Heartbeat response not OK: ${response.status} ${response.statusText}`);
                    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                }
            }).then(data => {
                console.log('Heartbeat response data:', data);
            }).catch((error) => {
                console.error('❌ Heartbeat failed:', error);
                console.error('This could indicate:');
                console.error(`  1. API server not running on port ${this.apiPort}`);
                console.error('  2. CORS issues');
                console.error('  3. Network connectivity problems');
            });
        } catch (error) {
            console.error('❌ Heartbeat error (outer catch):', error);
        }
    }

    /**
     * Stop heartbeat when shutting down
     */
    stopHeartbeat() {
        if (this.heartbeatInterval) {
            clearInterval(this.heartbeatInterval);
            this.heartbeatInterval = null;
        }
    }

    /**
     * Force shutdown (for manual triggers)
     */
    forceShutdown() {
        this.isShuttingDown = true;
        this.stopHeartbeat();
        this.sendShutdownSignal('manual_shutdown');
        
        // Give server a moment to process
        setTimeout(() => {
            window.close();
        }, 500);
    }
}

/**
 * Initialize the app lifecycle manager
 */
function initializeAppLifecycle() {
    console.log('🚀 Initializing WPP App Lifecycle Manager...');
    window.appLifecycle = new AppLifecycleManager();
    console.log('✅ App lifecycle management initialized');
    
    // Test if API port is available
    if (window.WPP_API_PORT) {
        console.log(`✅ WPP_API_PORT is set to: ${window.WPP_API_PORT}`);
    } else {
        console.warn('⚠️  WPP_API_PORT is not set - this may cause issues');
    }
}

/**
 * Get the current lifecycle manager instance
 */
function getAppLifecycle() {
    return window.appLifecycle;
}

/**
 * Manually trigger app shutdown
 */
function shutdownApp() {
    if (window.appLifecycle) {
        window.appLifecycle.forceShutdown();
    } else {
        console.warn('App lifecycle manager not initialized');
    }
}

// Auto-initialize when script loads
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeAppLifecycle);
} else {
    initializeAppLifecycle();
}