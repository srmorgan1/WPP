import React, { useState, useEffect } from 'react';
import { apiService, wsService } from '../services/api';
import ProgressBar from '../components/ProgressBar';
import DataTable from '../components/DataTable';
import LogViewer from '../components/LogViewer';
import { useAppContext } from '../contexts/AppContext';

const DatabasePage = () => {
  const { databasePageState, updateDatabasePageState } = useAppContext();
  const [deleteExisting, setDeleteExisting] = useState(true);
  const logViewerRef = React.useRef(null);
  
  // Destructure state from context
  const {
    results,
    issuesData,
    logContent,
    realtimeLog,
    progress,
    progressMessage,
    status,
    currentTask,
    isRunning
  } = databasePageState;

  useEffect(() => {
    // Connect WebSocket for real-time updates
    wsService.connect();
    
    const handleProgress = (message) => {
      if (message.task_id === currentTask) {
        updateDatabasePageState({
          progress: message.data.progress || 0,
          progressMessage: message.data.message || '',
          status: message.data.status || 'running'
        });
        
        // Accumulate log messages for scrolling display
        if (message.data.message) {
          const timestamp = new Date().toLocaleTimeString();
          const logEntry = `[${timestamp}] ${message.data.message}`;
          updateDatabasePageState({
            realtimeLog: [...realtimeLog, logEntry]
          });
        }
        
        if (message.data.status === 'completed') {
          updateDatabasePageState({
            progress: 100,
            isRunning: false
          });
          loadTaskResults(message.task_id);
        } else if (message.data.status === 'failed') {
          updateDatabasePageState({ isRunning: false });
          loadTaskResults(message.task_id);
        }
      }
    };

    wsService.addListener('progress', handleProgress);
    
    return () => {
      wsService.removeListener('progress', handleProgress);
    };
  }, [currentTask]);

  // Auto-scroll log viewer to bottom when new messages arrive
  React.useEffect(() => {
    if (logViewerRef.current) {
      logViewerRef.current.scrollTop = logViewerRef.current.scrollHeight;
    }
  }, [realtimeLog]);

  const handleUpdateDatabase = async () => {
    try {
      updateDatabasePageState({
        isRunning: true,
        progress: 0,
        progressMessage: 'Starting database update...',
        status: 'running',
        results: null,
        issuesData: null,
        logContent: null,
        realtimeLog: []
      });

      const response = await apiService.updateDatabase(deleteExisting);
      updateDatabasePageState({ currentTask: response.task_id });
    } catch (error) {
      console.error('Error starting database update:', error);
      updateDatabasePageState({
        isRunning: false,
        status: 'failed',
        progressMessage: `Error: ${error.message}`
      });
    }
  };

  const loadTaskResults = async (taskId) => {
    try {
      const taskResult = await apiService.getTaskStatus(taskId);
      updateDatabasePageState({ results: taskResult });

      // Check for web_sheets data directly in the task result (new system)
      if (taskResult.result_data?.summary?.web_sheets) {
        // Convert web_sheets to the format expected by DataTable component
        const webSheets = taskResult.result_data.summary.web_sheets;
        const convertedData = {
          file_info: {
            name: 'Data Import Issues',
            created_at: taskResult.completed_at || taskResult.started_at
          },
          sheets: Object.entries(webSheets).map(([sheetName, sheet]) => ({
            sheet_name: sheetName,
            columns: sheet.columns,
            data: sheet.data.map(row => sheet.columns.map(col => row[col] || '')),
            is_critical: sheet.is_critical || false
          }))
        };
        updateDatabasePageState({ issuesData: convertedData });
      }

      // Load files if available (legacy system)
      if (taskResult.result_data?.files) {
        for (const fileRef of taskResult.result_data.files) {
          try {
            if (fileRef.file_type === 'excel') {
              const issuesData = await apiService.getExcelData(fileRef.filename);
              updateDatabasePageState({ issuesData });
            } else if (fileRef.file_type === 'log') {
              const logData = await apiService.getLogContent(fileRef.filename);
              updateDatabasePageState({ logContent: logData.content });
            }
          } catch (error) {
            console.error(`Error loading ${fileRef.file_type} file ${fileRef.filename}:`, error);
          }
        }
      }
    } catch (error) {
      console.error('Error loading task results:', error);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="card p-6">
        <h2 className="text-2xl font-bold text-gray-900 mb-4">
          🔄 Database Update
        </h2>
        <p className="text-gray-600">
          Process source files and update the database with latest data
        </p>
      </div>

      {/* Configuration */}
      <div className="card p-6">
        <h3 className="text-lg font-medium text-gray-900 mb-4">
          Configuration
        </h3>
        <div className="flex items-center space-x-3">
          <input
            type="checkbox"
            id="deleteExisting"
            checked={deleteExisting}
            onChange={(e) => setDeleteExisting(e.target.checked)}
            disabled={isRunning}
            className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
          />
          <label htmlFor="deleteExisting" className="text-sm text-gray-700">
            Delete existing database before update
          </label>
        </div>
      </div>

      {/* Action */}
      <div className="card p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-medium text-gray-900">
            Execute Update
          </h3>
          <button
            onClick={handleUpdateDatabase}
            disabled={isRunning}
            className="btn-primary"
          >
            {isRunning ? (
              <>
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2" />
                Updating...
              </>
            ) : (
              'Update Database'
            )}
          </button>
        </div>

        {/* Progress */}
        {(isRunning || progress > 0) && (
          <ProgressBar
            progress={progress}
            message={progressMessage}
            status={status}
          />
        )}

        {/* Real-time Log Display */}
        {(isRunning || realtimeLog.length > 0) && (
          <div className="mt-4">
            <h4 className="text-sm font-medium text-gray-700 mb-2">
              Process Log
            </h4>
            <div 
              ref={logViewerRef}
              className="bg-gray-900 text-green-400 p-4 rounded-md h-32 overflow-y-auto font-mono text-xs"
            >
              {realtimeLog.length === 0 ? (
                <div className="text-gray-500">Waiting for log messages...</div>
              ) : (
                realtimeLog.map((logLine, index) => (
                  <div key={index} className="mb-1">
                    {logLine}
                  </div>
                ))
              )}
            </div>
          </div>
        )}
      </div>

      {/* Results */}
      {results && (
        <div className="space-y-6">
          {/* Status Summary */}
          <div className="card p-6">
            <h3 className="text-lg font-medium text-gray-900 mb-4">
              Update Results
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="text-center">
                <div className="text-2xl font-bold text-blue-600">
                  {results.status}
                </div>
                <div className="text-sm text-gray-500">Status</div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold text-green-600">
                  {results.started_at ? new Date(results.started_at).toLocaleTimeString() : 'N/A'}
                </div>
                <div className="text-sm text-gray-500">Started</div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold text-purple-600">
                  {results.completed_at ? new Date(results.completed_at).toLocaleTimeString() : 'N/A'}
                </div>
                <div className="text-sm text-gray-500">Completed</div>
              </div>
            </div>
            
            {results.error && (
              <div className="mt-4 p-4 bg-red-50 border border-red-200 rounded-md">
                <div className="text-red-800 font-medium">Error:</div>
                <div className="text-red-600">{results.error}</div>
              </div>
            )}
          </div>

          {/* Data Import Issues */}
          {issuesData && (
            <div className="card p-6">
              <h3 className="text-lg font-medium text-gray-900 mb-4">
                ⚠️ Data Import Issues
              </h3>
              <DataTable data={issuesData} />
            </div>
          )}

          {/* Log Content */}
          {logContent && (
            <div className="card p-6">
              <h3 className="text-lg font-medium text-gray-900 mb-4">
                📋 Update Log
              </h3>
              <LogViewer content={logContent} title="Database Update Log" />
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default DatabasePage;