import React, { useEffect, useState, useCallback } from 'react';
import { useMsal } from '@azure/msal-react';
import { tokenRequest } from '../authConfig';

interface WebhookSubscription {
  id: string;
  resource: string;
  changeType: string;
  notificationUrl: string;
  expirationDateTime: string;
  clientState: string;
}

export default function WebhookGrid() {
  const { instance, accounts } = useMsal();
  const [webhooks, setWebhooks] = useState<WebhookSubscription[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const callApi = useCallback(async () => {
    try {
      const { accessToken } = await instance.acquireTokenSilent({ 
        ...tokenRequest, 
        account: accounts[0] 
      });
      
      const response = await fetch(`${process.env.REACT_APP_API_BASE}/admin/webhooks`, {
        headers: {
          "Authorization": `Bearer ${accessToken}`,
          "Content-Type": "application/json"
        }
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const data = await response.json();
      setWebhooks(data.subscriptions || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load webhooks');
    } finally {
      setLoading(false);
    }
  }, [instance, accounts]);

  useEffect(() => {
    callApi();
  }, [callApi]);

  const formatExpiryDate = (dateString: string) => {
    const date = new Date(dateString);
    const now = new Date();
    const diffHours = Math.floor((date.getTime() - now.getTime()) / (1000 * 60 * 60));
    
    if (diffHours < 0) {
      return <span className="text-red-600 font-semibold">Expired</span>;
    } else if (diffHours < 24) {
      return <span className="text-red-600 font-semibold">Expires in {diffHours}h</span>;
    } else {
      return <span className="text-green-600">Expires {date.toLocaleDateString()}</span>;
    }
  };

  const getRowClassName = (expirationDateTime: string) => {
    const date = new Date(expirationDateTime);
    const now = new Date();
    const diffHours = Math.floor((date.getTime() - now.getTime()) / (1000 * 60 * 60));
    
    if (diffHours < 24) {
      return "hover:bg-red-50 bg-red-25 border-red-200";
    }
    return "hover:bg-gray-50";
  };

  if (loading) return <div>Loading webhooks...</div>;
  if (error) return <div className="text-red-600">Error: {error}</div>;

  return (
    <div>
      <h2 className="text-xl font-semibold mb-4">Active Webhook Subscriptions</h2>
      {webhooks.length === 0 ? (
        <p className="text-gray-500">No active webhook subscriptions found.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full border border-gray-300">
            <thead className="bg-gray-50">
              <tr>
                <th className="border border-gray-300 px-4 py-2 text-left">Resource</th>
                <th className="border border-gray-300 px-4 py-2 text-left">Change Type</th>
                <th className="border border-gray-300 px-4 py-2 text-left">Status</th>
                <th className="border border-gray-300 px-4 py-2 text-left">Subscription ID</th>
              </tr>
            </thead>
            <tbody>
              {webhooks.map((webhook) => (
                <tr key={webhook.id} className={getRowClassName(webhook.expirationDateTime)}>
                  <td className="border border-gray-300 px-4 py-2 font-mono text-sm">
                    {webhook.resource}
                  </td>
                  <td className="border border-gray-300 px-4 py-2">
                    {webhook.changeType}
                  </td>
                  <td className="border border-gray-300 px-4 py-2">
                    {formatExpiryDate(webhook.expirationDateTime)}
                  </td>
                  <td className="border border-gray-300 px-4 py-2 font-mono text-xs">
                    {webhook.id}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <button 
        onClick={callApi}
        className="mt-4 bg-gray-600 text-white px-4 py-2 rounded hover:bg-gray-700"
      >
        Refresh
      </button>
    </div>
  );
} 