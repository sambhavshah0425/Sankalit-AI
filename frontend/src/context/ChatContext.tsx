import React, { createContext, useContext, useEffect, useState } from 'react';
import { askKnowledgeBase, askKnowledgeBaseStream, checkOllamaHealth } from '../api/rag';
import type { ConversationSession, Message } from '../types/chat';
import type { HealthStatus } from '../types/document';

interface ChatContextType {
  sessions: ConversationSession[];
  activeSessionId: string | null;
  activeSession: ConversationSession | null;
  isGenerating: boolean;
  health: HealthStatus;
  createNewChat: () => void;
  selectSession: (id: string) => void;
  deleteSession: (id: string) => void;
  sendMessage: (content: string) => Promise<void>;
  refreshHealth: () => Promise<void>;
}

const STORAGE_KEY = 'skl_conversations_v1';
const ACTIVE_KEY = 'skl_active_conv_id';

const ChatContext = createContext<ChatContextType | undefined>(undefined);

export const ChatProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [sessions, setSessions] = useState<ConversationSession[]>(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      return saved ? JSON.parse(saved) : [];
    } catch {
      return [];
    }
  });

  const [activeSessionId, setActiveSessionId] = useState<string | null>(() => {
    return localStorage.getItem(ACTIVE_KEY) || null;
  });

  const [isGenerating, setIsGenerating] = useState<boolean>(false);
  const [health, setHealth] = useState<HealthStatus>({ status: 'checking' });

  // Save sessions to localStorage
  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(sessions));
    } catch (e) {
      console.error('Failed to save sessions to localStorage', e);
    }
  }, [sessions]);

  // Save activeSessionId
  useEffect(() => {
    if (activeSessionId) {
      localStorage.setItem(ACTIVE_KEY, activeSessionId);
    } else {
      localStorage.removeItem(ACTIVE_KEY);
    }
  }, [activeSessionId]);

  // Check Ollama health on mount and every 30s
  const refreshHealth = async () => {
    const status = await checkOllamaHealth();
    setHealth(status);
  };

  useEffect(() => {
    refreshHealth();
    const interval = setInterval(refreshHealth, 30000);
    return () => clearInterval(interval);
  }, []);

  const activeSession = sessions.find((s) => s.id === activeSessionId) || null;

  const createNewChat = () => {
    const newSession: ConversationSession = {
      id: `session_${Date.now()}`,
      title: 'New conversation',
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      messages: [],
    };
    setSessions((prev) => [newSession, ...prev]);
    setActiveSessionId(newSession.id);
  };

  const selectSession = (id: string) => {
    setActiveSessionId(id);
  };

  const deleteSession = (id: string) => {
    setSessions((prev) => prev.filter((s) => s.id !== id));
    if (activeSessionId === id) {
      const remaining = sessions.filter((s) => s.id !== id);
      setActiveSessionId(remaining.length > 0 ? remaining[0].id : null);
    }
  };

  const sendMessage = async (questionText: string) => {
    const trimmed = questionText.trim();
    if (!trimmed || isGenerating) return;

    // If no active session, create one
    let targetSessionId = activeSessionId;
    let targetSession = activeSession;

    if (!targetSessionId || !targetSession) {
      const newId = `session_${Date.now()}`;
      const newSession: ConversationSession = {
        id: newId,
        title: trimmed.length > 36 ? `${trimmed.substring(0, 36)}...` : trimmed,
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
        messages: [],
      };
      setSessions((prev) => [newSession, ...prev]);
      setActiveSessionId(newId);
      targetSessionId = newId;
      targetSession = newSession;
    }

    const userMessage: Message = {
      id: `msg_u_${Date.now()}`,
      role: 'user',
      content: trimmed,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    // Update session title if first message
    const isFirstMessage = targetSession.messages.length === 0;
    const sessionTitle = isFirstMessage
      ? (trimmed.length > 40 ? `${trimmed.substring(0, 40)}...` : trimmed)
      : targetSession.title;

    setSessions((prev) =>
      prev.map((s) => {
        if (s.id === targetSessionId) {
          return {
            ...s,
            title: sessionTitle,
            updatedAt: new Date().toISOString(),
            messages: [...s.messages, userMessage],
          };
        }
        return s;
      })
    );

    setIsGenerating(true);

    const assistantMsgId = `msg_a_${Date.now()}`;
    const initialAssistantMessage: Message = {
      id: assistantMsgId,
      role: 'assistant',
      content: '',
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      sources: [],
      retrieval_status: 'generating',
    };

    // Pre-insert assistant message so typing/streaming starts immediately
    setSessions((prev) =>
      prev.map((s) => {
        if (s.id === targetSessionId) {
          return {
            ...s,
            updatedAt: new Date().toISOString(),
            messages: [...s.messages, initialAssistantMessage],
          };
        }
        return s;
      })
    );

    try {
      let accumulatedText = '';
      await askKnowledgeBaseStream(
        trimmed,
        {
          onMetadata: (meta) => {
            setSessions((prev) =>
              prev.map((s) => {
                if (s.id === targetSessionId) {
                  return {
                    ...s,
                    updatedAt: new Date().toISOString(),
                    messages: s.messages.map((m) =>
                      m.id === assistantMsgId
                        ? {
                            ...m,
                            sources: meta.sources || [],
                            detected_domain: meta.detected_domain,
                            retrieval_status: meta.retrieval_status || 'success',
                          }
                        : m
                    ),
                  };
                }
                return s;
              })
            );
          },
          onDelta: (token) => {
            accumulatedText += token;
            setSessions((prev) =>
              prev.map((s) => {
                if (s.id === targetSessionId) {
                  return {
                    ...s,
                    updatedAt: new Date().toISOString(),
                    messages: s.messages.map((m) =>
                      m.id === assistantMsgId
                        ? {
                            ...m,
                            content: accumulatedText,
                          }
                        : m
                    ),
                  };
                }
                return s;
              })
            );
          },
          onDone: () => {
            // Stream complete
          },
          onError: (err) => {
            console.error('Streaming error callback:', err);
          },
        },
        3,
        0.25
      );
    } catch (err: any) {
      // If streaming fails (e.g. proxy or old backend), fallback to non-streaming endpoint
      try {
        const response = await askKnowledgeBase(trimmed, 3, 0.25);
        setSessions((prev) =>
          prev.map((s) => {
            if (s.id === targetSessionId) {
              return {
                ...s,
                updatedAt: new Date().toISOString(),
                messages: s.messages.map((m) =>
                  m.id === assistantMsgId
                    ? {
                        ...m,
                        content: response.answer,
                        sources: response.sources || [],
                        detected_domain: response.detected_domain || undefined,
                        retrieval_status: response.retrieval_status || 'success',
                      }
                    : m
                ),
              };
            }
            return s;
          })
        );
      } catch (fallbackErr: any) {
        const errorContent = `Error: ${fallbackErr.message || err.message || 'Unable to retrieve answer.'}`;
        setSessions((prev) =>
          prev.map((s) => {
            if (s.id === targetSessionId) {
              return {
                ...s,
                updatedAt: new Date().toISOString(),
                messages: s.messages.map((m) =>
                  m.id === assistantMsgId
                    ? {
                        ...m,
                        content: errorContent,
                        isError: true,
                        retrieval_status: 'insufficient_context',
                      }
                    : m
                ),
              };
            }
            return s;
          })
        );
      }
    } finally {
      setIsGenerating(false);
    }
  };

  return (
    <ChatContext.Provider
      value={{
        sessions,
        activeSessionId,
        activeSession,
        isGenerating,
        health,
        createNewChat,
        selectSession,
        deleteSession,
        sendMessage,
        refreshHealth,
      }}
    >
      {children}
    </ChatContext.Provider>
  );
};

export const useChat = () => {
  const context = useContext(ChatContext);
  if (!context) {
    throw new Error('useChat must be used within a ChatProvider');
  }
  return context;
};
