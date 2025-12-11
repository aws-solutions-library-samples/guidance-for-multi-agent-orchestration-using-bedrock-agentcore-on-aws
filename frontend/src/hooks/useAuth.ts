import { useEffect, useState } from 'react';
import { 
  CognitoUserPool, 
  CognitoUserSession,
} from 'amazon-cognito-identity-js';

export interface User {
  userId: string;
  email: string;
  customerId?: string;
}

export interface AuthState {
  user: User | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  error: Error | null;
}

// Initialize Cognito User Pool
const getUserPool = () => {
  const userPoolId = import.meta.env.VITE_USER_POOL_ID;
  const clientId = import.meta.env.VITE_USER_POOL_CLIENT_ID;
  
  if (!userPoolId || !clientId) {
    throw new Error('Cognito configuration missing');
  }
  
  return new CognitoUserPool({
    UserPoolId: userPoolId,
    ClientId: clientId,
  });
};

/**
 * Custom hook for managing authentication state
 */
export function useAuth() {
  const [authState, setAuthState] = useState<AuthState>({
    user: null,
    isLoading: true,
    isAuthenticated: false,
    error: null,
  });

  /**
   * Get current Cognito user session
   */
  const getCurrentSession = (): Promise<CognitoUserSession | null> => {
    return new Promise((resolve) => {
      const userPool = getUserPool();
      const cognitoUser = userPool.getCurrentUser();
      
      if (!cognitoUser) {
        resolve(null);
        return;
      }

      cognitoUser.getSession((err: Error | null, session: CognitoUserSession | null) => {
        if (err || !session || !session.isValid()) {
          resolve(null);
          return;
        }
        resolve(session);
      });
    });
  };

  /**
   * Fetches user attributes from Cognito
   */
  const fetchUser = async (): Promise<User | null> => {
    return new Promise((resolve) => {
      const userPool = getUserPool();
      const cognitoUser = userPool.getCurrentUser();
      
      if (!cognitoUser) {
        resolve(null);
        return;
      }

      cognitoUser.getSession((err: Error | null, session: CognitoUserSession | null) => {
        if (err || !session) {
          resolve(null);
          return;
        }

        cognitoUser.getUserAttributes((err: any, attributes: any) => {
          if (err || !attributes) {
            resolve(null);
            return;
          }

          const email = attributes.find((attr: any) => attr.getName() === 'email')?.getValue() || '';
          const customerId = attributes.find((attr: any) => attr.getName() === 'custom:customer_id')?.getValue();
          const userId = attributes.find((attr: any) => attr.getName() === 'sub')?.getValue() || '';

          resolve({
            userId,
            email,
            customerId,
          });
        });
      });
    });
  };

  /**
   * Checks authentication status
   */
  const checkAuthStatus = async () => {
    try {
      setAuthState(prev => ({ ...prev, isLoading: true, error: null }));

      const session = await getCurrentSession();
      
      if (!session || !session.isValid()) {
        setAuthState({
          user: null,
          isLoading: false,
          isAuthenticated: false,
          error: null,
        });
        return;
      }

      const user = await fetchUser();
      
      if (user) {
        setAuthState({
          user,
          isLoading: false,
          isAuthenticated: true,
          error: null,
        });
      } else {
        setAuthState({
          user: null,
          isLoading: false,
          isAuthenticated: false,
          error: null,
        });
      }
    } catch (error) {
      console.error('Error checking auth status:', error);
      setAuthState({
        user: null,
        isLoading: false,
        isAuthenticated: false,
        error: error instanceof Error ? error : new Error('Authentication error'),
      });
    }
  };

  /**
   * Logs out the current user
   */
  const logout = async () => {
    try {
      const userPool = getUserPool();
      const cognitoUser = userPool.getCurrentUser();
      
      if (cognitoUser) {
        cognitoUser.signOut();
      }
      
      setAuthState({
        user: null,
        isLoading: false,
        isAuthenticated: false,
        error: null,
      });
      
      // Force page reload to show login screen
      window.location.reload();
    } catch (error) {
      console.error('Error signing out:', error);
      setAuthState(prev => ({
        ...prev,
        error: error instanceof Error ? error : new Error('Logout error'),
      }));
    }
  };

  /**
   * Gets the current JWT access token
   */
  const getAccessToken = async (): Promise<string | null> => {
    try {
      const session = await getCurrentSession();
      return session?.getAccessToken().getJwtToken() || null;
    } catch (error) {
      console.error('Error getting access token:', error);
      return null;
    }
  };

  /**
   * Forces a token refresh
   */
  const refreshToken = async (): Promise<boolean> => {
    return new Promise((resolve) => {
      const userPool = getUserPool();
      const cognitoUser = userPool.getCurrentUser();
      
      if (!cognitoUser) {
        resolve(false);
        return;
      }

      cognitoUser.getSession((err: Error | null, session: CognitoUserSession | null) => {
        if (err || !session) {
          resolve(false);
          return;
        }

        const refreshToken = session.getRefreshToken();
        cognitoUser.refreshSession(refreshToken, (err: any, newSession: any) => {
          if (err) {
            console.error('Error refreshing token:', err);
            resolve(false);
            return;
          }
          resolve(!!newSession);
        });
      });
    });
  };

  // Check authentication status on mount
  useEffect(() => {
    checkAuthStatus();
  }, []);

  // Set up automatic token refresh
  useEffect(() => {
    if (!authState.isAuthenticated) {
      return;
    }

    // Check session validity every 5 minutes
    const intervalId = setInterval(async () => {
      const session = await getCurrentSession();
      if (!session || !session.isValid()) {
        await checkAuthStatus();
      }
    }, 5 * 60 * 1000);

    return () => clearInterval(intervalId);
  }, [authState.isAuthenticated]);

  return {
    ...authState,
    logout,
    getAccessToken,
    refreshToken,
    checkAuthStatus,
  };
}
