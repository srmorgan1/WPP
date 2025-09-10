import React, { createContext, useContext, useState } from 'react';

const AppContext = createContext();

export const useAppContext = () => {
  const context = useContext(AppContext);
  if (!context) {
    throw new Error('useAppContext must be used within an AppContextProvider');
  }
  return context;
};

export const AppContextProvider = ({ children }) => {
  // Shared state for database page
  const [databasePageState, setDatabasePageState] = useState({
    results: null,
    issuesData: null,
    logContent: null,
    realtimeLog: [],
    progress: 0,
    progressMessage: '',
    status: 'pending',
    currentTask: null,
    isRunning: false
  });

  // Shared state for reports page
  const [reportsPageState, setReportsPageState] = useState({
    results: null,
    reportData: null,
    logContent: null,
    realtimeLog: [],
    progress: 0,
    progressMessage: '',
    status: 'pending',
    currentTask: null,
    isRunning: false
  });

  const updateDatabasePageState = (newState) => {
    setDatabasePageState(prev => ({ ...prev, ...newState }));
  };

  const updateReportsPageState = (newState) => {
    setReportsPageState(prev => ({ ...prev, ...newState }));
  };

  const resetDatabasePageState = () => {
    setDatabasePageState({
      results: null,
      issuesData: null,
      logContent: null,
      realtimeLog: [],
      progress: 0,
      progressMessage: '',
      status: 'pending',
      currentTask: null,
      isRunning: false
    });
  };

  const resetReportsPageState = () => {
    setReportsPageState({
      results: null,
      reportData: null,
      logContent: null,
      realtimeLog: [],
      progress: 0,
      progressMessage: '',
      status: 'pending',
      currentTask: null,
      isRunning: false
    });
  };

  return (
    <AppContext.Provider value={{
      databasePageState,
      reportsPageState,
      updateDatabasePageState,
      updateReportsPageState,
      resetDatabasePageState,
      resetReportsPageState
    }}>
      {children}
    </AppContext.Provider>
  );
};