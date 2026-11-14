import React, { useEffect, useRef, useState } from 'react';
import { PaperPlaneRight, Paperclip } from '@phosphor-icons/react';

interface MessageComposerProps {
  onSend: (message: string) => void;
  isGenerating: boolean;
  disabled?: boolean;
}

export const MessageComposer: React.FC<MessageComposerProps> = ({
  onSend,
  isGenerating,
  disabled = false,
}) => {
  const [content, setContent] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-resize textarea height smoothly
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = '0px';
      const scrollHeight = textareaRef.current.scrollHeight;
      textareaRef.current.style.height = `${Math.min(Math.max(scrollHeight, 24), 160)}px`;
    }
  }, [content]);

  const handleSubmit = () => {
    if (!content.trim() || isGenerating || disabled) return;
    onSend(content.trim());
    setContent('');
    if (textareaRef.current) {
      textareaRef.current.style.height = '24px';
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const canSend = content.trim().length > 0 && !isGenerating && !disabled;

  return (
    <div className="w-full px-4 sm:px-6 pb-6 pt-3 bg-gradient-to-t from-[#282828] via-[#282828] to-transparent absolute bottom-0 left-0 right-0 z-20">
      {/* Centered composer, same outer alignment as the conversation column */}
      <div className="chat-reading-container">
        <div className="flex items-center gap-3 min-h-[68px] rounded-[14px] bg-[#2E2E2E] border border-[#5A5A5A] px-4 py-2.5 focus-within:border-[#F5A623] transition-colors">
          <button
            type="button"
            className="p-1 text-[#A8A8A8] hover:text-[#FFFFFF] transition-colors flex-shrink-0"
            title="Attach a document"
            aria-label="Attach a document"
            tabIndex={-1}
          >
            <Paperclip size={20} />
          </button>

          <textarea
            ref={textareaRef}
            value={content}
            onChange={(e) => setContent(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask a question about Sankalit..."
            rows={1}
            disabled={disabled || isGenerating}
            style={{ height: 24 }}
            className="flex-1 bg-transparent self-center text-[15.5px] text-[#FFFFFF] placeholder-[#9A9A9A] resize-none focus:outline-none max-h-40 leading-[1.5] font-sans"
          />

          <button
            onClick={handleSubmit}
            disabled={!canSend}
            className={`w-[46px] h-[46px] rounded-[11px] flex items-center justify-center flex-shrink-0 transition-all ${
              canSend
                ? 'bg-[#F5A623] hover:bg-[#F7C05A] text-[#FFFFFF] cursor-pointer'
                : 'bg-[#F5A623]/55 text-[#FFFFFF] cursor-not-allowed'
            }`}
            title="Send inquiry"
            aria-label="Send inquiry"
          >
            <PaperPlaneRight size={19} weight="fill" />
          </button>
        </div>
      </div>
    </div>
  );
};
