import { useCallback, useEffect, useState } from 'react';
import './App.css';

// --- Types ---

type Tab = 'dashboard' | 'chat' | 'agents' | 'settings' | 'memory';

interface ProviderDef {
 id: string;
 name: string;
 color: string;
 icon: string;
 authType: 'api_key' | 'oauth';
 models: ModelDef[];
}

interface ModelDef {
 id: string;
 name: string;
 inputPrice?: number; // $/1M tokens
 outputPrice?: number; // $/1M tokens
 contextWindow?: number;
 tags?: string[];
}

interface ProviderStatus {
 name: string;
 configured: boolean;
 default: boolean;
}

interface MemoryItem {
 id: string;
 content: string;
 metadata: Record<string, unknown>;
 score?: number;
}

// --- Provider Catalog with Pricing ---

const PROVIDERS: ProviderDef[] = [
 {
 id: 'anthropic',
 name: 'Claude',
 color: '#d97706',
 icon: '🟠',
 authType: 'api_key',
 models: [
 { id: 'claude-opus-4-20250514', name: 'Opus 4', inputPrice: 15, outputPrice: 75, contextWindow: 200000, tags: ['flagship', 'reasoning'] },
 { id: 'claude-sonnet-4-20250514', name: 'Sonnet 4', inputPrice: 3, outputPrice: 15, contextWindow: 200000, tags: ['balanced'] },
 { id: 'claude-haiku-3-5-20241022', name: 'Haiku 3.5', inputPrice: 0.8, outputPrice: 4, contextWindow: 200000, tags: ['fast', 'cheap'] },
 ],
 },
 {
 id: 'openai',
 name: 'Codex / GPT',
 color: '#10b981',
 icon: '🟢',
 authType: 'oauth',
 models: [
 { id: 'o3', name: 'o3', inputPrice: 2, outputPrice: 8, contextWindow: 200000, tags: ['reasoning'] },
 { id: 'gpt-4o', name: 'GPT-4o', inputPrice: 2.5, outputPrice: 10, contextWindow: 128000, tags: ['balanced'] },
 { id: 'gpt-4o-mini', name: 'GPT-4o Mini', inputPrice: 0.15, outputPrice: 0.6, contextWindow: 128000, tags: ['fast', 'cheap'] },
 { id: 'codex-mini-latest', name: 'Codex Mini', inputPrice: 1.5, outputPrice: 6, contextWindow: 200000, tags: ['coding'] },
 ],
 },
 {
 id: 'google',
 name: 'Gemini',
 color: '#3b82f6',
 icon: '🔵',
 authType: 'oauth',
 models: [
 { id: 'gemini-2.5-pro', name: 'Gemini 2.5 Pro', inputPrice: 1.25, outputPrice: 10, contextWindow: 1000000, tags: ['flagship', '1M-context'] },
 { id: 'gemini-2.0-flash', name: 'Gemini 2.0 Flash', inputPrice: 0.1, outputPrice: 0.4, contextWindow: 1048576, tags: ['fast', 'cheap', '1M-context'] },
 { id: 'gemini-2.5-flash-lite', name: '2.5 Flash Lite', inputPrice: 0.075, outputPrice: 0.3, contextWindow: 1000000, tags: ['cheapest'] },
 ],
 },
 {
 id: 'moonshot',
 name: 'Kimi',
 color: '#8b5cf6',
 icon: '🟣',
 authType: 'api_key',
 models: [
 { id: 'kimi-k2', name: 'Kimi K2', inputPrice: 0.4, outputPrice: 1.2, contextWindow: 131072, tags: ['coding', 'balanced'] },
 { id: 'moonshot-v1-128k', name: 'Moonshot 128K', inputPrice: 0.8, outputPrice: 2.4, contextWindow: 131072, tags: ['long-context'] },
 { id: 'moonshot-v1-8k', name: 'Moonshot 8K', inputPrice: 0.2, outputPrice: 0.6, contextWindow: 8192, tags: ['fast', 'cheap'] },
 ],
 },
 {
 id: 'minimax',
 name: 'MiniMax',
 color: '#ec4899',
 icon: '💗',
 authType: 'api_key',
 models: [
 { id: 'MiniMax-M1', name: 'M1', inputPrice: 0.55, outputPrice: 2.2, contextWindow: 1000000, tags: ['1M-context', 'reasoning'] },
 { id: 'abab7-chat', name: 'ABAB7', inputPrice: 0.1, outputPrice: 0.4, contextWindow: 256000, tags: ['fast', 'cheap'] },
 ],
 },
 {
 id: 'zhipu',
 name: 'GLM (Zhipu)',
 color: '#06b6d4',
 icon: '🩵',
 authType: 'api_key',
 models: [
 { id: 'glm-4-plus', name: 'GLM-4 Plus', inputPrice: 0.7, outputPrice: 2.8, contextWindow: 128000, tags: ['flagship'] },
 { id: 'glm-4-flash', name: 'GLM-4 Flash', inputPrice: 0, outputPrice: 0, contextWindow: 128000, tags: ['free', 'fast'] },
 { id: 'codegeex-4', name: 'CodeGeeX 4', inputPrice: 0, outputPrice: 0, contextWindow: 128000, tags: ['coding', 'free'] },
 ],
 },
 {
 id: 'openrouter',
 name: 'OpenRouter',
 color: '#f59e0b',
 icon: '🔶',
 authType: 'api_key',
 models: [
 { id: 'meta-llama/llama-4-maverick', name: 'Llama 4 Maverick', inputPrice: 0.2, outputPrice: 0.6, contextWindow: 1000000, tags: ['open-source', '1M-context'] },
 { id: 'qwen/qwen3-235b-a22b', name: 'Qwen3 235B', inputPrice: 0.14, outputPrice: 0.56, contextWindow: 131072, tags: ['open-source', 'cheap'] },
 { id: 'deepseek/deepseek-r1', name: 'DeepSeek R1', inputPrice: 0.55, outputPrice: 2.19, contextWindow: 64000, tags: ['reasoning'] },
 ],
 },
 {
 id: 'cheaper_inference',
 name: 'Cheaper Inference',
 color: '#84cc16',
 icon: '💚',
 authType: 'api_key',
 models: [
 { id: 'meta-llama/llama-3.3-70b-instruct', name: 'Llama 3.3 70B', inputPrice: 0.04, outputPrice: 0.04, contextWindow: 131072, tags: ['ultra-cheap', 'open-source'] },
 { id: 'qwen/qwen2.5-72b-instruct', name: 'Qwen 2.5 72B', inputPrice: 0.03, outputPrice: 0.03, contextWindow: 32768, tags: ['ultra-cheap'] },
 ],
 },
];

