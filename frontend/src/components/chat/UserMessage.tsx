import React from 'react';
import { User } from '@phosphor-icons/react';
import type { Message } from '../../types/chat';

interface UserMessageProps {
  message: Message;
}

export const UserMessage: React.FC<UserMessageProps> = ({ message }) => {
  return (
    <div className="flex flex-col items-end animate-message-in mb-7">
      <div className="max-w-[72%] flex items-start gap-3">
        <div className="bg-[#333333] rounded-[10px] px-4 py-2.5 text-[15px] text-[#FFFFFF] leading-relaxed">
          {message.content}
        </div>
        <div className="w-[34px] h-[34px] rounded-full bg-[#333333] flex items-center justify-center flex-shrink-0 text-[#B0B0B0]">
          <User size={17} />
        </div>
      </div>
      {message.timestamp && (
        <div className="mt-1.5 mr-[46px] text-[12px] text-[#8A8A8A] font-technical select-none">
          {message.timestamp}
        </div>
      )}
    </div>
  );
};
