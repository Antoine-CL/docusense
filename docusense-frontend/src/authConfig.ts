const SPA_CLIENT_ID = process.env.REACT_APP_SPACLIENT_ID || "<SPA_CLIENT_ID>";
const TENANT_ID    = process.env.REACT_APP_TENANT_ID    || "<TENANT_ID>";
const API_CLIENT_ID = process.env.REACT_APP_API_CLIENT_ID || "<API_CLIENT_ID>";

export const msalConfig = {
  auth: {
    clientId: SPA_CLIENT_ID,
    authority: `https://login.microsoftonline.com/${TENANT_ID}`,
    redirectUri: "http://localhost:3000/auth"
  },
  cache: {
    cacheLocation: "sessionStorage"
  }
};

export const tokenRequest = {
  scopes: [`api://${API_CLIENT_ID}/api.access`]
}; 