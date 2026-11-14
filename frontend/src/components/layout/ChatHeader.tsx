import React from 'react';
import { List, Sparkle } from '@phosphor-icons/react';
import { StatusBadge } from '../common/StatusBadge';
import { useChat } from '../../context/ChatContext';

interface ChatHeaderProps {
  onOpenMobileMenu: () => void;
  onToggleSidebar?: () => void;
  onOpenLogin: () => void;
  activeView: 'chat' | 'admin';
}

export const ChatHeader: React.FC<ChatHeaderProps> = ({
  onOpenMobileMenu,
  onToggleSidebar,
  activeView,
}) => {
  const { activeSession, health, refreshHealth } = useChat();

  const title =
    activeView === 'admin'
      ? 'Knowledge Base Administration'
      : activeSession?.title || 'New conversation';

  return (
    <header className="h-[60px] flex items-center justify-between px-5 sm:px-6 bg-[#282828] border-b border-[#2E2E2E] z-10 select-none flex-shrink-0">
      <div className="flex items-center gap-3 min-w-0">
        <button
          onClick={onOpenMobileMenu}
          className="md:hidden p-1 rounded-md text-[#9A9A9A] hover:text-[#FFFFFF] transition-colors"
          aria-label="Open navigation menu"
        >
          <List size={20} />
        </button>
        <button
          onClick={onToggleSidebar}
          className="hidden md:inline-flex p-1 rounded-md text-[#9A9A9A] hover:text-[#FFFFFF] transition-colors"
          aria-label="Toggle sidebar"
          title="Toggle sidebar"
        >
          <List size={20} />
        </button>

        <div className="flex items-center gap-2.5 min-w-0">
          <Sparkle size={18} weight="fill" className="text-[#F5A623] flex-shrink-0" />
          <h1 className="text-[16px] font-semibold text-[#FFFFFF] truncate">{title}</h1>
        </div>
      </div>

      <div className="flex items-center">
        <StatusBadge health={health} onClick={refreshHealth} />
      </div>
    </header>
  );
};
