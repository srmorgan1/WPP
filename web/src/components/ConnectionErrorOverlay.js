import React from 'react';
import { AlertTriangle, RefreshCw, Server } from 'lucide-react';

const ConnectionErrorOverlay = ({ isVisible, onRetry, error }) => {
  if (!isVisible) return null;

  const getErrorMessage = () => {
    if (error?.code === 'ECONNREFUSED') {
      return 'The server is not running or has been shut down.';
    }
    if (error?.message === 'Network Error') {
      return 'Unable to connect to the server.';
    }
    if (error?.code === 'ERR_NETWORK') {
      return 'Network connection failed.';
    }
    return 'Lost connection to the server.';
  };

  const handleRestartClick = () => {
    // Attempt to send shutdown request to any running instance first
    try {
      fetch('/api/shutdown', { method: 'POST' }).catch(() => {
        // Ignore errors - server might already be down
      });
    } catch (e) {
      // Ignore - server is likely down
    }
    
    // Show instructions
    alert('To restart the server:\n\n1. Go to your terminal\n2. Navigate to the WPP project directory\n3. Run: ./start-web.sh\n\nOr restart the executable if using the packaged version.');
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl p-8 max-w-md mx-4">
        {/* Icon */}
        <div className="flex items-center justify-center w-16 h-16 bg-red-100 rounded-full mx-auto mb-4">
          <AlertTriangle className="w-8 h-8 text-red-600" />
        </div>

        {/* Title */}
        <h2 className="text-xl font-bold text-gray-900 text-center mb-2">
          Server Connection Lost
        </h2>

        {/* Message */}
        <p className="text-gray-600 text-center mb-6">
          {getErrorMessage()}
        </p>

        {/* Instructions */}
        <div className="bg-amber-50 border border-amber-200 rounded-md p-4 mb-6">
          <h3 className="text-sm font-medium text-amber-800 mb-2">
            What to do:
          </h3>
          <ol className="text-sm text-amber-700 space-y-1 list-decimal list-inside">
            <li>Close this browser tab/window</li>
            <li>Restart the WPP server</li>
            <li>Open the application again</li>
          </ol>
        </div>

        {/* Actions */}
        <div className="flex space-x-3">
          <button
            onClick={onRetry}
            className="flex-1 flex items-center justify-center px-4 py-2 border border-gray-300 rounded-md text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
          >
            <RefreshCw className="w-4 h-4 mr-2" />
            Retry Connection
          </button>
          
          <button
            onClick={handleRestartClick}
            className="flex-1 flex items-center justify-center px-4 py-2 border border-transparent rounded-md text-sm font-medium text-white bg-red-600 hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500"
          >
            <Server className="w-4 h-4 mr-2" />
            Restart Instructions
          </button>
        </div>

        {/* Technical details (collapsible) */}
        {error && (
          <details className="mt-4">
            <summary className="text-sm text-gray-500 cursor-pointer hover:text-gray-700">
              Technical Details
            </summary>
            <div className="mt-2 text-xs text-gray-400 bg-gray-50 p-2 rounded font-mono">
              <div><strong>Error:</strong> {error.message || 'Unknown error'}</div>
              {error.code && <div><strong>Code:</strong> {error.code}</div>}
              <div><strong>Server:</strong> http://localhost:8000</div>
            </div>
          </details>
        )}
      </div>
    </div>
  );
};

export default ConnectionErrorOverlay;