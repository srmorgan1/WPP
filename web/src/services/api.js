import axios from 'axios';

const API_BASE_URL = 'http://localhost:8000';

// Create axios instance with default config
const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// API service functions
export const apiService = {
  // System
  async getSystemStatus() {
    const response = await api.get('/api/system/status');
    return response.data;
  },

  async getChargesDate() {
    const response = await api.get('/api/system/charges-date');
    return response.data;
  },

  // Database operations
  async updateDatabase(deleteExisting = true) {
    const response = await api.post('/api/database/update', {
      delete_existing: deleteExisting,
    });
    return response.data;
  },

  // Report operations
  async generateReports(reportDate) {
    const response = await api.post('/api/reports/generate', {
      report_date: reportDate,
    });
    return response.data;
  },

  // Task management
  async getTaskStatus(taskId) {
    const response = await api.get(`/api/tasks/${taskId}`);
    return response.data;
  },

  // File operations
  async getExcelData(filePath) {
    const response = await api.get(`/api/files/excel/${encodeURIComponent(filePath)}`);
    return response.data;
  },

  async getLogContent(filePath) {
    const response = await api.get(`/api/files/log/${encodeURIComponent(filePath)}`);
    return response.data;
  },
};

// WebSocket service
export class WebSocketService {
  constructor() {
    this.ws = null;
    this.reconnectInterval = null;
    this.heartbeatInterval = null;
    this.listeners = new Map();
    this.setupBrowserCloseHandlers();
  }

  connect() {
    try {
      this.ws = new WebSocket('ws://localhost:8000/ws');
      
      this.ws.onopen = () => {
        console.log('WebSocket connected');
        if (this.reconnectInterval) {
          clearInterval(this.reconnectInterval);
          this.reconnectInterval = null;
        }
        
        // Start heartbeat when connection is established
        this.startHeartbeat();
      };

      this.ws.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          this.notifyListeners(message.type, message);
        } catch (error) {
          console.error('Error parsing WebSocket message:', error);
        }
      };

      this.ws.onclose = () => {
        console.log('WebSocket disconnected');
        this.stopHeartbeat();
        this.scheduleReconnect();
      };

      this.ws.onerror = (error) => {
        console.error('WebSocket error:', error);
      };
    } catch (error) {
      console.error('Error connecting to WebSocket:', error);
      this.scheduleReconnect();
    }
  }

  scheduleReconnect() {
    if (!this.reconnectInterval) {
      this.reconnectInterval = setInterval(() => {
        console.log('Attempting to reconnect WebSocket...');
        this.connect();
      }, 5000);
    }
  }

  addListener(type, callback) {
    if (!this.listeners.has(type)) {
      this.listeners.set(type, []);
    }
    this.listeners.get(type).push(callback);
  }

  removeListener(type, callback) {
    if (this.listeners.has(type)) {
      const callbacks = this.listeners.get(type);
      const index = callbacks.indexOf(callback);
      if (index > -1) {
        callbacks.splice(index, 1);
      }
    }
  }

  notifyListeners(type, message) {
    if (this.listeners.has(type)) {
      this.listeners.get(type).forEach(callback => {
        try {
          callback(message);
        } catch (error) {
          console.error('Error in WebSocket listener:', error);
        }
      });
    }
  }

  send(message) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      try {
        this.ws.send(JSON.stringify(message));
      } catch (error) {
        console.error('Error sending WebSocket message:', error);
      }
    }
  }

  startHeartbeat() {
    // Clear any existing heartbeat
    this.stopHeartbeat();
    
    // Send initial heartbeat
    this.sendHeartbeat();
    
    // Set up 5-minute interval
    this.heartbeatInterval = setInterval(() => {
      this.sendHeartbeat();
    }, 5 * 60 * 1000); // 5 minutes
    
    console.log('Heartbeat started (5-minute interval)');
  }

  stopHeartbeat() {
    if (this.heartbeatInterval) {
      clearInterval(this.heartbeatInterval);
      this.heartbeatInterval = null;
      console.log('Heartbeat stopped');
    }
  }

  sendHeartbeat() {
    this.send({
      type: 'heartbeat',
      timestamp: new Date().toISOString(),
      page: window.location.pathname
    });
  }

  setupBrowserCloseHandlers() {
    // Handle page unload (tab/browser close, navigation away)
    window.addEventListener('beforeunload', () => {
      this.sendShutdownRequest();
    });
    
    // Handle visibility changes (tab switching, minimizing)
    document.addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'hidden') {
        // User switched away from tab - don't shutdown immediately
        // The heartbeat timeout will handle prolonged absence
      } else if (document.visibilityState === 'visible') {
        // User returned to tab - send immediate heartbeat
        this.sendHeartbeat();
      }
    });
  }

  sendShutdownRequest() {
    try {
      // Shutdown React/FastAPI server
      const xhr1 = new XMLHttpRequest();
      xhr1.open('POST', '/api/shutdown', false); // false = synchronous
      xhr1.setRequestHeader('Content-Type', 'application/json');
      xhr1.send(JSON.stringify({
        reason: 'browser_close',
        timestamp: new Date().toISOString()
      }));

      // Also try to shutdown Streamlit server if it's running on port 8501
      try {
        const xhr2 = new XMLHttpRequest();
        xhr2.open('POST', 'http://localhost:8502/wpp-shutdown', false);
        xhr2.setRequestHeader('Content-Type', 'application/json');
        xhr2.send(JSON.stringify({
          reason: 'browser_close_from_react'
        }));
      } catch (streamlitError) {
        // Streamlit server might not be running, that's okay
      }
    } catch (error) {
      console.error('Failed to send shutdown request:', error);
    }
  }

  disconnect() {
    this.stopHeartbeat();
    
    if (this.reconnectInterval) {
      clearInterval(this.reconnectInterval);
      this.reconnectInterval = null;
    }
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }
}

export const wsService = new WebSocketService();