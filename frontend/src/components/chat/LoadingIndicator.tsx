import React from 'react';
import { BrandMark } from '../common/BrandMark';

export const LoadingIndicator: React.FC = () => {
  return (
    <div className="w-full animate-message-in py-2">
      <div className="flex items-center gap-3.5">
        <div className="w-[34px] h-[34px] rounded-[9px] bg-[#FFFFFF] flex items-center justify-center flex-shrink-0">
          <BrandMark size={13} variant="mark" />
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[14px] text-[#A8A8A8]">Consulting knowledge base</span>
          <span className="w-1.5 h-1.5 rounded-full bg-[#F5A623] animate-pulse" />
          <span className="w-1.5 h-1.5 rounded-full bg-[#F5A623] animate-pulse delay-150" />
          <span className="w-1.5 h-1.5 rounded-full bg-[#F5A623] animate-pulse delay-300" />
        </div>
      </div>
    </div>
  );
};
