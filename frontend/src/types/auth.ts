export interface User {
  id: number;
  username: string;
  email: string;
  full_name?: string;
  roles: string[];
  permissions: string[];
  departments?: Array<{ id: number; name: string; slug: string }>;
  is_active: boolean;
  is_superuser: boolean;
}

export interface LoginResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  user: User;
}

export interface RefreshResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

