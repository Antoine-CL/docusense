import { useMsal } from "@azure/msal-react";
import { tokenRequest } from "../authConfig";
import { useState } from "react";

export default function SearchPage() {
  const { instance, accounts } = useMsal();
  const [q, setQ] = useState("");
  const [results, setResults] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Check auth mode from environment
  const isLocalDev = process.env.REACT_APP_API_BASE?.includes('localhost');
  const useProdAuth = process.env.REACT_APP_USE_PROD_AUTH === 'true';
  const shouldUseAuth = !isLocalDev || useProdAuth;

  const runSearch = async () => {
    if (!q.trim()) return;
    
    setLoading(true);
    setError(null);
    
    try {
      let headers: any = {
        "Content-Type": "application/json"
      };

      if (shouldUseAuth) {
        // Production or local production auth: use MSAL authentication
        let accessToken;
        
        if (accounts.length > 0) {
          // User is already signed in, try to get token silently
          const response = await instance.acquireTokenSilent({ 
            ...tokenRequest, 
            account: accounts[0] 
          });
          accessToken = response.accessToken;
        } else {
          // User is not signed in, prompt for login
          const response = await instance.acquireTokenPopup(tokenRequest);
          accessToken = response.accessToken;
        }
        
        headers.Authorization = `Bearer ${accessToken}`;
      }
      // For local dev with simple auth, no auth header needed

      // Make the search request
      const r = await fetch(`${process.env.REACT_APP_API_BASE}/search`, {
        method: "POST",
        headers,
        body: JSON.stringify({ query: q })
      });
      
      if (!r.ok) {
        throw new Error(`HTTP error! status: ${r.status}`);
      }
      
      const json = await r.json();
      setResults(json.results || json);
    } catch (error) {
      console.error("Search failed:", error);
      setError(error instanceof Error ? error.message : "Search failed");
    } finally {
      setLoading(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      runSearch();
    }
  };

  // Auth status info
  const getAuthStatus = () => {
    if (!shouldUseAuth) {
      return "🔧 Simple Auth (Local Development)";
    } else if (accounts.length > 0) {
      return `🔐 Authenticated as ${accounts[0].name}`;
    } else {
      return "🔑 Production Auth (Not Signed In)";
    }
  };

  return (
    <div className="p-8 space-y-6">
      <div className="max-w-4xl mx-auto">
        <div className="flex justify-between items-center mb-8">
          <h1 className="text-3xl font-bold text-gray-900">DocuSense Search</h1>
          <div className="text-sm text-gray-600 bg-gray-100 px-3 py-1 rounded">
            {getAuthStatus()}
          </div>
        </div>
        
        <div className="flex space-x-4 mb-6">
          <input
            className="flex-1 border border-gray-300 rounded-lg px-4 py-2 text-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
            value={q}
            onChange={e => setQ(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="Ask me anything about your documents..."
            disabled={loading}
          />
          <button
            className="bg-indigo-600 hover:bg-indigo-700 disabled:bg-indigo-400 text-white px-6 py-2 rounded-lg font-medium transition-colors"
            onClick={runSearch}
            disabled={loading || !q.trim()}
          >
            {loading ? "Searching..." : "Search"}
          </button>
        </div>

        {/* Auth Configuration Info */}
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-6 text-sm">
          <div className="font-medium text-blue-800 mb-2">Authentication Configuration:</div>
          <div className="text-blue-700 space-y-1">
            <div>• API Base: {process.env.REACT_APP_API_BASE || 'http://localhost:8001'}</div>
            <div>• Auth Mode: {shouldUseAuth ? 'Production (Azure AD)' : 'Simple (Development)'}</div>
            {shouldUseAuth && (
              <>
                <div>• Client ID: {process.env.REACT_APP_SPACLIENT_ID || '<not configured>'}</div>
                <div>• Tenant ID: {process.env.REACT_APP_TENANT_ID || '<not configured>'}</div>
              </>
            )}
          </div>
          {shouldUseAuth && (!process.env.REACT_APP_SPACLIENT_ID || process.env.REACT_APP_SPACLIENT_ID === 'your-spa-client-id-here') && (
            <div className="mt-2 text-orange-700 bg-orange-100 p-2 rounded">
              ⚠️ Azure AD not configured. Please update .env.local with your app registration details.
            </div>
          )}
        </div>

        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6">
            <div className="text-red-800">
              <strong>Error:</strong> {error}
            </div>
            <div className="text-sm text-red-600 mt-1">
              Make sure the backend is running on {process.env.REACT_APP_API_BASE || 'http://localhost:8001'}
              {shouldUseAuth && " and you're properly authenticated."}
            </div>
          </div>
        )}

        {results.length > 0 && (
          <div className="space-y-4">
            <h2 className="text-xl font-semibold text-gray-800">
              Search Results ({results.length})
            </h2>
            <ul className="space-y-4">
              {results.map((r: any, idx) => (
                <li key={idx} className="bg-white border border-gray-200 rounded-lg p-4 shadow-sm hover:shadow-md transition-shadow">
                  <div className="font-semibold text-lg text-gray-900 mb-2">{r.title}</div>
                  <div className="text-gray-600 mb-2">{r.snippet}…</div>
                  {r.score && (
                    <div className="text-xs text-gray-400">
                      Relevance: {r.score.toFixed?.(2) ?? r.score}
                    </div>
                  )}
                </li>
              ))}
            </ul>
          </div>
        )}

        {!loading && results.length === 0 && q && !error && (
          <div className="text-center py-8 text-gray-500">
            No results found for "{q}"
          </div>
        )}

        {/* Quick Auth Toggle for Testing */}
        <div className="mt-8 p-4 bg-gray-50 rounded-lg">
          <div className="text-sm font-medium text-gray-700 mb-2">Development Tools:</div>
          <div className="text-xs text-gray-600">
            To test production auth locally, set REACT_APP_USE_PROD_AUTH=true in .env.local
          </div>
        </div>
      </div>
    </div>
  );
} 