// --- Sub-components ---

function AgentCard({ provider, status }: { provider: ProviderDef; status?: ProviderStatus }) {
 const isConfigured = status?.configured ?? false;
 return (
 <div className="agent-card" style={{ '--agent-color': provider.color } as React.CSSProperties}>
 <div className="agent-card-header">
 <span className="agent-icon">{provider.icon}</span>
 <div className="agent-info">
 <span className="agent-name">{provider.name}</span>
 <span className="agent-auth-type">{provider.authType === 'oauth' ? 'OAuth' : 'API Key'}</span>
 </div>
 <span className={`agent-status-dot ${isConfigured ? 'status-configured' : 'status-unconfigured'}`} />
 </div>
 <div className="agent-models-count">{provider.models.length} modèles</div>
 <div className="agent-price-range">
 {Math.min(...provider.models.map(m => m.inputPrice ?? 0))}–{Math.max(...provider.models.map(m => m.inputPrice ?? 0))} $/M in
 </div>
 </div>
 );
}

function ModelTable({ provider }: { provider: ProviderDef }) {
 return (
 <div className="model-table-container">
 <h4 className="model-table-title" style={{ color: provider.color }}>
 {provider.icon} {provider.name} — Modèles & Tarifs
 </h4>
 <table className="model-table">
 <thead>
 <tr>
 <th>Modèle</th>
 <th>Input $/M</th>
 <th>Output $/M</th>
 <th>Contexte</th>
 <th>Tags</th>
 </tr>
 </thead>
 <tbody>
 {provider.models.map((m) => (
 <tr key={m.id}>
 <td className="model-name">{m.name}</td>
 <td className="model-price">{m.inputPrice !== undefined ? `$${m.inputPrice}` : '—'}</td>
 <td className="model-price">{m.outputPrice !== undefined ? `$${m.outputPrice}` : '—'}</td>
 <td className="model-context">{m.contextWindow ? `${(m.contextWindow / 1000).toFixed(0)}K` : '—'}</td>
 <td className="model-tags">
 {m.tags?.map(t => <span key={t} className="tag">{t}</span>)}
 </td>
 </tr>
 ))}
 </tbody>
 </table>
 </div>
 );
}

