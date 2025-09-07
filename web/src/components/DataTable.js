import React from 'react';

const DataTable = ({ data, maxHeight = '400px' }) => {
  // Always call hooks at the top level, before any returns
  const [activeTab, setActiveTab] = React.useState(0);
  const [isExporting, setIsExporting] = React.useState(false);

  const isCriticalSheet = (sheet) => {
    // Use API-provided is_critical flag if available, fallback to name-based checking
    if (sheet.is_critical !== undefined) {
      return sheet.is_critical;
    }
    // Fallback for backward compatibility
    const criticalSheetNames = ['Account Validation Problems', 'Qube Import Problems'];
    return criticalSheetNames.includes(sheet.sheet_name);
  };

  const handleExportToExcel = async () => {
    try {
      setIsExporting(true);
      
      // Prepare data for export
      const exportData = {
        reportName: data.file_info.name.replace(/[^a-zA-Z0-9]/g, '_'),
        sheets: {}
      };
      
      // Convert sheets back to the format expected by the backend
      data.sheets.forEach(sheet => {
        exportData.sheets[sheet.sheet_name] = {
          columns: sheet.columns,
          data: sheet.data,
          metadata: sheet.metadata || {}
        };
      });
      
      // Send export request
      const response = await fetch('/api/export/excel', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(exportData),
      });
      
      if (response.ok) {
        // Create blob and download
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${exportData.reportName}.xlsx`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
      } else {
        console.error('Export failed:', response.statusText);
      }
    } catch (error) {
      console.error('Export error:', error);
    } finally {
      setIsExporting(false);
    }
  };

  // Excel SVG Icon
  const ExcelIcon = () => (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
      <rect x="2" y="2" width="12" height="12" rx="1" fill="none" stroke="currentColor" strokeWidth="1"/>
      <rect x="3" y="3" width="10" height="2" fill="currentColor" opacity="0.3"/>
      <line x1="3" y1="7" x2="13" y2="7" stroke="currentColor" strokeWidth="0.5"/>
      <line x1="3" y1="9" x2="13" y2="9" stroke="currentColor" strokeWidth="0.5"/>
      <line x1="3" y1="11" x2="13" y2="11" stroke="currentColor" strokeWidth="0.5"/>
      <line x1="3" y1="13" x2="13" y2="13" stroke="currentColor" strokeWidth="0.5"/>
      <line x1="5" y1="6" x2="5" y2="14" stroke="currentColor" strokeWidth="0.5"/>
      <line x1="7" y1="6" x2="7" y2="14" stroke="currentColor" strokeWidth="0.5"/>
      <line x1="9" y1="6" x2="9" y2="14" stroke="currentColor" strokeWidth="0.5"/>
      <line x1="11" y1="6" x2="11" y2="14" stroke="currentColor" strokeWidth="0.5"/>
    </svg>
  );

  if (!data || !data.sheets || data.sheets.length === 0) {
    return (
      <div className="card p-4 text-center text-gray-500">
        No data available
      </div>
    );
  }

  const renderSheet = (sheet) => {
    if (!sheet.data || sheet.data.length === 0) {
      return (
        <div className="text-center text-gray-500 py-8">
          No data in this sheet
        </div>
      );
    }

    return (
      <div className="overflow-auto custom-scrollbar" style={{ maxHeight }}>
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50 sticky top-0">
            <tr>
              {sheet.columns.map((column, index) => (
                <th
                  key={index}
                  className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
                >
                  {column}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {sheet.data.map((row, rowIndex) => (
              <tr key={rowIndex} className="hover:bg-gray-50">
                {row.map((cell, cellIndex) => (
                  <td
                    key={cellIndex}
                    className="px-4 py-3 whitespace-nowrap text-sm text-gray-900"
                  >
                    {cell !== null && cell !== undefined ? String(cell) : ''}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  };

  if (data.sheets.length === 1) {
    // Single sheet - render directly
    return (
      <div className="card">
        <div className="px-4 py-3 border-b border-gray-200 flex justify-between items-center">
          <div>
            <h3 className="text-lg font-medium text-gray-900">
              {data.file_info.name}
            </h3>
            <p className="text-sm text-gray-500">
              Created: {new Date(data.file_info.created_at).toLocaleString()}
            </p>
          </div>
          <button
            onClick={handleExportToExcel}
            disabled={isExporting}
            title={isExporting ? 'Exporting...' : 'Export to Excel'}
            className="inline-flex items-center p-2 border border-gray-300 shadow-sm rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <ExcelIcon />
          </button>
        </div>
        {renderSheet(data.sheets[0])}
      </div>
    );
  }

  // Multiple sheets - render tabs

  return (
    <div className="card">
      <div className="px-4 py-3 border-b border-gray-200 flex justify-between items-center">
        <div>
          <h3 className="text-lg font-medium text-gray-900">
            {data.file_info.name}
          </h3>
          <p className="text-sm text-gray-500">
            Created: {new Date(data.file_info.created_at).toLocaleString()}
          </p>
        </div>
        <button
          onClick={handleExportToExcel}
          disabled={isExporting}
          title={isExporting ? 'Exporting...' : 'Export to Excel'}
          className="inline-flex items-center p-2 border border-gray-300 shadow-sm rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <ExcelIcon />
        </button>
      </div>
      
      {/* Tabs */}
      <div className="border-b border-gray-200">
        <nav className="-mb-px flex space-x-8 px-4">
          {data.sheets.map((sheet, index) => {
            const isCritical = isCriticalSheet(sheet);
            const isActive = activeTab === index;
            
            return (
              <button
                key={index}
                onClick={() => setActiveTab(index)}
                className={`py-2 px-1 border-b-2 font-medium text-sm ${
                  isActive
                    ? isCritical 
                      ? 'border-red-500 text-red-600' 
                      : 'border-blue-500 text-blue-600'
                    : isCritical
                      ? 'border-transparent text-red-600 hover:text-red-700 hover:border-red-300'
                      : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                {sheet.sheet_name || 'Unnamed Sheet'}
              </button>
            );
          })}
        </nav>
      </div>
      
      {/* Sheet content */}
      {renderSheet(data.sheets[activeTab])}
    </div>
  );
};

export default DataTable;