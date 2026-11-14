import React from 'react';
import { ArrowUpRight } from '@phosphor-icons/react';

interface ChatEmptyStateProps {
  onSelectPrompt: (prompt: string) => void;
}

export const ChatEmptyState: React.FC<ChatEmptyStateProps> = ({ onSelectPrompt }) => {
  const suggestions = [
    'Tell me about Sankalit Consultant.',
    'What expertise and services does the company offer?',
    'What technical knowledge is available?',
  ];

  return (
    <div className="flex-1 flex flex-col items-center justify-center p-6 text-center w-full max-w-lg mx-auto animate-message-in select-none my-auto">
      {/* Official Sankalit Logo Plate with cap-height clear space */}
      <div className="mb-6 px-3 py-1.5 rounded-lg bg-[#FFFFFF] border border-[#C8C8C8]/60 shadow-sm inline-flex items-center justify-center">
        <img
          src="/sankalit-logo-white.png"
          alt="Sankalit Consultant"
          className="h-7 w-auto object-contain"
        />
      </div>

      <h2 className="text-[27px] font-bold text-[#FFFFFF] mb-2 tracking-tight">
        What would you like to know?
      </h2>
      <p className="text-[14.5px] text-[#D0D0D0] mb-1">
        Ask anything about Sankalit Consultant.
      </p>
      <p className="text-xs text-[#8E8E8E] italic mb-8">
        &ldquo;It&apos;s all about Integration.&rdquo;
      </p>

      {/* 3 refined prompt suggestions with high contrast */}
      <div className="w-full space-y-2.5">
        <div className="text-[10.5px] font-bold text-[#A0A0A0] uppercase tracking-wider mb-2 text-left px-1">
          Suggested Inquiries
        </div>
        {suggestions.map((text, idx) => (
          <button
            key={idx}
            onClick={() => onSelectPrompt(text)}
            className="w-full text-left px-4 py-3 rounded-lg bg-[#2B2B2B] hover:bg-[#333333] border border-[#3C3C3C] hover:border-[#F5A623]/60 text-xs font-medium text-[#FFFFFF] flex items-center justify-between group transition-all shadow-xs"
          >
            <span className="truncate pr-2">{text}</span>
            <ArrowUpRight
              size={15}
              className="text-[#999999] group-hover:text-[#F5A623] transition-colors flex-shrink-0"
            />
          </button>
        ))}
      </div>
    </div>
  );
};
