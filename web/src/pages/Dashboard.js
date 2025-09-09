import React, { useState, useEffect } from 'react';
import { apiService } from '../services/api';
import StatusIndicator from '../components/StatusIndicator';

const Dashboard = () => {
  const [systemStatus, setSystemStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [inputDirValue, setInputDirValue] = useState('');
  const [staticInputDirValue, setStaticInputDirValue] = useState('');
  const [updatingInputDir, setUpdatingInputDir] = useState(false);
  const [updatingStaticInputDir, setUpdatingStaticInputDir] = useState(false);

  useEffect(() => {
    loadSystemStatus();
    // Refresh status every 30 seconds
    const interval = setInterval(loadSystemStatus, 30000);
    return () => clearInterval(interval);
  }, []);

  const loadSystemStatus = async () => {
    try {
      setError(null);
      const status = await apiService.getSystemStatus();
      setSystemStatus(status);
      // Set initial values for input fields
      setInputDirValue(status.input_directory || '');
      setStaticInputDirValue(status.static_input_directory || '');
    } catch (err) {
      console.error('Error loading system status:', err);

      // Provide more specific error messages
      let errorMessage = 'Failed to load system status';
      if (err.code === 'ECONNREFUSED' || err.message.includes('Network Error')) {
        errorMessage = 'Cannot connect to WPP API server. Make sure the FastAPI backend is running on http://localhost:8000';
      } else if (err.response) {
        errorMessage = `API Error: ${err.response.status} - ${err.response.statusText}`;
      } else {
        errorMessage = err.message || errorMessage;
      }

      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  const handleUpdateInputDirectory = async () => {
    if (!inputDirValue.trim()) return;

    setUpdatingInputDir(true);
    try {
      await apiService.updateInputDirectory(inputDirValue.trim());
      // Reload system status to reflect changes
      await loadSystemStatus();
    } catch (err) {
      console.error('Error updating input directory:', err);
      setError('Failed to update input directory');
    } finally {
      setUpdatingInputDir(false);
    }
  };

  const handleUpdateStaticInputDirectory = async () => {
    if (!staticInputDirValue.trim()) return;

    setUpdatingStaticInputDir(true);
    try {
      await apiService.updateStaticInputDirectory(staticInputDirValue.trim());
      // Reload system status to reflect changes
      await loadSystemStatus();
    } catch (err) {
      console.error('Error updating static input directory:', err);
      setError('Failed to update static input directory');
    } finally {
      setUpdatingStaticInputDir(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="card p-6">
        <div className="text-center">
          <div className="text-red-500 text-lg font-medium mb-2">Error</div>
          <p className="text-gray-600 mb-4">{error}</p>
          <button
            onClick={loadSystemStatus}
            className="btn-primary"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="card p-6">
        <h2 className="text-2xl font-bold text-gray-900 mb-4">
          📊 WPP Management Dashboard
        </h2>
        <p className="text-gray-600">
          Monitor system status and manage data processing operations
        </p>
      </div>

      {/* System Status */}
      <div className="card p-6">
        <h3 className="text-lg font-medium text-gray-900 mb-4">
          System Status
        </h3>
        
        {systemStatus ? (
          <div className="space-y-3">
            <StatusIndicator
              status={systemStatus.database_exists ? 'success' : 'warning'}
              text={
                systemStatus.database_exists
                  ? 'Database: Connected'
                  : 'Database: Not Found'
              }
            />
            
            <StatusIndicator
              status={systemStatus.data_directory_exists ? 'success' : 'error'}
              text={
                systemStatus.data_directory_exists
                  ? `Data Directory: ${systemStatus.data_directory}`
                  : `Data Directory: Not Found (${systemStatus.data_directory})`
              }
            />
            
            <StatusIndicator
              status={systemStatus.running_tasks.length > 0 ? 'running' : 'success'}
              text={
                systemStatus.running_tasks.length > 0
                  ? `Running Tasks: ${systemStatus.running_tasks.length}`
                  : 'No Running Tasks'
              }
            />
          </div>
        ) : (
          <div className="text-gray-500">Loading system status...</div>
        )}
      </div>

      {/* Quick Actions */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="card p-6">
          <h3 className="text-lg font-medium text-gray-900 mb-2">
            🔄 Database Update
          </h3>
          <p className="text-gray-600 mb-4">
            Process source files and update the database with latest data
          </p>
          <button
            onClick={() => window.location.href = '/database'}
            className="btn-primary"
          >
            Update Database
          </button>
        </div>

        <div className="card p-6">
          <h3 className="text-lg font-medium text-gray-900 mb-2">
            📊 Generate Reports
          </h3>
          <p className="text-gray-600 mb-4">
            Create comprehensive reports from your database information
          </p>
          <button
            onClick={() => window.location.href = '/reports'}
            className="btn-primary"
          >
            Generate Reports
          </button>
        </div>
      </div>

      {/* Running Tasks */}
      {systemStatus && systemStatus.running_tasks.length > 0 && (
        <div className="card p-6">
          <h3 className="text-lg font-medium text-gray-900 mb-4">
            Running Tasks
          </h3>
          <div className="space-y-2">
            {systemStatus.running_tasks.map((taskId) => (
              <div
                key={taskId}
                className="flex items-center justify-between p-3 bg-blue-50 rounded-md"
              >
                <span className="text-sm font-medium text-blue-900">
                  Task: {taskId}
                </span>
                <span className="status-indicator status-running" />
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default Dashboard;