import React from 'react';
import { BrowserRouter as Router, Routes, Route, Link, useLocation } from 'react-router-dom';
import { Database, BarChart3, Home } from 'lucide-react';

import { DatabaseProvider } from './contexts/DatabaseContext';
import { ConnectionProvider, useConnection } from './contexts/ConnectionContext';
import ConnectionErrorOverlay from './components/ConnectionErrorOverlay';
import Dashboard from './pages/Dashboard';
import DatabasePage from './pages/DatabasePage';
import ReportsPage from './pages/ReportsPage';
import { AppContextProvider } from './contexts/AppContext';

const Navigation = () => {
  const location = useLocation();

  const isActive = (path) => {
    return location.pathname === path;
  };

  const navItems = [
    { path: '/', icon: Home, label: 'Dashboard' },
    { path: '/database', icon: Database, label: 'Database' },
    { path: '/reports', icon: BarChart3, label: 'Reports' },
  ];

  return (
    <nav className="bg-white shadow-sm border-b border-gray-200">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between h-16">
          <div className="flex items-center">
            <div className="flex-shrink-0">
              <h1 className="text-xl font-bold text-gray-900">
                📊 WPP Management
              </h1>
            </div>
            <div className="hidden sm:ml-8 sm:flex sm:space-x-8">
              {navItems.map(({ path, icon: Icon, label }) => (
                <Link
                  key={path}
                  to={path}
                  className={`inline-flex items-center px-1 pt-1 border-b-2 text-sm font-medium ${
                    isActive(path)
                      ? 'border-blue-500 text-blue-600'
                      : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                  }`}
                >
                  <Icon className="w-4 h-4 mr-2" />
                  {label}
                </Link>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Mobile menu */}
      <div className="sm:hidden">
        <div className="pt-2 pb-3 space-y-1 border-t border-gray-200">
          {navItems.map(({ path, icon: Icon, label }) => (
            <Link
              key={path}
              to={path}
              className={`block pl-3 pr-4 py-2 border-l-4 text-base font-medium ${
                isActive(path)
                  ? 'bg-blue-50 border-blue-500 text-blue-700'
                  : 'border-transparent text-gray-600 hover:text-gray-800 hover:bg-gray-50 hover:border-gray-300'
              }`}
            >
              <Icon className="w-4 h-4 inline mr-2" />
              {label}
            </Link>
          ))}
        </div>
      </div>
    </nav>
  );
};

const Layout = ({ children }) => {
  const { showErrorOverlay, connectionError, handleRetry } = useConnection();
  
  return (
    <div className="min-h-screen bg-gray-50">
      <Navigation />
      <main className="max-w-7xl mx-auto py-6 px-4 sm:px-6 lg:px-8">
        {children}
      </main>
      
      {/* Connection Error Overlay */}
      <ConnectionErrorOverlay
        isVisible={showErrorOverlay}
        error={connectionError}
        onRetry={handleRetry}
      />
    </div>
  );
};

function App() {
  return (
    <AppContextProvider>
      <Router>
        <Layout>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/database" element={<DatabasePage />} />
            <Route path="/reports" element={<ReportsPage />} />
          </Routes>
        </Layout>
      </Router>
    </AppContextProvider>
  );
}

export default App;