import React from 'react';
import { WarningCircle } from '@phosphor-icons/react';
import type { Message } from '../../types/chat';
import { BrandMark } from '../common/BrandMark';
import { SourceReferences } from './SourceReferences';

interface AssistantMessageProps {
  message: Message;
}

export const AssistantMessage: React.FC<AssistantMessageProps> = ({ message }) => {
  const isInsufficient = message.retrieval_status === 'insufficient_context';

  // Parse and render markdown elements with high editorial quality
  const renderFormattedContent = (text: string) => {
    const lines = text.split('\n');
    const elements: React.ReactNode[] = [];
    let tableRows: string[][] = [];
    let inTable = false;

    const flushTable = (keyPrefix: number) => {
      if (tableRows.length > 0) {
        const headerRow = tableRows[0];
        const bodyRows = tableRows.slice(1);
        elements.push(
          <div key={`table-${keyPrefix}`} className="my-4 overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse border border-[#333333]">
              <thead>
                <tr className="bg-[#242424] border-b border-[#333333]">
                  {headerRow.map((col, cIdx) => (
                    <th key={cIdx} className="px-3 py-2 font-semibold text-[#FFFFFF] border-r border-[#333333] last:border-r-0">
                      {col.trim()}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-[#2E2E2E]">
                {bodyRows.map((row, rIdx) => (
                  <tr key={rIdx} className="hover:bg-[#222222]">
                    {row.map((cell, cIdx) => (
                      <td key={cIdx} className="px-3 py-2 text-[#CCCCCC] border-r border-[#2E2E2E] last:border-r-0">
                        {renderInlineStyles(cell.trim())}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        );
        tableRows = [];
        inTable = false;
      }
    };

    let i = 0;
    while (i < lines.length) {
      const line = lines[i];
      const trimmed = line.trim();

      // Check for markdown table row
      if (trimmed.startsWith('|') && trimmed.endsWith('|')) {
        // Skip separator rows like |---|---|
        if (/^\|(\s*[-:]+\s*\|)+$/.test(trimmed)) {
          i++;
          continue;
        }
        const cells = trimmed.slice(1, -1).split('|');
        tableRows.push(cells);
        inTable = true;
        i++;
        continue;
      } else if (inTable) {
        flushTable(i);
      }

      // Empty line / paragraph break
      if (!trimmed) {
        elements.push(<div key={`spacer-${i}`} className="h-3" />);
        i++;
        continue;
      }

      // Blockquote
      if (trimmed.startsWith('> ')) {
        elements.push(
          <blockquote
            key={`quote-${i}`}
            className="my-3 pl-3.5 border-l-2 border-[#F5A623] italic text-[#C0C0C0] text-[15px]"
          >
            {renderInlineStyles(trimmed.slice(2))}
          </blockquote>
        );
        i++;
        continue;
      }

      // Headings (H1, H2, H3, H4) — Strictly White text
      if (trimmed.startsWith('#### ')) {
        elements.push(
          <h5 key={`h5-${i}`} className="text-sm font-bold text-[#FFFFFF] mt-4 mb-1.5 tracking-tight">
            {trimmed.replace(/^####\s+/, '')}
          </h5>
        );
        i++;
        continue;
      }
      if (trimmed.startsWith('### ')) {
        elements.push(
          <h4 key={`h4-${i}`} className="text-[17px] font-bold text-[#FFFFFF] mt-5 mb-2 tracking-tight">
            {trimmed.replace(/^###\s+/, '')}
          </h4>
        );
        i++;
        continue;
      }
      if (trimmed.startsWith('## ')) {
        elements.push(
          <h3 key={`h3-${i}`} className="text-[19px] font-bold text-[#FFFFFF] mt-6 mb-2.5 tracking-tight">
            {trimmed.replace(/^##\s+/, '')}
          </h3>
        );
        i++;
        continue;
      }
      if (trimmed.startsWith('# ')) {
        elements.push(
          <h2 key={`h2-${i}`} className="text-[26px] font-bold text-[#FFFFFF] mt-1 mb-3 tracking-tight leading-tight">
            {trimmed.replace(/^#\s+/, '')}
          </h2>
        );
        i++;
        continue;
      }

      // Numbered List Items (e.g. "1. Step description")
      const numberedMatch = trimmed.match(/^(\d+)\.\s+(.*)$/);
      if (numberedMatch) {
        elements.push(
          <div key={`num-${i}`} className="flex items-start gap-3 py-[3px] pl-1">
            <span className="font-bold text-[#F5A623] text-[16px] select-none min-w-[22px] text-right">
              {numberedMatch[1]}.
            </span>
            <div className="flex-1 text-[#E8E8E8] text-[16px] leading-[1.6]">
              {renderInlineStyles(numberedMatch[2])}
            </div>
          </div>
        );
        i++;
        continue;
      }

      // Bullet List Items (e.g. "- Item" or "* Item")
      if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
        elements.push(
          <div key={`bullet-${i}`} className="flex items-start gap-3 py-[3px] pl-1">
            <span className="text-[#F5A623] text-sm leading-none mt-1.5 select-none">•</span>
            <div className="flex-1 text-[#E8E8E8] text-[16px] leading-[1.6]">
              {renderInlineStyles(trimmed.slice(2))}
            </div>
          </div>
        );
        i++;
        continue;
      }

      // Standard Paragraph
      elements.push(
        <p key={`p-${i}`} className="text-[16px] leading-[1.62] text-[#E0E0E0] py-[3px]">
          {renderInlineStyles(line)}
        </p>
      );
      i++;
    }

    if (inTable) {
      flushTable(lines.length);
    }

    return elements;
  };

  // Render **bold**, *italic*, and `code` spans cleanly
  const renderInlineStyles = (content: string) => {
    const parts = content.split(/(\*\*.*?\*\*|\*.*?\*|`.*?`)/g);
    return parts.map((part, index) => {
      if (part.startsWith('**') && part.endsWith('**')) {
        return (
          <strong key={index} className="font-bold text-[#FFFFFF]">
            {part.slice(2, -2)}
          </strong>
        );
      }
      if (part.startsWith('*') && part.endsWith('*')) {
        return (
          <em key={index} className="italic text-[#E0E0E0]">
            {part.slice(1, -1)}
          </em>
        );
      }
      if (part.startsWith('`') && part.endsWith('`')) {
        return (
          <code
            key={index}
            className="px-1.5 py-0.5 rounded bg-[#202020] text-[#F7C05A] text-xs font-technical border border-[#333333]"
          >
            {part.slice(1, -1)}
          </code>
        );
      }
      return part;
    });
  };

  return (
    <div className="w-full animate-message-in mb-9 last:mb-0">
      <div className="flex items-start gap-3.5">
        {/* Assistant identity mark */}
        <div className="w-[34px] h-[34px] rounded-[9px] bg-[#FFFFFF] flex items-center justify-center flex-shrink-0 mt-0.5">
          <BrandMark size={13} variant="mark" />
        </div>

        <div className="flex-1 min-w-0">
          <div className="text-[14px] font-bold text-[#FFFFFF] mb-3 select-none">
            Sankalit Intelligence
          </div>

          {/* Answer content — editorial, directly on the canvas */}
          <div className="max-w-[820px] text-[16px] leading-[1.62] text-[#E0E0E0] font-sans">
            {renderFormattedContent(message.content)}
          </div>

          {/* Insufficient context alert */}
          {isInsufficient && (
            <div className="mt-4 p-3 rounded-lg bg-[#F5A623]/10 border border-[#F5A623]/25 text-[13px] text-[#F7C05A] flex items-center gap-2.5 max-w-[820px]">
              <WarningCircle size={16} className="flex-shrink-0 text-[#F5A623]" />
              <span>
                The available company documents do not contain enough verified information in the
                knowledge base to answer this question with complete certainty.
              </span>
            </div>
          )}

          {/* Sources + timestamp */}
          <div className="max-w-[820px]">
            <SourceReferences sources={message.sources || []} timestamp={message.timestamp} />
          </div>
        </div>
      </div>
    </div>
  );
};
