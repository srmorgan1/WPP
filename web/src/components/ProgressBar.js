import React from 'react';

const ProgressBar = ({ progress = 0, message = '', status = 'pending' }) => {
  const getStatusColor = () => {
    switch (status) {
      case 'running':
        return 'bg-blue-500';
      case 'completed':
        return 'bg-green-500';
      case 'failed':
        return 'bg-red-500';
      default:
        return 'bg-gray-400';
    }
  };

  const getStatusText = () => {
    switch (status) {
      case 'running':
        return 'Running';
      case 'completed':
        return 'Completed';
      case 'failed':
        return 'Failed';
      default:
        return 'Pending';
    }
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium text-gray-700">
          {getStatusText()}
        </span>
        <span className="text-sm text-gray-500">{Math.round(progress)}%</span>
      </div>
      
      <div className="w-full bg-gray-200 rounded-full h-2">
        <div
          className={`h-2 rounded-full transition-all duration-300 ${getStatusColor()}`}
          style={{ width: `${Math.min(100, Math.max(0, progress))}%` }}
        />
      </div>
      
      {message && (
        <p className="text-sm text-gray-600">{message}</p>
      )}
    </div>
  );
};

export default ProgressBar;