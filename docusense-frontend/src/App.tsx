import React from 'react';
import { Routes, Route, Navigate, Link, useLocation } from "react-router-dom";
import { AuthenticatedTemplate, UnauthenticatedTemplate } from "@azure/msal-react";
import SearchPage from "./pages/SearchPage";
import AdminPage from "./pages/AdminPage";
import { useAdminRole } from "./hooks/useAdminRole";
import './App.css';

function App() {
  const location = useLocation();
  const { isAdmin, loading: adminLoading } = useAdminRole();

  return (
    <div>
      {/* Navigation Header */}
      <AuthenticatedTemplate>
        <nav className="bg-white border-b border-gray-200 px-4 py-3">
          <div className="max-w-6xl mx-auto flex items-center justify-between">
            <div className="flex items-center space-x-8">
              <h1 className="text-xl font-bold text-gray-900">DocuSense</h1>
              <div className="flex space-x-4">
                <Link
                  to="/search"
                  className={`px-3 py-2 rounded-md text-sm font-medium ${
                    location.pathname === '/search'
                      ? 'bg-blue-100 text-blue-700'
                      : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
                  }`}
                >
                  Search
                </Link>
                {isAdmin && !adminLoading && (
                  <Link
                    to="/admin"
                    className={`px-3 py-2 rounded-md text-sm font-medium ${
                      location.pathname === '/admin'
                        ? 'bg-blue-100 text-blue-700'
                        : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
                    }`}
                  >
                    Admin
                  </Link>
                )}
              </div>
            </div>
          </div>
        </nav>
      </AuthenticatedTemplate>

      {/* Main Content */}
      <Routes>
        <Route path="/" element={<Navigate to="/search" />} />
        <Route path="/search" element={<SearchPage />} />
        <Route 
          path="/admin" 
          element={
            <AuthenticatedTemplate>
              <AdminPage />
            </AuthenticatedTemplate>
          } 
        />
        <Route path="/auth" element={<div>Auth complete… redirecting</div>} />
      </Routes>

      {/* Fallback for unauthenticated users */}
      <UnauthenticatedTemplate>
        <div className="flex items-center justify-center min-h-screen">
          <div className="text-center">
            <h1 className="text-2xl font-bold text-gray-900 mb-4">DocuSense</h1>
            <p className="text-gray-600">Please sign in to access the application.</p>
          </div>
        </div>
      </UnauthenticatedTemplate>
    </div>
  );
}

export default App;
