import React, { useEffect, useState, useCallback } from 'react';
import { useMsal } from '@azure/msal-react';
import { tokenRequest } from '../authConfig';

interface UsageData {
  documentsIndexed: number;
  totalEmbeddings: number;
  searchRequests: number;
  storageUsedMB: number;
  estimatedMonthlyCost: number;
  lastUpdated: string;
}

export default function UsagePanel() {
  const { instance, accounts } = useMsal();
  const [usage, setUsage] = useState<UsageData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const callApi = useCallback(async () => {
    try {
      const { accessToken } = await instance.acquireTokenSilent({ 
        ...tokenRequest, 
        account: accounts[0] 
      });
      
      const response = await fetch(`${process.env.REACT_APP_API_BASE}/admin/usage`, {
        headers: {
          "Authorization": `Bearer ${accessToken}`,
          "Content-Type": "application/json"
        }
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const data = await response.json();
      setUsage(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load usage data');
    } finally {
      setLoading(false);
    }
  }, [instance, accounts]);

  useEffect(() => {
    callApi();
  }, [callApi]);

  if (loading) return <div>Loading usage data...</div>;
  if (error) return <div className="text-red-600">Error: {error}</div>;
  if (!usage) return <div>No usage data available</div>;

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD'
    }).format(amount);
  };

  const formatNumber = (num: number) => {
    return new Intl.NumberFormat('en-US').format(num);
  };

  return (
    <div>
      <h2 className="text-xl font-semibold mb-4">Usage & Costs</h2>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
          <h3 className="font-semibold text-blue-900">Documents Indexed</h3>
          <p className="text-2xl font-bold text-blue-700">
            {formatNumber(usage.documentsIndexed)}
          </p>
        </div>
        
        <div className="bg-green-50 border border-green-200 rounded-lg p-4">
          <h3 className="font-semibold text-green-900">Total Embeddings</h3>
          <p className="text-2xl font-bold text-green-700">
            {formatNumber(usage.totalEmbeddings)}
          </p>
        </div>
        
        <div className="bg-purple-50 border border-purple-200 rounded-lg p-4">
          <h3 className="font-semibold text-purple-900">Search Requests</h3>
          <p className="text-2xl font-bold text-purple-700">
            {formatNumber(usage.searchRequests)}
          </p>
        </div>
        
        <div className="bg-orange-50 border border-orange-200 rounded-lg p-4">
          <h3 className="font-semibold text-orange-900">Storage Used</h3>
          <p className="text-2xl font-bold text-orange-700">
            {formatNumber(usage.storageUsedMB)} MB
          </p>
        </div>
        
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <h3 className="font-semibold text-red-900">Estimated Monthly Cost</h3>
          <p className="text-2xl font-bold text-red-700">
            {formatCurrency(usage.estimatedMonthlyCost)}
          </p>
        </div>
        
        <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
          <h3 className="font-semibold text-gray-900">Last Updated</h3>
          <p className="text-sm text-gray-700">
            {new Date(usage.lastUpdated).toLocaleString()}
          </p>
        </div>
      </div>
      
      <button 
        onClick={callApi}
        className="mt-4 bg-gray-600 text-white px-4 py-2 rounded hover:bg-gray-700"
      >
        Refresh Usage Data
      </button>
    </div>
  );
} 