function SettingsPanel() {
 const [keys, setKeys] = useState<Record<string, string>>({});
 const [saved, setSaved] = useState<string | null>(null);
 const [showKey, setShowKey] = useState<Record<string, boolean>>({});

 const handleSave = useCallback(() => {
 // In production, this would POST to a secure backend endpoint
 // For now, store in localStorage as encrypted placeholder
 try {
 localStorage.setItem('jarvis_api_keys', JSON.stringify(keys));
 setSaved('Clés sauvegardées localement');
 setTimeout(() => setSaved(null), 3000);
 } catch {
 setSaved('Erreur de sauvegarde');
 }
 }, [keys]);

 useEffect(() => {
 try {
 const stored = localStorage.getItem('jarvis_api_keys');
 if (stored) setKeys(JSON.parse(stored));
 } catch { /* ignore */ }
 }, []);

 return (
 <div className="settings-panel">
 <h3 className="panel-title">CONFIGURATION API KEYS</h3>
 <p className="settings-note">
 Les clés sont stockées localement. En production, utiliser un vault sécurisé.
 </p>
 <div className="key-list">
 {PROVIDERS.map((p) => (
 <div key={p.id} className="key-row">
 <label className="key-label" style={{ color: p.color }}>
 {p.icon} {p.name}
 <span className="key-auth-badge">{p.authType}</span>
 </label>
 <div className="key-input-row">
 <input
 type={showKey[p.id] ? 'text' : 'password'}
 className="key-input"
 placeholder={p.authType === 'oauth' ? 'OAuth flow (bouton ci-dessous)' : `sk-...`}
 value={keys[p.id] || ''}
 onChange={(e) => setKeys(prev => ({ ...prev, [p.id]: e.target.value }))}
 disabled={p.authType === 'oauth'}
 />
 {p.authType === 'api_key' && (
 <button
 className="key-toggle-btn"
 onClick={() => setShowKey(prev => ({ ...prev, [p.id]: !prev[p.id] }))}
 >
 {showKey[p.id] ? '🙈' : '👁️'}
 </button>
 )}
 {p.authType === 'oauth' && (
 <button className="key-oauth-btn" style={{ borderColor: p.color, color: p.color }}>
 🔗 OAuth Connect
 </button>
 )}
 </div>
 </div>
 ))}
 </div>
 <div className="settings-actions">
 <button className="save-btn" onClick={handleSave}>💾 Sauvegarder les clés</button>
 {saved && <span className="save-feedback">{saved}</span>}
 </div>
 </div>
 );
}

function DashboardView({ statuses }: { statuses: ProviderStatus[] }) {
 const configuredCount = statuses.filter(s => s.configured).length;
 const totalModels = PROVIDERS.reduce((sum, p) => sum + p.models.length, 0);
 const cheapestModel = PROVIDERS.flatMap(p => p.models).sort((a, b) => (a.inputPrice ?? 999) - (b.inputPrice ?? 999))[0];

 return (
 <div className="dashboard-view">
 <div className="dash-stats">
 <div className="stat-card">
 <span className="stat-value">{configuredCount}/{PROVIDERS.length}</span>
 <span className="stat-label">Providers configurés</span>
 </div>
 <div className="stat-card">
 <span className="stat-value">{totalModels}</span>
 <span className="stat-label">Modèles disponibles</span>
 </div>
 <div className="stat-card">
 <span className="stat-value">${cheapestModel?.inputPrice ?? '?'}</span>
 <span className="stat-label">Prix min input/M</span>
 </div>
 </div>
 <h3 className="panel-title" style={{ marginTop: 24 }}>HUB AGENTS</h3>
 <div className="agent-grid">
 {PROVIDERS.map(p => (
 <AgentCard
 key={p.id}
 provider={p}
 status={statuses.find(s => s.name === p.id)}
 />
 ))}
 </div>
 </div>
 );
}

