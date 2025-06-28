import { useMsal } from '@azure/msal-react';
import { useState, useEffect } from 'react';
import { tokenRequest } from '../authConfig';

export const useAdminRole = () => {
  const { instance, accounts } = useMsal();
  const [isAdmin, setIsAdmin] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const checkAdminRole = async () => {
      try {
        if (accounts.length === 0) {
          setIsAdmin(false);
          setLoading(false);
          return;
        }

        const response = await instance.acquireTokenSilent({ 
          ...tokenRequest, 
          account: accounts[0] 
        });

        // Decode the ID token to check for roles
        if (response.idToken) {
          const payload = JSON.parse(atob(response.idToken.split('.')[1]));
          const roles = payload.roles || [];
          setIsAdmin(roles.includes('TenantAdmin'));
        } else {
          // Fallback: for now, allow all authenticated users to access admin
          // In production, this should be false and require proper role assignment
          setIsAdmin(true);
        }
      } catch (error) {
        console.error('Error checking admin role:', error);
        setIsAdmin(false);
      } finally {
        setLoading(false);
      }
    };

    checkAdminRole();
  }, [instance, accounts]);

  return { isAdmin, loading };
}; 