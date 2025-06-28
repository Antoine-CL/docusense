import React, { useEffect, useState, useCallback } from "react";
import { useMsal } from "@azure/msal-react";
import { tokenRequest } from "../authConfig";
import { useAdminRole } from "../hooks/useAdminRole";
import RegionSelect from "../components/RegionSelect";
import RetentionSlider from "../components/RetentionSlider";
import WebhookGrid from "../components/WebhookGrid";
import UsagePanel from "../components/UsagePanel";
import AuditDownload from "../components/AuditDownload";

interface AdminSettings {
  region: string;
  retentionDays: number;
  [key: string]: any;
}

export default function AdminPage() {
  const { instance, accounts } = useMsal();
  const { isAdmin, loading: adminLoading } = useAdminRole();
  const [settings, setSettings] = useState<AdminSettings | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const callApi = useCallback(async (method: string, body?: any) => {
    try {
      const { accessToken } = await instance.acquireTokenSilent({ 
        ...tokenRequest, 
        account: accounts[0] 
      });
      
      const response = await fetch(`${process.env.REACT_APP_API_BASE}/admin/settings`, {
        method,
        headers: {
          "Authorization": `Bearer ${accessToken}`,
          "Content-Type": "application/json"
        },
        body: body ? JSON.stringify(body) : undefined
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      return await response.json();
    } catch (err) {
      throw new Error(err instanceof Error ? err.message : 'API call failed');
    }
  }, [instance, accounts]);

  useEffect(() => {
    const loadSettings = async () => {
      try {
        const data = await callApi("GET");
        setSettings(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load settings');
      }
    };

    loadSettings();
  }, [callApi]);

  const save = async () => {
    if (!settings) return;

    setSaving(true);
    setError(null);
    setSuccessMessage(null);

    try {
      const updated = await callApi("PATCH", settings);
      setSettings(updated);
      setSuccessMessage("Settings saved! Backend will reprovision in background.");
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save settings');
    } finally {
      setSaving(false);
    }
  };

  // Clear success message after 5 seconds
  useEffect(() => {
    if (successMessage) {
      const timer = setTimeout(() => setSuccessMessage(null), 5000);
      return () => clearTimeout(timer);
    }
  }, [successMessage]);

  // Show loading state while checking admin role
  if (adminLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p>Checking admin permissions...</p>
        </div>
      </div>
    );
  }

  // Show access denied if not admin
  if (!isAdmin) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <div className="text-red-600 text-6xl mb-4">🚫</div>
          <h1 className="text-2xl font-bold text-gray-900 mb-2">Access Denied</h1>
          <p className="text-gray-600 mb-4">
            You need TenantAdmin role to access this page.
          </p>
          <p className="text-sm text-gray-500">
            Contact your administrator to request admin access.
          </p>
        </div>
      </div>
    );
  }

  // Show loading state while fetching settings
  if (!settings) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p>Loading admin settings...</p>
          {error && (
            <div className="mt-4 text-red-600 bg-red-50 border border-red-200 rounded p-3">
              {error}
            </div>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="p-8 space-y-8 max-w-6xl mx-auto">
      <div className="border-b border-gray-200 pb-4">
        <h1 className="text-3xl font-bold text-gray-900">Admin Settings</h1>
        <p className="text-gray-600 mt-2">
          Manage your DocuSense tenant configuration and monitor system usage
        </p>
      </div>

      {/* Settings Section */}
      <div className="bg-white border border-gray-200 rounded-lg p-6">
        <h2 className="text-xl font-semibold mb-4">Configuration</h2>
        
        <div className="space-y-6">
          <RegionSelect 
            value={settings.region} 
            onChange={r => setSettings({ ...settings, region: r })}
          />
          
          <RetentionSlider 
            days={settings.retentionDays}
            onChange={d => setSettings({ ...settings, retentionDays: d })}
          />
        </div>

        {error && (
          <div className="mt-4 text-red-600 bg-red-50 border border-red-200 rounded p-3">
            {error}
          </div>
        )}

        {successMessage && (
          <div className="mt-4 text-green-600 bg-green-50 border border-green-200 rounded p-3">
            {successMessage}
          </div>
        )}

        <button 
          onClick={save}
          className="mt-6 bg-blue-600 text-white px-6 py-2 rounded hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
          disabled={saving}
        >
          {saving ? "Saving..." : "Save Changes"}
        </button>
      </div>

      {/* Monitoring Sections */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        <div className="bg-white border border-gray-200 rounded-lg p-6">
          <WebhookGrid />
        </div>
        
        <div className="bg-white border border-gray-200 rounded-lg p-6">
          <AuditDownload />
        </div>
      </div>

      {/* Usage Panel - Full Width */}
      <div className="bg-white border border-gray-200 rounded-lg p-6">
        <UsagePanel />
      </div>
    </div>
  );
} 