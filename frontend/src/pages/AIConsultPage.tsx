import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import api from '../lib/api';
import { useAuth } from '../context/AuthContext';
import { supabase } from '../lib/supabase';
import { EmergencyBanner } from '../components/ui/EmergencyBanner';

interface ChatMessage {
  id?: string;
  session_id?: string;
  role: 'user' | 'assistant';
  content_en?: string;
  content_ur?: string;
  content?: string;
  is_emergency?: boolean;
  emergency_action?: any;
  risk_level?: string;
  recommended_specialty?: string;
  possible_causes?: string[];
  self_care?: string[];
  questions_for_doctor?: string[];
  created_at?: string;
  profile_updates?: Array<{
    id: string;
    text: string;
    operation: string;
    target_name: string;
    target_type: string;
    undone?: boolean;
  }>;
}

interface ChatSession {
  id: string;
  patient_id?: string;
  title: string;
  risk_level?: string;
  created_at?: string;
}

interface AIConsultPageProps {
  currentPatientId?: string;
}

export const AIConsultPage: React.FC<AIConsultPageProps> = ({ currentPatientId: propPatientId }) => {
  const { profile, refreshProfile } = useAuth();
  const currentPatientId = propPatientId || profile?.id || '';
  const { i18n } = useTranslation();
  const navigate = useNavigate();
  const isUrdu = i18n.language.startsWith('ur');

  // Sessions and Active Chat State
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string>('');
  const [searchQuery, setSearchQuery] = useState('');
  const [mobileDrawerOpen, setMobileDrawerOpen] = useState(false);
  const [loadingSessions, setLoadingSessions] = useState(false);

  // Rename & Delete state
  const [editingSessionId, setEditingSessionId] = useState<string | null>(null);
  const [renameText, setRenameText] = useState('');
  const [deleteTargetId, setDeleteTargetId] = useState<string | null>(null);

  // Profile Auto-Updates Undo State
  const [undoneUpdates, setUndoneUpdates] = useState<Set<string>>(new Set());

  const handleUndoProfileUpdate = async (logId: string) => {
    try {
      await api.post(`/api/profile/undo/${logId}`);
      setUndoneUpdates((prev) => new Set(prev).add(logId));
      if (refreshProfile) {
        await refreshProfile();
      }
      if (showMemoryInspector) {
        fetchMemoryDebug();
      }
    } catch (err) {
      console.error('Failed to undo profile update:', err);
    }
  };

  // Messages and Input State
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputText, setInputText] = useState('');
  const [loading, setLoading] = useState(false);
  const [activeEmergency, setActiveEmergency] = useState<{
    instructionEn?: string;
    instructionUr?: string;
    matchedTerm?: string;
  } | null>(null);

  // Memory Inspector State
  const [showMemoryInspector, setShowMemoryInspector] = useState(false);
  const [memoryDebugData, setMemoryDebugData] = useState<any>(null);
  const [loadingMemoryDebug, setLoadingMemoryDebug] = useState(false);

  const fetchMemoryDebug = async (sessionId?: string) => {
    const targetId = sessionId || activeSessionId;
    if (!targetId) return;
    setLoadingMemoryDebug(true);
    try {
      const res = await api.get(`/api/chat/debug/memory/${targetId}`);
      setMemoryDebugData(res.data);
    } catch (err) {
      console.warn('Failed to fetch memory debug info:', err);
    } finally {
      setLoadingMemoryDebug(false);
    }
  };

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const latestAssistantRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // 1. Fetch past sessions
  const fetchSessions = async () => {
    setLoadingSessions(true);
    try {
      const res = await api.get('/api/chat/sessions');
      if (res.data && res.data.length > 0) {
        setSessions(res.data);
        const targetId = activeSessionId && res.data.some((s: any) => s.id === activeSessionId)
          ? activeSessionId
          : res.data[0].id;
        setActiveSessionId(targetId);
        await fetchMessages(targetId);
      } else {
        // If no past sessions, create the initial new one
        await handleNewChat(false);
      }
    } catch (err) {
      console.warn('Could not fetch past chat sessions:', err);
    } finally {
      setLoadingSessions(false);
    }
  };

  useEffect(() => {
    fetchSessions();
  }, [currentPatientId]);

  // 2. Fetch messages for active session
  const fetchMessages = async (sid: string) => {
    if (!sid) return;
    try {
      const res = await api.get(`/api/chat/sessions/${sid}/messages`);
      if (res.data && res.data.length > 0) {
        const formatted = res.data.map((m: any) => ({
          id: m.id,
          session_id: m.session_id,
          role: m.role,
          content: m.content,
          content_en: m.meta?.response_en || m.content,
          content_ur: m.meta?.response_ur,
          is_emergency: m.meta?.is_emergency,
          emergency_action: m.meta?.emergency_action,
          risk_level: m.meta?.risk_level,
          recommended_specialty: m.meta?.specialty,
          possible_causes: m.meta?.possible_causes || [],
          self_care: m.meta?.self_care || [],
          questions_for_doctor: m.meta?.questions_for_doctor || [],
          profile_updates: m.meta?.profile_updates || [],
          created_at: m.created_at,
        }));
        setMessages(formatted);
      } else {
        setMessages([]);
      }
    } catch (err) {
      console.warn('Could not load session messages:', err);
      setMessages([]);
    }
  };

  useEffect(() => {
    if (activeSessionId) {
      fetchMessages(activeSessionId);
    }
  }, [activeSessionId]);

  // 3. Supabase Realtime subscription for active chat session
  useEffect(() => {
    if (!activeSessionId) return;

    const channel = supabase
      .channel(`chat_messages_${activeSessionId}`)
      .on(
        'postgres_changes',
        {
          event: 'INSERT',
          schema: 'public',
          table: 'chat_messages',
          filter: `session_id=eq.${activeSessionId}`,
        },
        (payload: any) => {
          const newRow = payload.new;
          if (!newRow) return;

          setMessages((prev) => {
            // Avoid duplicate additions
            if (prev.some((m) => m.id === String(newRow.id))) return prev;
            const newMsg: ChatMessage = {
              id: String(newRow.id),
              session_id: newRow.session_id,
              role: newRow.role,
              content: newRow.content,
              content_en: newRow.meta?.response_en || newRow.content,
              content_ur: newRow.meta?.response_ur,
              is_emergency: newRow.meta?.is_emergency,
              emergency_action: newRow.meta?.emergency_action,
              risk_level: newRow.meta?.risk_level,
              recommended_specialty: newRow.meta?.specialty,
              possible_causes: newRow.meta?.possible_causes || [],
              self_care: newRow.meta?.self_care || [],
              questions_for_doctor: newRow.meta?.questions_for_doctor || [],
              created_at: newRow.created_at,
            };
            return [...prev, newMsg];
          });
        }
      )
      .subscribe();

    return () => {
      supabase.removeChannel(channel);
    };
  }, [activeSessionId]);

  // Auto-scroll behavior:
  // When an assistant message arrives, scroll to the TOP/START of that message so the patient starts reading from the beginning.
  // When user sends a message or during loading, scroll to the bottom to show the question and typing indicator.
  useEffect(() => {
    const lastMsg = messages[messages.length - 1];
    if (lastMsg && lastMsg.role === 'assistant') {
      const timer = setTimeout(() => {
        if (latestAssistantRef.current) {
          latestAssistantRef.current.scrollIntoView({ behavior: 'smooth', block: 'start' });
        } else {
          messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
        }
      }, 50);
      return () => clearTimeout(timer);
    } else {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, loading]);

  // Create New Chat
  const handleNewChat = async (shouldFocusInput: boolean = true) => {
    try {
      const res = await api.post('/api/chat/session', {
        title: 'New Consultation',
      });
      const newSession: ChatSession = res.data;
      setSessions((prev) => [newSession, ...prev]);
      setActiveSessionId(newSession.id);
      setMessages([]);
      setMobileDrawerOpen(false);
      if (shouldFocusInput) {
        setTimeout(() => inputRef.current?.focus(), 100);
      }
    } catch (err) {
      console.error('Failed to create new chat session:', err);
    }
  };

  // Select an existing chat
  const handleSelectSession = (sid: string) => {
    setActiveSessionId(sid);
    fetchMessages(sid);
    setMobileDrawerOpen(false);
    if (showMemoryInspector) {
      fetchMemoryDebug(sid);
    }
  };

  // Start Inline Rename
  const handleStartRename = (s: ChatSession, e: React.MouseEvent) => {
    e.stopPropagation();
    setEditingSessionId(s.id);
    setRenameText(s.title);
  };

  // Submit Rename
  const handleSubmitRename = async (sid: string, e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!renameText.trim()) return;

    try {
      await api.patch(`/api/chat/sessions/${sid}`, {
        title: renameText.trim(),
      });
      setSessions((prev) =>
        prev.map((s) => (s.id === sid ? { ...s, title: renameText.trim() } : s))
      );
      setEditingSessionId(null);
    } catch (err) {
      console.error('Failed to rename session:', err);
      setEditingSessionId(null);
    }
  };

  // Delete Chat Session
  const handleDeleteSession = async (sid: string) => {
    try {
      await api.delete(`/api/chat/sessions/${sid}`);
      setSessions((prev) => prev.filter((s) => s.id !== sid));
      setDeleteTargetId(null);

      // If active session was deleted, switch to first available or create new
      if (activeSessionId === sid) {
        const remaining = sessions.filter((s) => s.id !== sid);
        if (remaining.length > 0) {
          setActiveSessionId(remaining[0].id);
        } else {
          await handleNewChat(false);
        }
      }
    } catch (err) {
      console.error('Failed to delete chat session:', err);
      setDeleteTargetId(null);
    }
  };

  // Send message
  const handleSendMessage = async (textToSend?: string) => {
    const content = (textToSend || inputText).trim();
    if (!content || loading) return;

    let targetSessionId = activeSessionId;
    if (!targetSessionId) {
      const res = await api.post('/api/chat/session', { title: 'New Consultation' });
      targetSessionId = res.data.id;
      setSessions((prev) => [res.data, ...prev]);
      setActiveSessionId(targetSessionId);
    }

    setInputText('');
    const userMsg: ChatMessage = {
      role: 'user',
      content: content,
    };
    setMessages((prev) => [...prev, userMsg]);
    setLoading(true);

    try {
      const res = await api.post('/api/chat/message', {
        session_id: targetSessionId,
        content: content,
        lang: isUrdu ? 'ur' : 'en',
      });

      const replyData = res.data;

      // Update session title if auto-titling generated a new title
      if (replyData.session_title) {
        setSessions((prev) =>
          prev.map((s) =>
            s.id === targetSessionId ? { ...s, title: replyData.session_title } : s
          )
        );
      }

      if (replyData.is_emergency) {
        setActiveEmergency({
          instructionEn: replyData.content_en,
          instructionUr: replyData.content_ur,
          matchedTerm: replyData.emergency_action?.matched_term,
        });
      }

      const assistantMsg: ChatMessage = {
        role: 'assistant',
        content_en: replyData.content_en,
        content_ur: replyData.content_ur,
        is_emergency: replyData.is_emergency,
        emergency_action: replyData.emergency_action,
        risk_level: replyData.risk_level,
        recommended_specialty: replyData.recommended_specialty,
        possible_causes: replyData.possible_causes,
        self_care: replyData.self_care,
        questions_for_doctor: replyData.questions_for_doctor,
        profile_updates: replyData.profile_updates || [],
      };

      setMessages((prev) => [...prev, assistantMsg]);
      if (showMemoryInspector) {
        fetchMemoryDebug(targetSessionId);
      }
    } catch (err) {
      console.error('Chat error:', err);
      const mockReply: ChatMessage = {
        role: 'assistant',
        content_en:
          'Based on the symptoms you shared, mild headache and fatigue may relate to dehydration, eye strain, or sleep changes. If symptoms persist or worsen, seeing a General Physician is recommended.',
        content_ur:
          'آپ کی بیان کردہ علامات کے مطابق، ہلکا سر درد اور سستی پانی کی کمی یا نیند میں بے قاعدگی کی وجہ سے ہو سکتی ہے۔ اگر علامات برقرار رہیں تو جنرل فزیشن سے معائنہ کروائیں۔',
        risk_level: 'LOW',
        recommended_specialty: 'General Physician',
        possible_causes: ['May relate to mild dehydration', 'May relate to lack of sleep or screen eye strain'],
        self_care: ['Drink plenty of water and rest in a quiet, dim room', 'Limit screen time before bed'],
        questions_for_doctor: ['Could this be related to blood pressure or eye strain?', 'Should I have any routine blood work done?'],
      };
      setMessages((prev) => [...prev, mockReply]);
    } finally {
      setLoading(false);
    }
  };

  // Grouping Sessions by Date (Today, Yesterday, Previous 7 Days, Older)
  const groupSessionsByDate = (items: ChatSession[]) => {
    const filtered = items.filter((s) =>
      s.title.toLowerCase().includes(searchQuery.toLowerCase().trim())
    );

    const groups: { [key: string]: ChatSession[] } = {
      Today: [],
      Yesterday: [],
      'Previous 7 Days': [],
      Older: [],
    };

    const now = new Date();
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const yesterday = new Date(today);
    yesterday.setDate(yesterday.getDate() - 1);
    const sevenDaysAgo = new Date(today);
    sevenDaysAgo.setDate(sevenDaysAgo.getDate() - 7);

    filtered.forEach((s) => {
      const d = s.created_at ? new Date(s.created_at) : new Date();
      const sessionDate = new Date(d.getFullYear(), d.getMonth(), d.getDate());

      if (sessionDate.getTime() === today.getTime()) {
        groups.Today.push(s);
      } else if (sessionDate.getTime() === yesterday.getTime()) {
        groups.Yesterday.push(s);
      } else if (sessionDate.getTime() >= sevenDaysAgo.getTime()) {
        groups['Previous 7 Days'].push(s);
      } else {
        groups.Older.push(s);
      }
    });

    return groups;
  };

  const groupedSessions = groupSessionsByDate(sessions);
  const activeSession = sessions.find((s) => s.id === activeSessionId);

  // Render Sidebar Content (Shared between desktop and mobile drawer)
  const renderSidebarContent = () => (
    <div className="flex flex-col h-full bg-surface-container-lowest select-none">
      {/* Top Action Header */}
      <div className="p-3.5 space-y-2.5 border-b border-outline-variant/50">
        <button
          onClick={() => handleNewChat(true)}
          className="w-full flex items-center justify-between px-4 py-2.5 rounded-2xl bg-primary text-on-primary font-bold text-xs shadow-xs hover:opacity-95 active:scale-98 transition-all"
        >
          <span className="flex items-center gap-2">
            <span className="material-symbols-outlined text-lg">add</span>
            <span>New Chat</span>
          </span>
          <span className="material-symbols-outlined text-sm opacity-80">edit_square</span>
        </button>

        {/* Search Input */}
        <div className="relative">
          <span className="material-symbols-outlined absolute left-3 top-2.5 text-secondary text-base">
            search
          </span>
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search past chats..."
            className="w-full bg-surface-container-low border border-outline-variant/60 rounded-xl pl-9 pr-7 py-1.5 text-xs text-on-surface focus:outline-none focus:border-primary transition-colors"
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery('')}
              className="absolute right-2.5 top-2 text-secondary hover:text-on-surface text-xs"
            >
              <span className="material-symbols-outlined text-sm">close</span>
            </button>
          )}
        </div>
      </div>

      {/* Grouped Chats Scroll Area */}
      <div className="flex-1 overflow-y-auto px-2 py-3 space-y-4">
        {loadingSessions ? (
          <div className="p-4 text-center text-xs text-secondary animate-pulse">
            Loading conversations...
          </div>
        ) : (
          Object.entries(groupedSessions).map(([groupTitle, items]) => {
            if (items.length === 0) return null;
            return (
              <div key={groupTitle} className="space-y-1">
                <div className="px-3 py-1 text-[10px] font-bold uppercase tracking-wider text-secondary/80">
                  {groupTitle}
                </div>
                {items.map((s) => {
                  const isActive = s.id === activeSessionId;
                  const isEditing = editingSessionId === s.id;

                  return (
                    <div
                      key={s.id}
                      onClick={() => handleSelectSession(s.id)}
                      className={`group relative flex items-center justify-between px-3 py-2 rounded-xl text-xs cursor-pointer transition-all ${
                        isActive
                          ? 'bg-primary-container/20 text-primary font-bold shadow-2xs'
                          : 'text-on-surface hover:bg-surface-container-low'
                      }`}
                    >
                      {/* Left: Icon and Title */}
                      <div className="flex items-center gap-2 min-w-0 flex-1 pr-2">
                        <span
                          className={`material-symbols-outlined text-base shrink-0 ${
                            isActive ? 'text-primary' : 'text-secondary'
                          }`}
                        >
                          chat_bubble_outline
                        </span>

                        {isEditing ? (
                          <form
                            onSubmit={(e) => handleSubmitRename(s.id, e)}
                            onClick={(e) => e.stopPropagation()}
                            className="flex items-center gap-1 w-full"
                          >
                            <input
                              type="text"
                              autoFocus
                              value={renameText}
                              onChange={(e) => setRenameText(e.target.value)}
                              className="w-full bg-surface-container-lowest border border-primary px-1.5 py-0.5 rounded text-xs text-on-surface focus:outline-none"
                            />
                            <button
                              type="submit"
                              className="text-primary hover:text-on-surface p-0.5"
                              title="Save"
                            >
                              <span className="material-symbols-outlined text-sm">check</span>
                            </button>
                            <button
                              type="button"
                              onClick={(e) => {
                                e.stopPropagation();
                                setEditingSessionId(null);
                              }}
                              className="text-secondary hover:text-on-surface p-0.5"
                              title="Cancel"
                            >
                              <span className="material-symbols-outlined text-sm">close</span>
                            </button>
                          </form>
                        ) : (
                          <span className="truncate">{s.title}</span>
                        )}
                      </div>

                      {/* Right: Actions Menu (Rename, Delete) */}
                      {!isEditing && (
                        <div
                          className={`flex items-center gap-0.5 ${
                            isActive ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'
                          } transition-opacity`}
                          onClick={(e) => e.stopPropagation()}
                        >
                          <button
                            onClick={(e) => handleStartRename(s, e)}
                            className="p-1 rounded text-secondary hover:text-primary hover:bg-surface-container transition-colors"
                            title="Rename chat"
                          >
                            <span className="material-symbols-outlined text-sm">edit</span>
                          </button>
                          <button
                            onClick={() => setDeleteTargetId(s.id)}
                            className="p-1 rounded text-secondary hover:text-error hover:bg-error-container/20 transition-colors"
                            title="Delete chat"
                          >
                            <span className="material-symbols-outlined text-sm">delete</span>
                          </button>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            );
          })
        )}

        {!loadingSessions &&
          Object.values(groupedSessions).every((arr) => arr.length === 0) && (
            <div className="p-6 text-center text-xs text-secondary">
              {searchQuery ? 'No matching chats found.' : 'No conversations yet.'}
            </div>
          )}
      </div>

      {/* Footer Info */}
      <div className="p-3 border-t border-outline-variant/40 text-[10px] text-secondary text-center">
        Zero-LLM Emergency Interception • Gemma 4
      </div>
    </div>
  );

  return (
    <div className="flex h-full w-full overflow-hidden bg-background">
      {/* ── DESKTOP PERSISTENT CHAT HISTORY SIDEBAR ───────────────────────── */}
      <aside className="hidden md:flex w-72 lg:w-80 border-r border-outline-variant shadow-xs shrink-0 flex-col h-full z-20">
        {renderSidebarContent()}
      </aside>

      {/* ── MOBILE SLIDE-IN DRAWER OVERLAY ─────────────────────────────────── */}
      {mobileDrawerOpen && (
        <div className="md:hidden fixed inset-0 z-50 flex">
          {/* Backdrop overlay */}
          <div
            onClick={() => setMobileDrawerOpen(false)}
            className="fixed inset-0 bg-black/40 backdrop-blur-xs transition-opacity"
          />
          {/* Drawer Canvas */}
          <div className="relative w-72 max-w-[85vw] h-full shadow-2xl z-10 animate-in slide-in-from-left duration-200">
            {renderSidebarContent()}
          </div>
        </div>
      )}

      {/* ── DELETE CONFIRMATION MODAL ───────────────────────────────────────── */}
      {deleteTargetId && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-xs">
          <div className="bg-surface-container-lowest border border-outline-variant rounded-3xl p-6 max-w-sm w-full shadow-xl animate-in zoom-in-95">
            <div className="w-10 h-10 rounded-2xl bg-error-container text-on-error-container flex items-center justify-center mb-3">
              <span className="material-symbols-outlined text-xl">delete_forever</span>
            </div>
            <h3 className="text-base font-bold text-on-surface">Delete Conversation?</h3>
            <p className="text-xs text-secondary mt-1 leading-relaxed">
              This will permanently delete this conversation and its associated message history.
            </p>
            <div className="flex items-center justify-end gap-2 mt-5">
              <button
                onClick={() => setDeleteTargetId(null)}
                className="px-4 py-2 rounded-xl text-xs font-semibold text-secondary hover:bg-surface-container transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={() => handleDeleteSession(deleteTargetId)}
                className="px-4 py-2 rounded-xl bg-error text-on-error text-xs font-bold shadow-xs hover:opacity-95 transition-all"
              >
                Delete
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── MAIN CHAT WORKSPACE CANVAS (100dvh pinned) ──────────────────────── */}
      <main className="flex-1 flex flex-col h-full min-w-0 overflow-hidden relative">
        {/* Top Chat App Bar */}
        <div className="h-14 border-b border-outline-variant/60 bg-surface-container-lowest flex items-center justify-between px-4 sm:px-6 shrink-0 z-10">
          <div className="flex items-center gap-3 min-w-0">
            {/* Mobile Hamburger toggle for chats */}
            <button
              onClick={() => setMobileDrawerOpen(true)}
              className="md:hidden p-1.5 rounded-xl text-on-surface-variant hover:bg-surface-container transition-colors"
              title="Open Chat History"
            >
              <span className="material-symbols-outlined text-xl">menu_open</span>
            </button>

            {/* Chat Icon & Active Title */}
            <div className="flex items-center gap-2 min-w-0">
              <div className="w-7 h-7 rounded-xl bg-primary-container text-on-primary-container flex items-center justify-center shrink-0 text-xs shadow-2xs">
                <span className="material-symbols-outlined text-sm" style={{ fontVariationSettings: "'FILL' 1" }}>
                  smart_toy
                </span>
              </div>
              <h2 className="text-xs sm:text-sm font-bold text-on-surface truncate max-w-[200px] sm:max-w-md">
                {activeSession?.title || 'Symptom Consultation'}
              </h2>
            </div>
          </div>

          {/* Right Header Status Badges */}
          <div className="flex items-center gap-2">
            {activeSession?.risk_level && (
              <span
                className={`text-[10px] font-bold px-2.5 py-0.5 rounded-full uppercase tracking-wider ${
                  activeSession.risk_level === 'CRITICAL'
                    ? 'bg-error-container text-on-error-container'
                    : 'bg-primary-container text-on-primary-container'
                }`}
              >
                {activeSession.risk_level}
              </span>
            )}
            <button
              onClick={() => {
                const next = !showMemoryInspector;
                setShowMemoryInspector(next);
                if (next) fetchMemoryDebug();
              }}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl border text-xs font-semibold transition-all ${
                showMemoryInspector
                  ? 'bg-primary text-on-primary border-primary shadow-xs'
                  : 'border-outline-variant hover:border-primary text-secondary hover:text-primary bg-surface-container-low'
              }`}
              title="Inspect Active Injected Context & Memory"
            >
              <span className="material-symbols-outlined text-sm">psychology</span>
              <span className="hidden sm:inline">Memory</span>
            </button>
            <button
              onClick={() => handleNewChat(true)}
              className="hidden sm:flex items-center gap-1 px-3 py-1.5 rounded-xl border border-outline-variant hover:border-primary text-xs font-semibold text-primary transition-colors"
              title="Start New Chat"
            >
              <span className="material-symbols-outlined text-sm">add</span>
              <span>New</span>
            </button>
          </div>
        </div>

        {/* ── CHAT AND INSPECTOR HORIZONTAL CONTAINER ───────────────────── */}
        <div className="flex-1 flex min-h-0 overflow-hidden relative">
          <div className="flex-1 flex flex-col h-full min-w-0 overflow-hidden relative">
            {/* Emergency Alert (if triggered in current turn) */}
        {activeEmergency && (
          <div className="px-4 py-2 shrink-0">
            <EmergencyBanner
              instructionEn={activeEmergency.instructionEn}
              instructionUr={activeEmergency.instructionUr}
              matchedTerm={activeEmergency.matchedTerm}
              onDismiss={() => setActiveEmergency(null)}
            />
          </div>
        )}

        {/* ── MESSAGES VIEWPORT ─────────────────────────────────────────────── */}
        <div className="flex-1 overflow-y-auto px-4 sm:px-6 md:px-8 py-6 space-y-6">
          {/* Empty State (Clean Minimalist) */}
          {messages.length === 0 && (
            <div className="max-w-md mx-auto py-16 sm:py-24 flex flex-col items-center text-center animate-in fade-in duration-300">
              <div className="w-14 h-14 rounded-3xl bg-primary-container text-on-primary-container flex items-center justify-center shadow-xs mb-4">
                <span className="material-symbols-outlined text-3xl" style={{ fontVariationSettings: "'FILL' 1" }}>
                  medical_services
                </span>
              </div>

              <h1 className="text-xl sm:text-2xl font-extrabold text-on-surface tracking-tight">
                {isUrdu ? 'اے آئی ڈاکٹر مشورہ' : 'AI Doctor Consultation'}
              </h1>
              <p className="text-xs sm:text-sm text-secondary mt-1.5 leading-relaxed">
                {isUrdu
                  ? 'اپنی علامات یا طبی سوال نیچے لکھ کر مشورہ شروع کریں۔'
                  : 'Describe your symptoms or ask a health question below to begin.'}
              </p>
            </div>
          )}

          {/* Active Messages */}
          {messages.map((msg, index) => {
            const isLatestAssistant = index === messages.length - 1 && msg.role === 'assistant';
            return (
              <div
                key={index}
                ref={isLatestAssistant ? latestAssistantRef : undefined}
                className={`flex items-start gap-3 scroll-mt-6 ${
                  msg.role === 'user' ? 'justify-end' : 'justify-start'
                }`}
              >
              {msg.role === 'assistant' && (
                <div className="w-8 h-8 rounded-xl bg-primary-container text-on-primary-container flex items-center justify-center shrink-0 shadow-2xs mt-1">
                  <span className="material-symbols-outlined text-lg" style={{ fontVariationSettings: "'FILL' 1" }}>
                    smart_toy
                  </span>
                </div>
              )}

              <div
                className={`max-w-[85%] sm:max-w-[75%] rounded-3xl p-4 sm:p-5 shadow-xs transition-all ${
                  msg.role === 'user'
                    ? 'bg-primary-container text-on-primary-container rounded-tr-xs font-medium text-xs sm:text-sm'
                    : msg.is_emergency
                    ? 'bg-error-container text-on-error-container border border-error/30 rounded-tl-xs'
                    : 'bg-surface-container-lowest border border-outline-variant/60 text-on-surface rounded-tl-xs'
                }`}
              >
                {msg.role === 'user' && <p className="leading-relaxed whitespace-pre-wrap">{msg.content}</p>}

                {msg.role === 'assistant' && (
                  <div className="space-y-4">
                    {/* Assessment Header */}
                    {msg.risk_level && (
                      <div className="flex items-center justify-between pb-2 border-b border-outline-variant/30">
                        <span className="text-[10px] font-bold text-secondary uppercase tracking-wider">
                          Clinical Assessment
                        </span>
                        <span
                          className={`text-[10px] font-bold px-2.5 py-0.5 rounded-full uppercase tracking-wider ${
                            msg.risk_level === 'CRITICAL'
                              ? 'bg-error-container text-on-error-container'
                              : msg.risk_level === 'HIGH'
                              ? 'bg-[#FEF3C7] text-[#D97706]'
                              : 'bg-[#DCFCE7] text-[#16A34A]'
                          }`}
                        >
                          {msg.risk_level} Urgency
                        </span>
                      </div>
                    )}

                    {/* Primary Response Content */}
                    <div className="text-xs sm:text-sm text-on-surface leading-relaxed space-y-2">
                      <p>{isUrdu && msg.content_ur ? msg.content_ur : msg.content_en || msg.content}</p>
                      {!isUrdu && msg.content_ur && (
                        <p
                          dir="rtl"
                          className="text-xs text-secondary pt-2 border-t border-outline-variant/30 font-urdu leading-relaxed"
                        >
                          {msg.content_ur}
                        </p>
                      )}
                    </div>

                    {/* Possible Factors List */}
                    {msg.possible_causes && msg.possible_causes.length > 0 && (
                      <div className="bg-surface-container-low rounded-2xl p-3 border border-outline-variant/40 text-xs">
                        <span className="font-bold text-on-surface block mb-1">
                          Factors to Discuss with Your Doctor:
                        </span>
                        <ul className="list-disc list-inside space-y-1 text-secondary">
                          {msg.possible_causes.map((c, i) => (
                            <li key={i}>{c}</li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {/* Safe Self-Care Guidance */}
                    {msg.self_care && msg.self_care.length > 0 && (
                      <div className="bg-[#DCFCE7]/60 rounded-2xl p-3 border border-[#16A34A]/20 text-xs">
                        <span className="font-bold text-[#16A34A] block mb-1">
                          Safe Comfort Guidance (No Drug Dosing):
                        </span>
                        <ul className="list-disc list-inside space-y-1 text-[#15803D]">
                          {msg.self_care.map((sc, i) => (
                            <li key={i}>{sc}</li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {/* Specialist Referral Button */}
                    {msg.recommended_specialty && (
                      <div className="pt-1">
                        <button
                          onClick={() =>
                            navigate(
                              `/doctors?specialty=${encodeURIComponent(msg.recommended_specialty || '')}`
                            )
                          }
                          className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-surface-container hover:bg-surface-container-high text-primary border border-outline-variant/60 text-xs font-bold transition-all shadow-2xs"
                        >
                          <span className="material-symbols-outlined text-base">location_on</span>
                          <span>Find Nearby {msg.recommended_specialty}</span>
                          <span className="material-symbols-outlined text-sm">arrow_forward</span>
                        </button>
                      </div>
                    )}

                    {/* Auto-Profile Update Transparency Chip with Undo */}
                    {msg.profile_updates && msg.profile_updates.length > 0 && (
                      <div className="pt-2 flex flex-col gap-1.5 border-t border-outline-variant/30">
                        {msg.profile_updates.map((chip, i) => {
                          const isUndone = undoneUpdates.has(chip.id);
                          return (
                            <div
                              key={i}
                              className="inline-flex items-center justify-between gap-2 px-3 py-1.5 rounded-xl bg-primary-container/20 border border-primary/20 text-on-surface text-xs"
                            >
                              <div className="flex items-center gap-2">
                                <span className="material-symbols-outlined text-primary text-sm" style={{ fontVariationSettings: "'FILL' 1" }}>
                                  auto_fix_high
                                </span>
                                <span className="font-medium">
                                  {chip.text || `Profile updated: ${chip.target_name}`}
                                </span>
                              </div>
                              {isUndone ? (
                                <span className="text-[11px] font-bold text-secondary flex items-center gap-1">
                                  <span className="material-symbols-outlined text-xs">undo</span>
                                  Reverted
                                </span>
                              ) : (
                                <button
                                  type="button"
                                  onClick={() => handleUndoProfileUpdate(chip.id)}
                                  className="px-2 py-0.5 rounded-md bg-surface-container hover:bg-surface-container-high text-primary font-bold text-[11px] transition-all shadow-2xs hover:underline cursor-pointer"
                                >
                                  Undo
                                </button>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </div>
                )}
              </div>

              {msg.role === 'user' && (
                <div className="w-8 h-8 rounded-xl bg-surface-container text-secondary flex items-center justify-center shrink-0 shadow-2xs mt-1">
                  <span className="material-symbols-outlined text-lg">account_circle</span>
                </div>
              )}
            </div>
            );
          })}

          {loading && (
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-xl bg-primary/10 text-primary flex items-center justify-center shrink-0 shadow-2xs">
                <span className="material-symbols-outlined text-base">smart_toy</span>
              </div>
              <div className="bg-surface-container-lowest border border-outline-variant/60 rounded-2xl px-4 py-2.5 flex items-center gap-1.5 shadow-2xs">
                <span className="w-2 h-2 rounded-full bg-primary/60 animate-bounce" style={{ animationDelay: '0ms' }} />
                <span className="w-2 h-2 rounded-full bg-primary/60 animate-bounce" style={{ animationDelay: '150ms' }} />
                <span className="w-2 h-2 rounded-full bg-primary/60 animate-bounce" style={{ animationDelay: '300ms' }} />
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* ── STICKY BOTTOM INPUT CANVAS (Pinned above keyboard, 100dvh) ────── */}
        <div className="p-3 sm:p-4 border-t border-outline-variant/60 bg-surface-container-lowest shrink-0">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleSendMessage();
            }}
            className="max-w-4xl mx-auto flex items-center gap-2"
          >
            <div className="relative flex-1">
              <input
                ref={inputRef}
                type="text"
                value={inputText}
                onChange={(e) => setInputText(e.target.value)}
                placeholder={
                  isUrdu
                    ? 'اپنی علامات لکھیں (مثلاً: دو دن سے سر درد ہے)'
                    : 'Describe your symptoms or ask a health question…'
                }
                className="w-full bg-surface-container-low border border-outline-variant/60 rounded-2xl pl-4 pr-10 py-3 text-xs sm:text-sm text-on-surface focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary transition-all"
              />
            </div>

            <button
              type="submit"
              disabled={!inputText.trim() || loading}
              className={`p-3 rounded-2xl font-bold shadow-xs transition-all shrink-0 ${
                !inputText.trim() || loading
                  ? 'bg-surface-container text-secondary cursor-not-allowed'
                  : 'bg-primary text-on-primary hover:opacity-95 active:scale-95'
              }`}
              title="Send consultation message"
            >
              <span className="material-symbols-outlined text-xl">arrow_upward</span>
            </button>
          </form>

          {/* Under-Input Safety Disclaimer */}
          <div className="max-w-4xl mx-auto mt-2 text-center text-[10px] text-secondary flex items-center justify-center gap-1.5">
            <span className="material-symbols-outlined text-xs text-error">emergency</span>
            <span>Emergency Warning: For chest pain, sudden numbness, or shortness of breath, call Rescue 1122 immediately.</span>
          </div>
        </div>
      </div>

      {/* ── MEMORY & CONTEXT INSPECTOR DRAWER ────────────────────────── */}
      {showMemoryInspector && (
        <aside className="w-80 lg:w-96 border-l border-outline-variant bg-surface-container-lowest flex flex-col h-full shrink-0 z-20 animate-in slide-in-from-right duration-200">
          {/* Header */}
          <div className="p-3.5 border-b border-outline-variant flex items-center justify-between bg-surface-container-low/50">
            <div className="flex items-center gap-2">
              <div className="w-7 h-7 rounded-lg bg-primary/10 text-primary flex items-center justify-center">
                <span className="material-symbols-outlined text-base">psychology</span>
              </div>
              <div>
                <h3 className="text-xs font-bold text-on-surface">Memory Inspector</h3>
                <p className="text-[10px] text-secondary">Injected context & profile truth</p>
              </div>
            </div>
            <div className="flex items-center gap-1">
              <button
                onClick={() => fetchMemoryDebug()}
                disabled={loadingMemoryDebug}
                className="p-1 rounded-lg text-secondary hover:text-on-surface hover:bg-surface-container transition-colors"
                title="Refresh memory state"
              >
                <span className={`material-symbols-outlined text-base ${loadingMemoryDebug ? 'animate-spin' : ''}`}>
                  refresh
                </span>
              </button>
              <button
                onClick={() => setShowMemoryInspector(false)}
                className="p-1 rounded-lg text-secondary hover:text-on-surface hover:bg-surface-container transition-colors"
                title="Close Inspector"
              >
                <span className="material-symbols-outlined text-base">close</span>
              </button>
            </div>
          </div>

          {/* Inspector Content */}
          <div className="flex-1 overflow-y-auto p-4 space-y-4 text-xs">
            {loadingMemoryDebug ? (
              <div className="flex flex-col items-center justify-center py-12 text-secondary space-y-2">
                <span className="material-symbols-outlined text-2xl animate-spin text-primary">progress_activity</span>
                <span className="text-[11px]">Loading prompt context & memories...</span>
              </div>
            ) : memoryDebugData ? (
              <>
                {/* 1. Patient Profile (Source of Truth) */}
                <div className="rounded-2xl border border-outline-variant/60 bg-surface-container-low/40 p-3 space-y-2">
                  <div className="flex items-center justify-between font-bold text-on-surface text-[11px]">
                    <span className="flex items-center gap-1.5">
                      <span className="material-symbols-outlined text-sm text-primary">badge</span>
                      Patient Profile (Source of Truth)
                    </span>
                    <span className="text-[9px] uppercase px-1.5 py-0.5 rounded bg-primary-container text-on-primary-container">
                      Live DB
                    </span>
                  </div>

                  <div className="space-y-1.5 pt-1 text-[11px]">
                    <div>
                      <span className="text-secondary font-medium block text-[10px]">Active Conditions:</span>
                      <div className="flex flex-wrap gap-1 mt-0.5">
                        {(memoryDebugData.profile_injected?.active_conditions || []).length > 0 ? (
                          memoryDebugData.profile_injected.active_conditions.map((c: string, i: number) => (
                            <span key={i} className="px-2 py-0.5 rounded-full bg-primary/10 text-primary font-semibold text-[10px]">
                              {c}
                            </span>
                          ))
                        ) : (
                          <span className="text-secondary/70 italic text-[10px]">None recorded</span>
                        )}
                      </div>
                    </div>

                    <div>
                      <span className="text-secondary font-medium block text-[10px]">Resolved Conditions:</span>
                      <div className="flex flex-wrap gap-1 mt-0.5">
                        {(memoryDebugData.profile_injected?.resolved_conditions || []).length > 0 ? (
                          memoryDebugData.profile_injected.resolved_conditions.map((c: string, i: number) => (
                            <span key={i} className="px-2 py-0.5 rounded-full bg-surface-container text-secondary line-through text-[10px]">
                              {c}
                            </span>
                          ))
                        ) : (
                          <span className="text-secondary/70 italic text-[10px]">None</span>
                        )}
                      </div>
                    </div>

                    <div>
                      <span className="text-secondary font-medium block text-[10px]">Known Allergies:</span>
                      <div className="flex flex-wrap gap-1 mt-0.5">
                        {(memoryDebugData.profile_injected?.allergies || []).length > 0 ? (
                          memoryDebugData.profile_injected.allergies.map((a: string, i: number) => (
                            <span key={i} className="px-2 py-0.5 rounded-full bg-error-container text-on-error-container font-semibold text-[10px]">
                              {a}
                            </span>
                          ))
                        ) : (
                          <span className="text-secondary/70 italic text-[10px]">None recorded</span>
                        )}
                      </div>
                    </div>

                    <div>
                      <span className="text-secondary font-medium block text-[10px]">Active Medications:</span>
                      <div className="flex flex-wrap gap-1 mt-0.5">
                        {(memoryDebugData.profile_injected?.active_medications || []).length > 0 ? (
                          memoryDebugData.profile_injected.active_medications.map((m: string, i: number) => (
                            <span key={i} className="px-2 py-0.5 rounded-full bg-[#EDE9FE] text-[#6D28D9] font-medium text-[10px]">
                              {m}
                            </span>
                          ))
                        ) : (
                          <span className="text-secondary/70 italic text-[10px]">None recorded</span>
                        )}
                      </div>
                    </div>
                  </div>
                </div>

                {/* 2. Recent Chat Summaries (Last 3 Deterministic) */}
                <div className="rounded-2xl border border-outline-variant/60 bg-surface-container-low/40 p-3 space-y-2">
                  <div className="flex items-center justify-between font-bold text-on-surface text-[11px]">
                    <span className="flex items-center gap-1.5">
                      <span className="material-symbols-outlined text-sm text-secondary">history_edu</span>
                      Past Session Summaries
                    </span>
                    <span className="text-[10px] text-secondary">
                      {memoryDebugData.past_summaries_injected?.length || 0} loaded
                    </span>
                  </div>

                  <div className="space-y-2 pt-1">
                    {(memoryDebugData.past_summaries_injected || []).length > 0 ? (
                      memoryDebugData.past_summaries_injected.map((s: any, i: number) => (
                        <div key={i} className="p-2 rounded-xl bg-surface-container-lowest border border-outline-variant/40 space-y-1">
                          <p className="text-[11px] text-on-surface leading-snug">{s.summary || s.content}</p>
                          {s.session_id && (
                            <span className="text-[9px] text-secondary font-mono truncate block">
                              Session: {s.session_id.substring(0, 8)}...
                            </span>
                          )}
                        </div>
                      ))
                    ) : (
                      <p className="text-[10px] text-secondary/70 italic">No previous consultation summaries yet.</p>
                    )}
                  </div>
                </div>

                {/* 3. Semantic Memory Retrieved (Vector Search) */}
                <div className="rounded-2xl border border-outline-variant/60 bg-surface-container-low/40 p-3 space-y-2">
                  <div className="flex items-center justify-between font-bold text-on-surface text-[11px]">
                    <span className="flex items-center gap-1.5">
                      <span className="material-symbols-outlined text-sm text-secondary">hub</span>
                      Semantic Memory (Vector Search)
                    </span>
                    <span className="text-[10px] text-secondary">
                      {memoryDebugData.semantic_memories_retrieved?.length || 0} matches
                    </span>
                  </div>

                  <div className="space-y-2 pt-1">
                    {(memoryDebugData.semantic_memories_retrieved || []).length > 0 ? (
                      memoryDebugData.semantic_memories_retrieved.map((m: any, i: number) => (
                        <div key={i} className="p-2 rounded-xl bg-surface-container-lowest border border-outline-variant/40 space-y-1">
                          <div className="flex items-center justify-between">
                            <span className="text-[9px] font-bold text-primary px-1.5 py-0.5 rounded bg-primary/10">
                              Score: {typeof m.similarity === 'number' ? m.similarity.toFixed(3) : 'N/A'}
                            </span>
                          </div>
                          <p className="text-[11px] text-on-surface leading-snug">{m.content}</p>
                        </div>
                      ))
                    ) : (
                      <p className="text-[10px] text-secondary/70 italic">No semantic memory match above threshold (0.25).</p>
                    )}
                  </div>
                </div>

                {/* 4. Prompt Preview Accordion */}
                {memoryDebugData.raw_prompt_preview && (
                  <details className="rounded-2xl border border-outline-variant/60 bg-surface-container-low/40 p-3 group">
                    <summary className="font-bold text-on-surface text-[11px] cursor-pointer flex items-center justify-between select-none">
                      <span className="flex items-center gap-1.5">
                        <span className="material-symbols-outlined text-sm text-secondary">code</span>
                        Raw Prompt Injected
                      </span>
                      <span className="material-symbols-outlined text-sm text-secondary group-open:rotate-180 transition-transform">
                        expand_more
                      </span>
                    </summary>
                    <pre className="mt-2 p-2.5 rounded-xl bg-surface-container-lowest text-[10px] text-on-surface font-mono whitespace-pre-wrap max-h-60 overflow-y-auto border border-outline-variant/40 leading-relaxed">
                      {memoryDebugData.raw_prompt_preview}
                    </pre>
                  </details>
                )}
              </>
            ) : (
              <div className="text-center py-8 text-secondary">
                <p className="text-xs">No active debug info for this session.</p>
              </div>
            )}
          </div>
        </aside>
      )}
    </div>
      </main>
    </div>
  );
};
