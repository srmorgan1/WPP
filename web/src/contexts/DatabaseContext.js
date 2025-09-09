import React, { createContext, useContext, useState } from 'react';

// Create the context
const DatabaseContext = createContext();

// Custom hook to use the database context
export const useDatabase = () => {
  const context = useContext(DatabaseContext);
  if (!context) {
    throw new Error('useDatabase must be used within a DatabaseProvider');
  }
  return context;
};

// Provider component
export const DatabaseProvider = ({ children }) => {
  // State for database update results
  const [databaseResults, setDatabaseResults] = useState(null);
  const [issuesData, setIssuesData] = useState(null);
  const [logContent, setLogContent] = useState(null);
  const [realtimeLog, setRealtimeLog] = useState([]);

  // State for current operation
  const [isRunning, setIsRunning] = useState(false);
  const [progress, setProgress] = useState(0);
  const [progressMessage, setProgressMessage] = useState('');
  const [status, setStatus] = useState('pending');
  const [currentTask, setCurrentTask] = useState(null);

  // Clear all data
  const clearDatabaseData = () => {
    setDatabaseResults(null);
    setIssuesData(null);
    setLogContent(null);
    setRealtimeLog([]);
    setProgress(0);
    setProgressMessage('');
    setStatus('pending');
    setCurrentTask(null);
  };

  // Update results
  const updateDatabaseResults = (results) => {
    setDatabaseResults(results);
  };

  // Update issues data
  const updateIssuesData = (data) => {
    setIssuesData(data);
  };

  // Update log content
  const updateLogContent = (content) => {
    setLogContent(content);
  };

  // Add to realtime log
  const addRealtimeLogEntry = (entry) => {
    setRealtimeLog(prev => [...prev, entry]);
  };

  // Clear realtime log
  const clearRealtimeLog = () => {
    setRealtimeLog([]);
  };

  // Context value
  const value = {
    // Data
    databaseResults,
    issuesData,
    logContent,
    realtimeLog,

    // Operation state
    isRunning,
    progress,
    progressMessage,
    status,
    currentTask,

    // Actions
    clearDatabaseData,
    updateDatabaseResults,
    updateIssuesData,
    updateLogContent,
    addRealtimeLogEntry,
    clearRealtimeLog,

    // Setters for operation state
    setIsRunning,
    setProgress,
    setProgressMessage,
    setStatus,
    setCurrentTask,
  };

  return (
    <DatabaseContext.Provider value={value}>
      {children}
    </DatabaseContext.Provider>
  );
};