import React, { useEffect, useState } from 'react';
import { Lock, User as UserIcon, X, ArrowRight } from '@phosphor-icons/react';
import { useAuth } from '../../context/AuthContext';

interface LoginModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const LoginModal: React.FC<LoginModalProps> = ({ isOpen, onClose }) => {
  const { login } = useAuth();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Always open on empty fields — never carry credentials across sessions.
  useEffect(() => {
    if (isOpen) {
      setUsername('');
      setPassword('');
      setError(null);
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      await login(username, password);
      setUsername('');
      setPassword('');
      onClose();
    } catch (err: any) {
      setError(err.message || 'Login failed. Please verify your credentials.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-message-in select-none">
      <div className="w-full max-w-sm rounded-xl bg-[#252525] border border-[#3D3D3D] p-6 shadow-2xl relative">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-[#9E9E9E] hover:text-[#FFFFFF] p-1.5 rounded-lg hover:bg-[#333333] transition-colors"
          aria-label="Close"
        >
          <X size={18} />
        </button>

        <div className="flex flex-col items-center text-center mb-6">
          {/* Authentic white logo tile with required clear space */}
          <div className="mb-4 p-2.5 rounded-lg bg-[#FFFFFF] border border-[#C8C8C8]/60 shadow-sm">
            <img
              src="/sankalit-logo.jpg"
              alt="Sankalit Logo"
              className="h-7 w-auto object-contain"
            />
          </div>
          <h2 className="text-lg font-bold text-[#FFFFFF]">Sign in to Sankalit</h2>
          <p className="text-xs text-[#C8C8C8] mt-1">
            Access internal company documents and authorized knowledge
          </p>
        </div>

        {error && (
          <div className="mb-4 p-3 rounded-lg bg-[#E56857]/15 border border-[#E56857]/40 text-xs text-[#E56857]">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4" autoComplete="off">
          <div>
            <label className="block text-[11px] font-bold text-[#9E9E9E] mb-1.5 uppercase tracking-wider">
              Username
            </label>
            <div className="relative">
              <span className="absolute left-3 top-2.5 text-[#888888]">
                <UserIcon size={16} />
              </span>
              <input
                type="text"
                required
                name="skl-username"
                autoComplete="off"
                autoCorrect="off"
                spellCheck={false}
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="Username"
                className="w-full pl-9 pr-3 py-2 text-sm bg-[#1E1E1E] border border-[#3D3D3D] rounded-lg text-[#FFFFFF] focus:border-[#F5A623] focus:ring-1 focus:ring-[#F5A623] focus:outline-none"
              />
            </div>
          </div>

          <div>
            <label className="block text-[11px] font-bold text-[#9E9E9E] mb-1.5 uppercase tracking-wider">
              Password
            </label>
            <div className="relative">
              <span className="absolute left-3 top-2.5 text-[#888888]">
                <Lock size={16} />
              </span>
              <input
                type="password"
                required
                name="skl-password"
                autoComplete="new-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••••••"
                className="w-full pl-9 pr-3 py-2 text-sm bg-[#1E1E1E] border border-[#3D3D3D] rounded-lg text-[#FFFFFF] focus:border-[#F5A623] focus:ring-1 focus:ring-[#F5A623] focus:outline-none"
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={isSubmitting}
            className="w-full mt-2 py-2.5 px-4 rounded-lg bg-[#F5A623] hover:bg-[#F7C05A] text-[#1E1E1E] font-bold text-sm flex items-center justify-center gap-2 transition-all shadow-sm disabled:opacity-50"
          >
            {isSubmitting ? 'Authenticating...' : 'Sign In'}
            {!isSubmitting && <ArrowRight size={16} weight="bold" />}
          </button>
        </form>

        <div className="mt-4 pt-4 border-t border-[#383838] text-center">
          <p className="text-[11px] text-[#888888]">
            Protected by internal JWT & Role-Based Access Control.
          </p>
        </div>
      </div>
    </div>
  );
};
