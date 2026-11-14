import React from 'react';
import type { HealthStatus } from '../../types/document';

interface StatusBadgeProps {
  health: HealthStatus;
  onClick?: () => void;
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({ health, onClick }) => {
  const isOnline = health.status === 'connected';
  const isChecking = health.status === 'checking';

  const dotColor = isOnline ? 'bg-[#F5A623]' : isChecking ? 'bg-[#F7C05A]' : 'bg-[#E56857]';
  const label = isOnline ? 'Local AI' : isChecking ? 'Connecting...' : 'AI Offline';

  return (
    <div
      onClick={onClick}
      title={
        isOnline
          ? `Connected to local ${health.model || 'model'} — Click to refresh`
          : health.detail || 'Backend/Ollama offline'
      }
      className="inline-flex items-center gap-2.5 text-[13.5px] text-[#C8C8C8] cursor-pointer hover:text-[#FFFFFF] transition-colors select-none"
    >
      <span className={`w-2 h-2 rounded-full ${dotColor} ${isOnline ? 'pulse-dot' : ''}`} />
      <span>{label}</span>
    </div>
  );
};