function AgentsDetailView() {
 const [selectedProvider, setSelectedProvider] = useState<string>(PROVIDERS[0].id);
 const selected = PROVIDERS.find(p => p.id === selectedProvider) || PROVIDERS[0];

 return (
 <div className="agents-detail">
 <div className="provider-tabs">
 {PROVIDERS.map(p => (
 <button
 key={p.id}
 className={`provider-tab ${selectedProvider === p.id ? 'active' : ''}`}
 style={{ '--tab-color': p.color } as React.CSSProperties}
 onClick={() => setSelectedProvider(p.id)}
 >
 {p.icon} {p.name}
 </button>
 ))}
 </div>
 <ModelTable provider={selected} />
 </div>
 );
}

function MemoryView() {
 const [memories, setMemories] = useState<MemoryItem[]>([]);
 const [loading, setLoading] = useState(false);
 const [query, setQuery] = useState('');

 const loadMemories = useCallback(async (searchQuery: string) => {
 try {
 setLoading(true);
 const resp = await fetch('http://localhost:8004/recall', {
 method: 'POST',
 headers: { 'Content-Type': 'application/json' },
 body: JSON.stringify({ query: searchQuery || '*', limit: 20 }),
 });
 if (resp.ok) {
 const data = await resp.json();
 setMemories(data.results || []);
 }
 } catch { /* service may not be running */ }
 finally { setLoading(false); }
 }, []);

 useEffect(() => { loadMemories(''); }, [loadMemories]);

 return (
 <div className="memory-view">
 <h3 className="panel-title">MÉMOIRE GLOBALE</h3>
 <div className="memory-search">
 <input
 className="memory-search-input"
 placeholder="Recherche sémantique..."
 value={query}
 onChange={(e) => setQuery(e.target.value)}
 onKeyDown={(e) => e.key === 'Enter' && loadMemories(query)}
 />
 <button className="memory-search-btn" onClick={() => loadMemories(query)}>🔍</button>
 </div>
 <div className="memory-list">
 {loading ? (
 <div className="memory-loading">Chargement...</div>
 ) : memories.length === 0 ? (
 <div className="memory-empty">Aucune mémoire trouvée</div>
 ) : (
 memories.map((m) => (
 <div key={m.id} className="memory-item-full">
 <div className="memory-meta">
 <span className="memory-agent-tag">{(m.metadata?.agent_id as string) || 'unknown'}</span>
 {m.score !== undefined && <span className="memory-score">score: {m.score.toFixed(3)}</span>}
 </div>
 <div className="memory-text">{m.content}</div>
 </div>
 ))
 )}
 </div>
 </div>
 );
}

// --- Chat Panel ---

interface ChatMessage {
 role: 'user' | 'assistant';
 content: string;
 provider?: string;
 model?: string;
 costEstimate?: number; // $ estimated
 timestamp: number;
}

const CHAT_STORAGE_KEY = 'jarvis_chat_history';

function loadChatHistory(): ChatMessage[] {
 try {
 const stored = localStorage.getItem(CHAT_STORAGE_KEY);
 return stored ? JSON.parse(stored) : [];
 } catch {
 return [];
 }
}

function saveChatHistory(msgs: ChatMessage[]) {
 try {
 // Keep last 200 messages to avoid localStorage overflow
 const trimmed = msgs.slice(-200);
 localStorage.setItem(CHAT_STORAGE_KEY, JSON.stringify(trimmed));
 } catch { /* ignore quota errors */ }
}

