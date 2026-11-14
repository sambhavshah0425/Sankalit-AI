import { apiClient, clearStoredTokens, setStoredTokens } from './client';
import type { LoginResponse, User } from '../types/auth';

export async function loginUser(username: string, password: string): Promise<LoginResponse> {
  const data = await apiClient<LoginResponse>('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  });
  setStoredTokens(data.access_token, data.refresh_token);
  return data;
}

export async function fetchCurrentUser(): Promise<User> {
  return apiClient<User>('/auth/me', {
    method: 'GET',
  });
}

export async function logoutUser(): Promise<void> {
  try {
    await apiClient('/auth/logout', { method: 'POST' });
  } catch (err) {
    // Ignore network error on logout
  } finally {
    clearStoredTokens();
  }
}
