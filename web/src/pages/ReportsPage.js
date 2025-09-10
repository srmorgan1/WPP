import React, { useState, useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import { apiService, wsService } from '../services/api';
import ProgressBar from '../components/ProgressBar';
import DataTable from '../components/DataTable';
import LogViewer from '../components/LogViewer';
import { useAppContext } from '../contexts/AppContext';

const ReportsPage = () => {
  const location = useLocation();
  const { reportsPageState, updateReportsPageState } = useAppContext();
  const [reportDate, setReportDate] = useState(new Date().toISOString().split('T')[0]);
  const logViewerRef = React.useRef(null);
  
  // Destructure state from context
  const {
    results,
    reportData,
    logContent,
    realtimeLog,
    progress,
    progressMessage,
    status,
    currentTask,
    isRunning
  } = reportsPageState;

  useEffect(() => {
    // Connect WebSocket for real-time updates
    wsService.connect();
    
    const handleProgress = (message) => {
      if (message.task_id === currentTask) {
        updateReportsPageState({
          progress: message.data.progress || 0,
          progressMessage: message.data.message || '',
          status: message.data.status || 'running'
        });
        
        // Accumulate log messages for scrolling display
        if (message.data.message) {
          const timestamp = new Date().toLocaleTimeString();
          const logEntry = `[${timestamp}] ${message.data.message}`;
          updateReportsPageState({
            realtimeLog: [...realtimeLog, logEntry]
          });
        }
        
        if (message.data.status === 'completed') {
          updateReportsPageState({
            progress: 100,
            isRunning: false
          });
          loadTaskResults(message.task_id);
        } else if (message.data.status === 'failed') {
          updateReportsPageState({ isRunning: false });
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

  // Fetch latest charges date on component mount
  const fetchChargesDate = async () => {
    try {
      console.log('🔄 Fetching charges date from API...');
      const response = await apiService.getChargesDate();
      console.log('📡 API Response:', response);
      if (response.date) {
        console.log('✅ Setting report date to:', response.date);
        setReportDate(response.date);
      } else {
        console.log('⚠️ No date found in response, keeping current date');
      }
      // If no charges date (database not updated yet), keep today's date as fallback
    } catch (error) {
      console.error('❌ Error fetching charges date:', error);
      // Keep today's date as fallback if API call fails
    }
  };

  // Combined hook: fetch charges date on mount and when navigating to reports page
  useEffect(() => {
    console.log('📍 Location changed to:', location.pathname);
    if (location.pathname === '/reports') {
      console.log('🎯 On reports page, fetching charges date...');
      fetchChargesDate();
    }
  }, [location.pathname]);

  const handleGenerateReports = async () => {
    try {
      updateReportsPageState({
        isRunning: true,
        progress: 0,
        progressMessage: 'Starting report generation...',
        status: 'running',
        results: null,
        reportData: null,
        logContent: null,
        realtimeLog: []
      });

      const response = await apiService.generateReports(reportDate);
      updateReportsPageState({ currentTask: response.task_id });
    } catch (error) {
      console.error('Error starting report generation:', error);
      updateReportsPageState({
        isRunning: false,
        status: 'failed',
        progressMessage: `Error: ${error.message}`
      });
    }
  };

  const loadTaskResults = async (taskId) => {
    try {
      const taskResult = await apiService.getTaskStatus(taskId);
      updateReportsPageState({ results: taskResult });

      // Check for web_sheets data directly in the task result (new system)
      if (taskResult.result_data?.summary?.web_sheets) {
        // Convert web_sheets to the format expected by DataTable component
        const webSheets = taskResult.result_data.summary.web_sheets;
        const convertedData = {
          file_info: {
            name: 'Generated Reports',
            created_at: taskResult.completed_at || taskResult.started_at
          },
          sheets: Object.entries(webSheets).map(([sheetName, sheet]) => ({
            sheet_name: sheetName,
            columns: sheet.columns,
            data: sheet.data.map(row => sheet.columns.map(col => row[col] || '')),
            is_critical: sheet.is_critical || false
          }))
        };
        updateReportsPageState({ reportData: convertedData });
      }

      // Load files if available (legacy system)
      if (taskResult.result_data?.files) {
        for (const fileRef of taskResult.result_data.files) {
          try {
            if (fileRef.file_type === 'excel') {
              const reportData = await apiService.getExcelData(fileRef.filename);
              updateReportsPageState({ reportData });
            } else if (fileRef.file_type === 'log') {
              const logData = await apiService.getLogContent(fileRef.filename);
              updateReportsPageState({ logContent: logData.content });
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
          📊 Generate Reports
        </h2>
        <p className="text-gray-600">
          Create comprehensive reports from your database information
        </p>
      </div>

      {/* Configuration */}
      <div className="card p-6">
        <h3 className="text-lg font-medium text-gray-900 mb-4">
          Report Configuration
        </h3>
        <div className="max-w-md">
          <label htmlFor="reportDate" className="block text-sm font-medium text-gray-700 mb-2">
            Report Date
          </label>
          <input
            type="date"
            id="reportDate"
            value={reportDate}
            onChange={(e) => setReportDate(e.target.value)}
            disabled={isRunning}
            className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500"
          />
          <p className="mt-2 text-sm text-gray-500">
            Using business day calendar (excludes weekends and UK holidays)
          </p>
        </div>
      </div>

      {/* Action */}
      <div className="card p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-medium text-gray-900">
            Generate Reports
          </h3>
          <button
            onClick={handleGenerateReports}
            disabled={isRunning}
            className="btn-primary"
          >
            {isRunning ? (
              <>
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2" />
                Generating...
              </>
            ) : (
              'Generate Reports'
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
              Generation Results
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

          {/* Generated Report */}
          {reportData && (
            <div className="card p-6">
              <h3 className="text-lg font-medium text-gray-900 mb-4">
                📊 Generated Report
              </h3>
              <DataTable data={reportData} />
            </div>
          )}

          {/* Log Content */}
          {logContent && (
            <div className="card p-6">
              <h3 className="text-lg font-medium text-gray-900 mb-4">
                📋 Generation Log
              </h3>
              <LogViewer content={logContent} title="Report Generation Log" />
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default ReportsPage;