function ChatPanel() {
 const [messages, setMessages] = useState<ChatMessage[]>(loadChatHistory);
 const [input, setInput] = useState('');
 const [selectedProvider, setSelectedProvider] = useState(PROVIDERS[0].id);
 const [selectedModel, setSelectedModel] = useState(PROVIDERS[0].models[0].id);
 const [loading, setLoading] = useState(false);
 const [error, setError] = useState<string | null>(null);
 const [streamingContent, setStreamingContent] = useState('');

 const currentProvider = PROVIDERS.find(p => p.id === selectedProvider) || PROVIDERS[0];
 const currentModel = currentProvider.models.find(m => m.id === selectedModel) || currentProvider.models[0];

 // Persist messages to localStorage on every change
 useEffect(() => {
 saveChatHistory(messages);
 }, [messages]);

 // Sync model when provider changes
 useEffect(() => {
 setSelectedModel(currentProvider.models[0]?.id || '');
 }, [selectedProvider, currentProvider]);

 const estimateCost = (inputChars: number, outputChars: number): number => {
 const inputTokens = Math.ceil(inputChars / 4);
 const outputTokens = Math.ceil(outputChars / 4);
 const inputCost = (inputTokens / 1_000_000) * (currentModel.inputPrice ?? 0);
 const outputCost = (outputTokens / 1_000_000) * (currentModel.outputPrice ?? 0);
 return inputCost + outputCost;
 };

 const handleSend = useCallback(async () => {
 if (!input.trim() || loading) return;

 const userMsg: ChatMessage = {
 role: 'user',
 content: input.trim(),
 timestamp: Date.now(),
 };

 setMessages(prev => [...prev, userMsg]);
 setInput('');
 setLoading(true);
 setError(null);
 setStreamingContent('');

 const allMessages = [...messages, userMsg].map(m => ({
 role: m.role,
 content: m.content,
 }));

 try {
 const resp = await fetch('http://localhost:8003/chat/stream', {
 method: 'POST',
 headers: { 'Content-Type': 'application/json' },
 body: JSON.stringify({
 messages: allMessages,
 provider: selectedProvider,
 model: selectedModel,
 }),
 });

 if (!resp.ok) {
 const errData = await resp.json().catch(() => ({}));
 throw new Error(errData.detail || `HTTP ${resp.status}`);
 }

 if (!resp.body) {
 throw new Error('Streaming not supported');
 }

 const reader = resp.body.getReader();
 const decoder = new TextDecoder();
 let finalContent = '';
 let finalProvider = selectedProvider;
 let finalModel = selectedModel;

 // Read SSE events — server now emits single complete event (no fake chunking)
 while (true) {
 const { done, value } = await reader.read();
 if (done) break;

 const chunk = decoder.decode(value, { stream: true });
 const lines = chunk.split('\n');

 for (const line of lines) {
 if (!line.startsWith('data: ')) continue;
 const jsonStr = line.slice(6).trim();
 if (!jsonStr) continue;

 try {
 const event = JSON.parse(jsonStr);

 if (event.error) {
 throw new Error(event.error);
 }

 if (event.done && event.content !== undefined) {
 finalContent = event.content;
 finalProvider = event.provider || finalProvider;
 finalModel = event.model || finalModel;
 }
 } catch (parseErr) {
 if (parseErr instanceof Error && !parseErr.message.includes('LLM request failed')) {
 // Skip malformed SSE lines silently
 } else if (parseErr instanceof Error) {
 throw parseErr; // Re-throw actual API errors
 }
 }
 }
 }

 const totalInputChars = allMessages.reduce((sum, m) => sum + m.content.length, 0);
 const assistantMsg: ChatMessage = {
 role: 'assistant',
 content: finalContent,
 provider: finalProvider,
 model: finalModel,
 costEstimate: estimateCost(totalInputChars, finalContent.length),
 timestamp: Date.now(),
 };

 setMessages(prev => [...prev, assistantMsg]);
 setStreamingContent('');
 } catch (exc) {
 setError(exc instanceof Error ? exc.message : 'Erreur inconnue');
 setStreamingContent('');
 } finally {
 setLoading(false);
 }
 }, [input, loading, messages, selectedProvider, selectedModel, currentModel]);

 return (
 <div className="chat-panel">
 <h3 className="panel-title">CHAT INTERACTIF</h3>

 {/* Provider + Model selector */}
 <div className="chat-controls">
 <select
 className="chat-select"
 value={selectedProvider}
 onChange={(e) => setSelectedProvider(e.target.value)}
 >
 {PROVIDERS.map(p => (
 <option key={p.id} value={p.id}>{p.icon} {p.name}</option>
 ))}
 </select>
 <select
 className="chat-select"
 value={selectedModel}
 onChange={(e) => setSelectedModel(e.target.value)}
 >
 {currentProvider.models.map(m => (
 <option key={m.id} value={m.id}>
 {m.name} — {m.inputPrice !== undefined ? `$${m.inputPrice}/M` : 'free'}
 </option>
 ))}
 </select>
 </div>

 {/* Messages */}
 <div className="chat-messages">
 {messages.length === 0 && (
 <div className="chat-empty">Envoyez un message pour commencer une conversation</div>
 )}
 {messages.map((msg, i) => (
 <div key={i} className={`chat-msg chat-msg-${msg.role}`}>
 <div className="chat-msg-header">
 <span className="chat-msg-role">{msg.role === 'user' ? '👤 Vous' : `🤖 ${msg.provider || 'Assistant'}`}</span>
 {msg.model && <span className="chat-msg-model">{msg.model}</span>}
 {msg.costEstimate !== undefined && msg.costEstimate > 0 && (
 <span className="chat-msg-cost">~${msg.costEstimate.toFixed(6)}</span>
 )}
 </div>
 <div className="chat-msg-content">{msg.content}</div>
 </div>
 ))}
 {loading && streamingContent && (
 <div className="chat-msg chat-msg-assistant chat-msg-streaming">
 <div className="chat-msg-header">
 <span className="chat-msg-role">🤖 {selectedProvider}</span>
 <span className="chat-msg-model">{selectedModel}</span>
 <span className="chat-streaming-indicator">● streaming</span>
 </div>
 <div className="chat-msg-content">{streamingContent}</div>
 </div>
 )}
 {loading && !streamingContent && <div className="chat-loading">⏳ Connexion au provider...</div>}
 {error && <div className="chat-error">❌ {error}</div>}
 </div>

 {/* Input */}
 <div className="chat-input-row">
 <input
 className="chat-input"
 placeholder="Écrivez votre message..."
 value={input}
 onChange={(e) => setInput(e.target.value)}
 onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && handleSend()}
 disabled={loading}
 />
 <button
 className="chat-send-btn"
 onClick={handleSend}
 disabled={!input.trim() || loading}
 >
 {loading ? '...' : '➤'}
 </button>
 </div>
 </div>
 );
}

