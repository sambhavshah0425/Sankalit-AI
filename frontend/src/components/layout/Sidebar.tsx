import React from 'react';
import { ChatText, Plus, Trash, Database, SignOut, SignIn } from '@phosphor-icons/react';
import { useAuth } from '../../context/AuthContext';
import { useChat } from '../../context/ChatContext';
import { BrandMark } from '../common/BrandMark';

interface SidebarProps {
  isCollapsed: boolean;
  onToggleCollapse: () => void;
  activeView: 'chat' | 'admin';
  onSelectView: (view: 'chat' | 'admin') => void;
  onOpenLogin: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  isCollapsed,
  activeView,
  onSelectView,
  onOpenLogin,
}) => {
  const { user, isAuthenticated, logout, isAdmin } = useAuth();
  const { sessions, activeSessionId, createNewChat, selectSession, deleteSession } = useChat();

  return (
    <aside
      className={`h-full flex flex-col bg-[#1A1A1A] border-r border-[#2E2E2E] transition-all duration-200 select-none ${
        isCollapsed ? 'w-16' : 'w-[315px]'
      }`}
    >
      {/* Brand row: logo plate + INTELLIGENCE beside it */}
      <div className="px-5 pt-5 pb-4">
        <div
          onClick={() => onSelectView('chat')}
          className="flex items-center gap-3 cursor-pointer overflow-hidden"
          title="Sankalit Intelligence"
        >
          {isCollapsed ? (
            <div className="w-9 h-9 rounded-lg bg-[#FFFFFF] flex items-center justify-center">
              <BrandMark size={14} variant="mark" />
            </div>
          ) : (
            <>
              <div className="h-[38px] px-3 rounded-[10px] bg-[#FFFFFF] flex items-center justify-center flex-shrink-0">
                <img
                  src="/sankalit-logo-white.png"
                  alt="Sankalit"
                  className="h-[21px] w-auto object-contain"
                />
              </div>
              <span className="text-[12.5px] uppercase tracking-[0.13em] font-bold text-[#F5A623] whitespace-nowrap">
                Intelligence
              </span>
            </>
          )}
        </div>
      </div>

      {/* Primary Action: New conversation */}
      <div className="px-4 pb-4">
        <button
          onClick={() => {
            onSelectView('chat');
            createNewChat();
          }}
          className={`w-full h-[46px] rounded-[10px] flex items-center gap-2.5 text-[15px] font-semibold bg-[#F5A623] hover:bg-[#F7C05A] text-[#FFFFFF] transition-colors ${
            isCollapsed ? 'justify-center px-0' : 'px-4'
          }`}
          title="Start new inquiry"
        >
          <Plus size={19} weight="bold" className="text-[#FFFFFF]" />
          {!isCollapsed && <span>New conversation</span>}
        </button>
      </div>

      {/* Primary Navigation */}
      <div className="px-4 space-y-1">
        <button
          onClick={() => onSelectView('chat')}
          className={`w-full h-[42px] rounded-[8px] flex items-center gap-3 text-[14.5px] font-semibold transition-colors ${
            activeView === 'chat'
              ? 'bg-[#2A2A2A] text-[#FFFFFF]'
              : 'text-[#B5B5B5] hover:bg-[#232323] hover:text-[#FFFFFF]'
          } ${isCollapsed ? 'justify-center px-0' : 'px-3.5'}`}
          title="AI Assistant"
        >
          <ChatText
            size={19}
            weight={activeView === 'chat' ? 'fill' : 'regular'}
            className={activeView === 'chat' ? 'text-[#F5A623]' : 'text-[#9A9A9A]'}
          />
          {!isCollapsed && <span>Assistant</span>}
        </button>

        {isAdmin && (
          <button
            onClick={() => onSelectView('admin')}
            className={`w-full h-[42px] rounded-[8px] flex items-center gap-3 text-[14.5px] font-normal transition-colors ${
              activeView === 'admin'
                ? 'bg-[#2A2A2A] text-[#FFFFFF]'
                : 'text-[#B5B5B5] hover:bg-[#232323] hover:text-[#FFFFFF]'
            } ${isCollapsed ? 'justify-center px-0' : 'px-3.5'}`}
            title="Knowledge Base Administration"
          >
            <Database
              size={19}
              weight={activeView === 'admin' ? 'fill' : 'regular'}
              className={activeView === 'admin' ? 'text-[#F5A623]' : 'text-[#9A9A9A]'}
            />
            {!isCollapsed && <span>Knowledge Base</span>}
          </button>
        )}
      </div>

      {/* Divider */}
      <div className="mx-4 mt-4 border-t border-[#2E2E2E]" />

      {/* Recent conversations */}
      <div className="flex-1 overflow-y-auto px-4 pt-4 pb-2">
        {!isCollapsed && (
          <>
            <div className="px-1 pb-2 text-[11px] font-semibold text-[#8A8A8A] uppercase tracking-[0.12em]">
              Recent conversations
            </div>
            <div className="space-y-0.5">
              {sessions.map((session) => (
                <SessionItem
                  key={session.id}
                  session={session}
                  isActive={activeSessionId === session.id && activeView === 'chat'}
                  onSelect={() => {
                    onSelectView('chat');
                    selectSession(session.id);
                  }}
                  onDelete={() => deleteSession(session.id)}
                />
              ))}
            </div>

            {sessions.length === 0 && (
              <div className="px-1 py-5">
                <p className="text-[13px] text-[#777777]">No recent conversations</p>
              </div>
            )}
          </>
        )}
      </div>

      {/* Account footer */}
      <div className="px-4 pb-5 pt-4 border-t border-[#2E2E2E]">
        {isAuthenticated && user ? (
          <>
            <div className="flex items-center gap-3 px-1">
              <div className="w-9 h-9 rounded-full bg-[#F5A623] text-[#FFFFFF] font-bold text-[12.5px] flex items-center justify-center flex-shrink-0">
                {user.username.substring(0, 2).toUpperCase()}
              </div>
              {!isCollapsed && (
                <div className="flex flex-col min-w-0">
                  <span className="text-[14px] font-semibold text-[#FFFFFF] truncate leading-tight">
                    {user.full_name || user.username}
                  </span>
                  <span className="text-[11.5px] text-[#8A8A8A] truncate tracking-wide">
                    {user.roles[0] || 'Employee'}
                  </span>
                </div>
              )}
            </div>

            <button
              onClick={logout}
              className={`mt-3 w-full h-[40px] rounded-[8px] flex items-center gap-3 text-[14.5px] text-[#B5B5B5] hover:text-[#FFFFFF] hover:bg-[#232323] transition-colors ${
                isCollapsed ? 'justify-center px-0' : 'px-1.5'
              }`}
              title="Sign out"
            >
              <SignOut size={19} className="text-[#9A9A9A]" />
              {!isCollapsed && <span>Logout</span>}
            </button>
          </>
        ) : (
          <button
            onClick={onOpenLogin}
            className={`w-full h-[42px] rounded-[8px] flex items-center gap-3 text-[14.5px] font-semibold text-[#FFFFFF] bg-[#252525] hover:bg-[#2E2E2E] transition-colors ${
              isCollapsed ? 'justify-center px-0' : 'px-3.5'
            }`}
          >
            <SignIn size={18} className="text-[#F5A623]" />
            {!isCollapsed && <span>Sign In</span>}
          </button>
        )}
      </div>
    </aside>
  );
};

interface SessionItemProps {
  session: { id: string; title: string };
  isActive: boolean;
  onSelect: () => void;
  onDelete: () => void;
}

const SessionItem: React.FC<SessionItemProps> = ({ session, isActive, onSelect, onDelete }) => {
  return (
    <div
      onClick={onSelect}
      title={session.title}
      className={`group flex items-center justify-between px-3 h-[36px] rounded-[7px] text-[14px] cursor-pointer transition-colors ${
        isActive
          ? 'bg-[#2A2A2A] text-[#FFFFFF]'
          : 'text-[#B5B5B5] hover:bg-[#232323] hover:text-[#FFFFFF]'
      }`}
    >
      <span className="truncate flex-1 pr-1">{session.title}</span>
      <button
        onClick={(e) => {
          e.stopPropagation();
          onDelete();
        }}
        className="opacity-0 group-hover:opacity-100 p-0.5 text-[#777777] hover:text-[#E56857] transition-opacity"
        title="Delete conversation"
      >
        <Trash size={13} />
      </button>
    </div>
  );
};
