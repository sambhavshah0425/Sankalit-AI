import React, { useState } from 'react';
import { useChat } from '../../context/ChatContext';
import { KnowledgeAdmin } from '../admin/KnowledgeAdmin';
import { LoginModal } from '../auth/LoginModal';
import { ChatThread } from '../chat/ChatThread';
import { MessageComposer } from '../chat/MessageComposer';
import { ChatHeader } from './ChatHeader';
import { Sidebar } from './Sidebar';

export const AppShell: React.FC = () => {
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(() => {
    if (typeof window !== 'undefined') {
      return new URLSearchParams(window.location.search).get('sidebar') === 'collapsed';
    }
    return false;
  });
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const [isLoginOpen, setIsLoginOpen] = useState(false);
  const [activeView, setActiveView] = useState<'chat' | 'admin'>('chat');

  const { sendMessage, isGenerating } = useChat();

  const handleSelectPrompt = (prompt: string) => {
    sendMessage(prompt);
  };

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-[#282828] text-[#FFFFFF] select-none font-sans">
      {/* Desktop Sidebar */}
      <div className="hidden md:block h-full flex-shrink-0">
        <Sidebar
          isCollapsed={isSidebarCollapsed}
          onToggleCollapse={() => setIsSidebarCollapsed(!isSidebarCollapsed)}
          activeView={activeView}
          onSelectView={setActiveView}
          onOpenLogin={() => setIsLoginOpen(true)}
        />
      </div>

      {/* Mobile Drawer Backdrop & Sidebar */}
      {isMobileMenuOpen && (
        <div className="md:hidden fixed inset-0 z-40 flex">
          <div
            className="fixed inset-0 bg-black/75 backdrop-blur-sm"
            onClick={() => setIsMobileMenuOpen(false)}
          />
          <div className="relative w-[300px] h-full z-50 animate-message-in">
            <Sidebar
              isCollapsed={false}
              onToggleCollapse={() => setIsMobileMenuOpen(false)}
              activeView={activeView}
              onSelectView={(v) => {
                setActiveView(v);
                setIsMobileMenuOpen(false);
              }}
              onOpenLogin={() => {
                setIsMobileMenuOpen(false);
                setIsLoginOpen(true);
              }}
            />
          </div>
        </div>
      )}

      {/* Main Workspace Column */}
      <div className="flex-1 flex flex-col h-full min-w-0 bg-[#282828] relative">
        <ChatHeader
          onOpenMobileMenu={() => setIsMobileMenuOpen(true)}
          onToggleSidebar={() => setIsSidebarCollapsed(!isSidebarCollapsed)}
          onOpenLogin={() => setIsLoginOpen(true)}
          activeView={activeView}
        />

        {activeView === 'chat' ? (
          <main className="flex-1 flex flex-col min-h-0 relative overflow-hidden">
            <ChatThread onSelectPrompt={handleSelectPrompt} />
            <MessageComposer onSend={sendMessage} isGenerating={isGenerating} />
          </main>
        ) : (
          <main className="flex-1 flex flex-col min-h-0 relative overflow-y-auto">
            <KnowledgeAdmin onBackToChat={() => setActiveView('chat')} />
          </main>
        )}
      </div>

      {/* Authentication Modal */}
      <LoginModal isOpen={isLoginOpen} onClose={() => setIsLoginOpen(false)} />
    </div>
  );
};