// --- Main App ---

export default function App() {
 const [activeTab, setActiveTab] = useState<Tab>('dashboard');
 const [currentTime, setCurrentTime] = useState(new Date());
 const [providerStatuses, setProviderStatuses] = useState<ProviderStatus[]>([]);

 useEffect(() => {
 const interval = setInterval(() => setCurrentTime(new Date()), 1000);
 return () => clearInterval(interval);
 }, []);

 // Fetch provider statuses from core service
 useEffect(() => {
 async function fetchStatuses() {
 try {
 const resp = await fetch('http://localhost:8003/providers');
 if (resp.ok) {
 const data = await resp.json();
 setProviderStatuses(data.providers || []);
 }
 } catch { /* core not running */ }
 }
 fetchStatuses();
 const interval = setInterval(fetchStatuses, 30000);
 return () => clearInterval(interval);
 }, []);

 const tabs: { id: Tab; label: string; icon: string }[] = [
 { id: 'dashboard', label: 'DASHBOARD', icon: '◈' },
 { id: 'chat', label: 'CHAT', icon: '💬' },
 { id: 'agents', label: 'AGENTS & MODÈLES', icon: '🤖' },
 { id: 'settings', label: 'API KEYS', icon: '🔑' },
 { id: 'memory', label: 'MÉMOIRE', icon: '🧠' },
 ];

 return (
 <div className="jarvis-hud">
 {/* Header */}
 <header className="hud-header">
 <div className="hud-logo">◈ JARVIS</div>
 <nav className="hud-nav">
 {tabs.map(t => (
 <button
 key={t.id}
 className={`nav-tab ${activeTab === t.id ? 'active' : ''}`}
 onClick={() => setActiveTab(t.id)}
 >
 <span className="nav-icon">{t.icon}</span>
 <span className="nav-label">{t.label}</span>
 </button>
 ))}
 </nav>
 <div className="hud-clock-group">
 <div className="hud-clock">
 {currentTime.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
 </div>
 <div className="hud-date">
 {currentTime.toLocaleDateString('fr-FR', { weekday: 'short', day: 'numeric', month: 'short' })}
 </div>
 </div>
 </header>

 {/* Main content area */}
 <main className="hud-main">
 {activeTab === 'dashboard' && <DashboardView statuses={providerStatuses} />}
 {activeTab === 'chat' && <ChatPanel />}
 {activeTab === 'agents' && <AgentsDetailView />}
 {activeTab === 'settings' && <SettingsPanel />}
 {activeTab === 'memory' && <MemoryView />}
 </main>

 {/* Footer status bar */}
 <footer className="hud-footer">
 <span>SYS: ONLINE</span>
 <span>STT: :8001</span>
 <span>TTS: :8002</span>
 <span>CORE: :8003</span>
 <span>MEM: :8004</span>
 <span>CONN: :8005</span>
 </footer>
 </div>
 );
}