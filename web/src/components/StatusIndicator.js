import React from 'react';

const StatusIndicator = ({ status, text, className = '' }) => {
  const getStatusClass = () => {
    switch (status) {
      case 'success':
        return 'status-success';
      case 'warning':
        return 'status-warning';
      case 'error':
        return 'status-error';
      case 'running':
        return 'status-running';
      default:
        return 'bg-gray-400';
    }
  };

  return (
    <div className={`flex items-center ${className}`}>
      <span className={`status-indicator ${getStatusClass()}`} />
      <span className="text-sm text-gray-700">{text}</span>
    </div>
  );
};

export default StatusIndicator;