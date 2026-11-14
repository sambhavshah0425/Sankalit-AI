import React, { useState } from 'react';
import { CaretDown, CaretUp, FileText } from '@phosphor-icons/react';
import type { SourceCitation } from '../../types/chat';

interface SourceReferencesProps {
  sources: SourceCitation[];
  timestamp?: string;
}

export const SourceReferences: React.FC<SourceReferencesProps> = ({ sources, timestamp }) => {
  const [isExpanded, setIsExpanded] = useState(() => {
    if (typeof window !== 'undefined') {
      return new URLSearchParams(window.location.search).get('expand_sources') === 'true';
    }
    return false;
  });

  const hasSources = sources && sources.length > 0;
  if (!hasSources && !timestamp) return null;

  return (
    <div className="mt-6 pt-3 border-t border-[#3A3A3A]">
      <div className="flex items-center justify-between">
        {hasSources ? (
          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className="flex items-center gap-2 text-[13.5px] text-[#B0B0B0] hover:text-[#FFFFFF] transition-colors group select-none"
            aria-expanded={isExpanded}
          >
            <FileText size={16} className="text-[#B0B0B0] group-hover:text-[#FFFFFF]" />
            <span>
              {sources.length} {sources.length === 1 ? 'Source' : 'Sources'}
            </span>
            {isExpanded ? (
              <CaretUp size={13} className="text-[#888888] group-hover:text-[#FFFFFF]" />
            ) : (
              <CaretDown size={13} className="text-[#888888] group-hover:text-[#FFFFFF]" />
            )}
          </button>
        ) : (
          <span />
        )}

        {timestamp && (
          <span className="text-[12px] text-[#8A8A8A] font-technical select-none">{timestamp}</span>
        )}
      </div>

      {hasSources && isExpanded && (
        <div className="mt-3 space-y-1.5 animate-message-in">
          {sources.map((src, index) => (
            <div
              key={index}
              className="p-2.5 rounded-md bg-[#222222] border border-[#2E2E2E] text-xs flex items-start gap-2 text-[#CCCCCC]"
            >
              <FileText size={15} className="text-[#F5A623] flex-shrink-0 mt-0.5" />
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-medium text-[#E0E0E0] truncate text-[12.5px]">
                    {src.filename}
                  </span>
                  {src.similarity !== undefined && (
                    <span className="text-[10.5px] font-technical text-[#F7C05A] bg-[#F5A623]/10 px-1.5 py-0.5 rounded border border-[#F5A623]/20 flex-shrink-0">
                      {(src.similarity * 100).toFixed(0)}% match
                    </span>
                  )}
                </div>
                <div className="text-[11px] text-[#777777] mt-0.5 flex items-center gap-2 font-technical">
                  <span>Chunk {src.chunk_index}</span>
                  {src.document_title && (
                    <>
                      <span>•</span>
                      <span className="truncate text-[#AAAAAA]">{src.document_title}</span>
                    </>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
