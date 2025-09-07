import React from 'react';

const LogViewer = ({ content, title = "Log Content", maxHeight = '400px' }) => {
  if (!content) {
    return (
      <div className="card p-4 text-center text-gray-500">
        No log content available
      </div>
    );
  }

  return (
    <div className="card">
      <div className="px-4 py-3 border-b border-gray-200">
        <h3 className="text-lg font-medium text-gray-900">{title}</h3>
      </div>
      <div 
        className="p-4 bg-gray-900 text-green-400 font-mono text-sm overflow-auto custom-scrollbar"
        style={{ maxHeight }}
      >
        <pre className="whitespace-pre-wrap">{content}</pre>
      </div>
    </div>
  );
};

export default LogViewer;