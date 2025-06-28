import React, { useState } from 'react';
import { useMsal } from '@azure/msal-react';
import { tokenRequest } from '../authConfig';

export default function AuditDownload() {
  const { instance, accounts } = useMsal();
  const [fromDate, setFromDate] = useState('');
  const [toDate, setToDate] = useState('');
  const [downloading, setDownloading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const downloadAuditLog = async () => {
    if (!fromDate || !toDate) {
      setError('Please select both from and to dates');
      return;
    }

    if (new Date(fromDate) > new Date(toDate)) {
      setError('From date cannot be after to date');
      return;
    }

    setDownloading(true);
    setError(null);

    try {
      const { accessToken } = await instance.acquireTokenSilent({ 
        ...tokenRequest, 
        account: accounts[0] 
      });
      
      const params = new URLSearchParams({
        from: fromDate,
        to: toDate
      });
      
      const response = await fetch(
        `${process.env.REACT_APP_API_BASE}/admin/auditlog?${params}`, 
        {
          headers: {
            "Authorization": `Bearer ${accessToken}`,
          }
        }
      );

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      // Get the CSV content
      const csvContent = await response.text();
      
      // Create a blob and download it
      const blob = new Blob([csvContent], { type: 'text/csv' });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `audit-log-${fromDate}-to-${toDate}.csv`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
      
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to download audit log');
    } finally {
      setDownloading(false);
    }
  };

  // Set default dates (last 30 days)
  React.useEffect(() => {
    const today = new Date();
    const thirtyDaysAgo = new Date(today);
    thirtyDaysAgo.setDate(today.getDate() - 30);
    
    setToDate(today.toISOString().split('T')[0]);
    setFromDate(thirtyDaysAgo.toISOString().split('T')[0]);
  }, []);

  return (
    <div>
      <h2 className="text-xl font-semibold mb-4">Audit Log Download</h2>
      
      <div className="space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block font-semibold mb-1">From Date</label>
            <input
              type="date"
              value={fromDate}
              onChange={e => setFromDate(e.target.value)}
              className="border p-2 rounded w-full"
            />
          </div>
          
          <div>
            <label className="block font-semibold mb-1">To Date</label>
            <input
              type="date"
              value={toDate}
              onChange={e => setToDate(e.target.value)}
              className="border p-2 rounded w-full"
            />
          </div>
        </div>
        
        {error && (
          <div className="text-red-600 bg-red-50 border border-red-200 rounded p-3">
            {error}
          </div>
        )}
        
        <button
          onClick={downloadAuditLog}
          disabled={downloading || !fromDate || !toDate}
          className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {downloading ? 'Downloading...' : 'Download Audit Log CSV'}
        </button>
        
        <div className="text-sm text-gray-600">
          <p>The audit log includes:</p>
          <ul className="list-disc list-inside mt-1 space-y-1">
            <li>User search queries and results</li>
            <li>Document ingestion events</li>
            <li>Authentication events</li>
            <li>Admin configuration changes</li>
            <li>Error events and system alerts</li>
          </ul>
        </div>
      </div>
    </div>
  );
} 