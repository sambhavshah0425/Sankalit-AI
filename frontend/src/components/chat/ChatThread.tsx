import React, { useEffect, useRef } from 'react';
import { useChat } from '../../context/ChatContext';
import { AssistantMessage } from './AssistantMessage';
import { ChatEmptyState } from './ChatEmptyState';
import { LoadingIndicator } from './LoadingIndicator';
import { UserMessage } from './UserMessage';

interface ChatThreadProps {
  onSelectPrompt: (prompt: string) => void;
}

export const ChatThread: React.FC<ChatThreadProps> = ({ onSelectPrompt }) => {
  const { activeSession, isGenerating } = useChat();
  const bottomRef = useRef<HTMLDivElement>(null);

  const messages = activeSession?.messages || [];

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isGenerating]);

  if (messages.length === 0) {
    return (
      <div className="flex-1 flex flex-col justify-center items-center overflow-y-auto px-4 sm:px-6">
        <ChatEmptyState onSelectPrompt={onSelectPrompt} />
      </div>
    );
  }

  return (
    <div className="chat-scroll-stable flex-1 overflow-y-auto px-4 sm:px-6 pt-7 pb-[132px] w-full">
      {/* 840px Centered Reading Column */}
      <div className="chat-reading-container">
        {messages.map((msg) =>
          msg.role === 'user' ? (
            <UserMessage key={msg.id} message={msg} />
          ) : (
            <AssistantMessage key={msg.id} message={msg} />
          )
        )}

        {isGenerating && <LoadingIndicator />}
        <div ref={bottomRef} className="h-4" />
      </div>
    </div>
  );
};
