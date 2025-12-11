// Authentication type definitions

export interface User {
  userId: string;
  email: string;
  customerId?: string;
}

export interface AuthSession {
  user: User;
  accessToken: string;
  idToken: string;
  refreshToken: string;
}

export interface AuthState {
  isAuthenticated: boolean;
  user: User | null;
  isLoading: boolean;
  error: Error | null;
}
