import React, { createContext, useContext, useEffect, useState } from 'react';
import { fetchCurrentUser, loginUser, logoutUser } from '../api/auth';
import { getStoredToken } from '../api/client';
import type { User } from '../types/auth';

interface AuthContextType {
  user: User | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (u: string, p: string) => Promise<void>;
  logout: () => Promise<void>;
  hasPermission: (perm: string) => boolean;
  isAdmin: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  useEffect(() => {
    async function loadUser() {
      const token = getStoredToken();
      if (!token) {
        setIsLoading(false);
        return;
      }
      try {
        const u = await fetchCurrentUser();
        setUser(u);
      } catch (err) {
        setUser(null);
      } finally {
        setIsLoading(false);
      }
    }
    loadUser();
  }, []);

  const login = async (u: string, p: string) => {
    setIsLoading(true);
    try {
      const res = await loginUser(u, p);
      setUser(res.user);
    } finally {
      setIsLoading(false);
    }
  };

  const logout = async () => {
    try {
      await logoutUser();
    } finally {
      setUser(null);
    }
  };

  const hasPermission = (perm: string): boolean => {
    if (!user) return false;
    if (user.is_superuser || user.roles.includes('SUPER_ADMIN')) return true;
    return user.permissions.includes(perm);
  };

  const isAdmin = Boolean(
    user && (user.is_superuser || user.roles.includes('SUPER_ADMIN') || user.roles.includes('ADMIN'))
  );

  return (
    <AuthContext.Provider
      value={{
        user,
        isLoading,
        isAuthenticated: !!user,
        login,
        logout,
        hasPermission,
        isAdmin,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
