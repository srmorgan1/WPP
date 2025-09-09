import React, { createContext, useContext, useState, useEffect } from 'react';
import { onConnectionStatusChange } from '../services/api';

// Create the context
const ConnectionContext = createContext();

// Custom hook to use the connection context
export const useConnection = () => {
  const context = useContext(ConnectionContext);
  if (!context) {
    throw new Error('useConnection must be used within a ConnectionProvider');
  }
  return context;
};

// Provider component
export const ConnectionProvider = ({ children }) => {
  const [isConnected, setIsConnected] = useState(true); // Start optimistically
  const [connectionError, setConnectionError] = useState(null);
  const [showErrorOverlay, setShowErrorOverlay] = useState(false);
  
  useEffect(() => {
    // Register for connection status changes from:
    // 1. Existing WebSocket heartbeat failures (passive timeout)
    // 2. API call failures when user clicks buttons (active interaction)
    const unsubscribe = onConnectionStatusChange((connected, error) => {
      setIsConnected(connected);
      setConnectionError(error);
      
      // Show overlay on connection loss, hide on recovery
      if (!connected) {
        setShowErrorOverlay(true);
      } else {
        setShowErrorOverlay(false);
        setConnectionError(null);
      }
    });

    return unsubscribe; // Cleanup connection status listener
  }, []);

  const handleRetry = () => {
    // Hide overlay temporarily while retrying
    setShowErrorOverlay(false);
    setConnectionError(null);
    
    // Make a test request to check connectivity
    fetch('/api/system/status')
      .then(() => {
        // Success - connection restored
        setIsConnected(true);
        setShowErrorOverlay(false);
      })
      .catch((error) => {
        // Still failing - show overlay again
        setIsConnected(false);
        setConnectionError(error);
        setShowErrorOverlay(true);
      });
  };

  const hideErrorOverlay = () => {
    setShowErrorOverlay(false);
  };

  const value = {
    isConnected,
    connectionError,
    showErrorOverlay,
    handleRetry,
    hideErrorOverlay,
  };

  return (
    <ConnectionContext.Provider value={value}>
      {children}
    </ConnectionContext.Provider>
  );
};