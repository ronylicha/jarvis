import { useCallback, useEffect, useState } from 'react';
import './App.css';
import { t, setLocale, getLocale, initLocale, type Locale } from './i18n';

// --- Types ---

type Tab = 'dashboard' | 'chat' | 'agents' | 'sessions' | 'settings' | 'memory' | 'messaging';

interface AgentSessionInfo {
 agent_type: string;
 session_id: string;
 status: string;
 pid?: number;
 model?: string;
 proxy_url?: string;
 started_at?: string;
}

interface SessionsData {
 sessions: AgentSessionInfo[];
 total_active: number;
 by_agent: Record<string, number>;
 proxy_relay: { pid: number; url: string; upstream: string; status: string } | null;
 scanned_at: string;
}

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
 inputPrice?: number;
 outputPrice?: number;
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

interface ChatMessage {
 role: 'user' | 'assistant';
 content: string;
 provider?: string;
 model?: string;
 costEstimate?: number;
 timestamp: number;
}

interface InboxMessage {
 channel: string;
 sender: string;
 content: string;
 timestamp: string;
 message_id?: string;
 subject?: string;
}

// --- Provider Catalog ---

const PROVIDERS: ProviderDef[] = [
 { id: 'anthropic', name: 'Claude', color: '#d97706', icon: '🟠', authType: 'api_key', models: [
 { id: 'claude-opus-4-20250514', name: 'Opus 4', inputPrice: 15, outputPrice: 75, contextWindow: 200000, tags: ['flagship', 'reasoning'] },
 { id: 'claude-sonnet-4-20250514', name: 'Sonnet 4', inputPrice: 3, outputPrice: 15, contextWindow: 200000, tags: ['balanced'] },
 { id: 'claude-haiku-3-5-20241022', name: 'Haiku 3.5', inputPrice: 0.8, outputPrice: 4, contextWindow: 200000, tags: ['fast', 'cheap'] },
 ]},
 { id: 'openai', name: 'Codex / GPT', color: '#10b981', icon: '🟢', authType: 'oauth', models: [
 { id: 'o3', name: 'o3', inputPrice: 2, outputPrice: 8, contextWindow: 200000, tags: ['reasoning'] },
 { id: 'gpt-4o', name: 'GPT-4o', inputPrice: 2.5, outputPrice: 10, contextWindow: 128000, tags: ['balanced'] },
 { id: 'gpt-4o-mini', name: 'GPT-4o Mini', inputPrice: 0.15, outputPrice: 0.6, contextWindow: 128000, tags: ['fast', 'cheap'] },
 { id: 'codex-mini-latest', name: 'Codex Mini', inputPrice: 1.5, outputPrice: 6, contextWindow: 200000, tags: ['coding'] },
 ]},
 { id: 'google', name: 'Gemini', color: '#3b82f6', icon: '🔵', authType: 'oauth', models: [
 { id: 'gemini-2.5-pro', name: 'Gemini 2.5 Pro', inputPrice: 1.25, outputPrice: 10, contextWindow: 1000000, tags: ['flagship', '1M-context'] },
 { id: 'gemini-2.0-flash', name: 'Gemini 2.0 Flash', inputPrice: 0.1, outputPrice: 0.4, contextWindow: 1048576, tags: ['fast', 'cheap', '1M-context'] },
 { id: 'gemini-2.5-flash-lite', name: '2.5 Flash Lite', inputPrice: 0.075, outputPrice: 0.3, contextWindow: 1000000, tags: ['cheapest'] },
 ]},
 { id: 'moonshot', name: 'Kimi', color: '#8b5cf6', icon: '🟣', authType: 'api_key', models: [
 { id: 'kimi-k2', name: 'Kimi K2', inputPrice: 0.4, outputPrice: 1.2, contextWindow: 131072, tags: ['coding', 'balanced'] },
 { id: 'moonshot-v1-128k', name: 'Moonshot 128K', inputPrice: 0.8, outputPrice: 2.4, contextWindow: 131072, tags: ['long-context'] },
 { id: 'moonshot-v1-8k', name: 'Moonshot 8K', inputPrice: 0.2, outputPrice: 0.6, contextWindow: 8192, tags: ['fast', 'cheap'] },
 ]},
 { id: 'minimax', name: 'MiniMax', color: '#ec4899', icon: '💗', authType: 'api_key', models: [
 { id: 'MiniMax-M1', name: 'M1', inputPrice: 0.55, outputPrice: 2.2, contextWindow: 1000000, tags: ['1M-context', 'reasoning'] },
 { id: 'abab7-chat', name: 'ABAB7', inputPrice: 0.1, outputPrice: 0.4, contextWindow: 256000, tags: ['fast', 'cheap'] },
 ]},
 { id: 'zhipu', name: 'GLM (Zhipu)', color: '#06b6d4', icon: '🩵', authType: 'api_key', models: [
 { id: 'glm-4-plus', name: 'GLM-4 Plus', inputPrice: 0.7, outputPrice: 2.8, contextWindow: 128000, tags: ['flagship'] },
 { id: 'glm-4-flash', name: 'GLM-4 Flash', inputPrice: 0, outputPrice: 0, contextWindow: 128000, tags: ['free', 'fast'] },
 { id: 'codegeex-4', name: 'CodeGeeX 4', inputPrice: 0, outputPrice: 0, contextWindow: 128000, tags: ['coding', 'free'] },
 ]},
 { id: 'openrouter', name: 'OpenRouter', color: '#f59e0b', icon: '🔶', authType: 'api_key', models: [
 { id: 'meta-llama/llama-4-maverick', name: 'Llama 4 Maverick', inputPrice: 0.2, outputPrice: 0.6, contextWindow: 1000000, tags: ['open-source', '1M-context'] },
 { id: 'qwen/qwen3-235b-a22b', name: 'Qwen3 235B', inputPrice: 0.14, outputPrice: 0.56, contextWindow: 131072, tags: ['open-source', 'cheap'] },
 { id: 'deepseek/deepseek-r1', name: 'DeepSeek R1', inputPrice: 0.55, outputPrice: 2.19, contextWindow: 64000, tags: ['reasoning'] },
 ]},
 { id: 'cheaper_inference', name: 'Cheaper Inference', color: '#84cc16', icon: '💚', authType: 'api_key', models: [
 { id: 'meta-llama/llama-3.3-70b-instruct', name: 'Llama 3.3 70B', inputPrice: 0.04, outputPrice: 0.04, contextWindow: 131072, tags: ['ultra-cheap', 'open-source'] },
 { id: 'qwen/qwen2.5-72b-instruct', name: 'Qwen 2.5 72B', inputPrice: 0.03, outputPrice: 0.03, contextWindow: 32768, tags: ['ultra-cheap'] },
 ]},
];

const STT_LANGUAGES = [
 { code: 'fr', label: 'Français' },
 { code: 'en', label: 'English' },
 { code: 'es', label: 'Español' },
 { code: 'de', label: 'Deutsch' },
 { code: 'auto', label: 'Auto-detect' },
];

const TTS_VOICES = [
 { id: 'fr_FR-siwis-medium', label: 'FR — Siwis (Femme)', lang: 'fr' },
 { id: 'fr_FR-upmc-medium', label: 'FR — UPMC (Homme)', lang: 'fr' },
 { id: 'en_US-lessac-medium', label: 'EN — Lessac (Homme)', lang: 'en' },
 { id: 'en_US-amy-medium', label: 'EN — Amy (Femme)', lang: 'en' },
 { id: 'es_ES-carlfm-medium', label: 'ES — CarlFM (Homme)', lang: 'es' },
 { id: 'de_DE-thorsten-medium', label: 'DE — Thorsten (Homme)', lang: 'de' },
];

// --- Sub-components ---

function AgentCard({ provider, status }: { provider: ProviderDef; status?: ProviderStatus }) {
 const isConfigured = status?.configured ?? false;
 if (!isConfigured) return null; // Only show configured providers
 return (
 <div className="agent-card" style={{ '--agent-color': provider.color } as React.CSSProperties}>
 <div className="agent-card-header">
 <span className="agent-icon">{provider.icon}</span>
 <div className="agent-info">
 <span className="agent-name">{provider.name}</span>
 <span className="agent-auth-type">{provider.authType === 'oauth' ? 'OAuth' : 'API Key'}</span>
 </div>
 <span className="agent-status-dot status-configured" />
 </div>
 <div className="agent-models-count">{provider.models.length} {t('common.models')}</div>
 <div className="agent-price-range">
 {Math.min(...provider.models.map(m => m.inputPrice ?? 0))}–{Math.max(...provider.models.map(m => m.inputPrice ?? 0))} $/M in
 </div>
 </div>
 );
}

function ModelTable({ provider, onRefresh, refreshing }: { provider: ProviderDef; onRefresh: () => void; refreshing: boolean }) {
 return (
 <div className="model-table-container">
 <div className="model-table-header">
 <h4 className="model-table-title" style={{ color: provider.color }}>
 {provider.icon} {provider.name} — {t('agents.models_title')}
 </h4>
 <button className="refresh-btn" onClick={onRefresh} disabled={refreshing}>
 {refreshing ? t('agents.refreshing') : t('agents.refresh_models')}
 </button>
 </div>
 <table className="model-table">
 <thead>
 <tr>
 <th>{t('agents.th_model')}</th>
 <th>{t('agents.th_input')}</th>
 <th>{t('agents.th_output')}</th>
 <th>{t('agents.th_context')}</th>
 <th>{t('agents.th_tags')}</th>
 </tr>
 </thead>
 <tbody>
 {provider.models.map((m) => (
 <tr key={m.id}>
 <td className="model-name">{m.name}</td>
 <td className="model-price">{m.inputPrice !== undefined ? `$${m.inputPrice}` : '—'}</td>
 <td className="model-price">{m.outputPrice !== undefined ? `$${m.outputPrice}` : '—'}</td>
 <td className="model-context">{m.contextWindow ? `${(m.contextWindow / 1000).toFixed(0)}K` : '—'}</td>
 <td className="model-tags">{m.tags?.map(tag => <span key={tag} className="tag">{tag}</span>)}</td>
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
 const [locale, setLocaleState] = useState<Locale>(getLocale());
 const [sttLang, setSttLang] = useState('fr');
 const [ttsVoice, setTtsVoice] = useState('fr_FR-siwis-medium');
 const [voiceSpeed, setVoiceSpeed] = useState(1.0);

 useEffect(() => {
 try {
 const stored = localStorage.getItem('jarvis_api_keys');
 if (stored) setKeys(JSON.parse(stored));
 const voiceSettings = localStorage.getItem('jarvis_voice_settings');
 if (voiceSettings) {
 const vs = JSON.parse(voiceSettings);
 if (vs.sttLang) setSttLang(vs.sttLang);
 if (vs.ttsVoice) setTtsVoice(vs.ttsVoice);
 if (vs.voiceSpeed) setVoiceSpeed(vs.voiceSpeed);
 }
 } catch { /* ignore */ }
 }, []);

 const handleSave = useCallback(() => {
 try {
 localStorage.setItem('jarvis_api_keys', JSON.stringify(keys));
 localStorage.setItem('jarvis_voice_settings', JSON.stringify({ sttLang, ttsVoice, voiceSpeed }));
 setSaved(t('settings.saved'));
 setTimeout(() => setSaved(null), 3000);
 } catch {
 setSaved(t('settings.error'));
 }
 }, [keys, sttLang, ttsVoice, voiceSpeed]);

 const handleLocaleChange = (newLocale: Locale) => {
 setLocale(newLocale);
 setLocaleState(newLocale);
 };

 return (
 <div className="settings-panel">
 {/* Language selector */}
 <h3 className="panel-title">{t('settings.language')}</h3>
 <div className="locale-selector">
 <button className={`locale-btn ${locale === 'fr' ? 'active' : ''}`} onClick={() => handleLocaleChange('fr')}>🇫🇷 Français</button>
 <button className={`locale-btn ${locale === 'en' ? 'active' : ''}`} onClick={() => handleLocaleChange('en')}>🇬🇧 English</button>
 </div>

 {/* Voice settings */}
 <h3 className="panel-title" style={{ marginTop: 20 }}>{t('settings.section_voice')}</h3>
 <div className="voice-settings">
 <div className="voice-row">
 <label>{t('settings.stt_language')}</label>
 <select value={sttLang} onChange={(e) => setSttLang(e.target.value)} className="voice-select">
 {STT_LANGUAGES.map(l => <option key={l.code} value={l.code}>{l.label}</option>)}
 </select>
 </div>
 <div className="voice-row">
 <label>{t('settings.tts_voice')}</label>
 <select value={ttsVoice} onChange={(e) => setTtsVoice(e.target.value)} className="voice-select">
 {TTS_VOICES.map(v => <option key={v.id} value={v.id}>{v.label}</option>)}
 </select>
 </div>
 <div className="voice-row">
 <label>{t('settings.voice_speed')}: {voiceSpeed.toFixed(1)}x</label>
 <input type="range" min="0.5" max="2.0" step="0.1" value={voiceSpeed} onChange={(e) => setVoiceSpeed(parseFloat(e.target.value))} className="voice-slider" />
 </div>
 </div>

 {/* API Keys */}
 <h3 className="panel-title" style={{ marginTop: 20 }}>{t('settings.section_keys')}</h3>
 <p className="settings-note">{t('settings.note')}</p>
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
 placeholder={p.authType === 'oauth' ? 'OAuth flow' : `sk-...`}
 value={keys[p.id] || ''}
 onChange={(e) => setKeys(prev => ({ ...prev, [p.id]: e.target.value }))}
 disabled={p.authType === 'oauth'}
 />
 {p.authType === 'api_key' && (
 <button className="key-toggle-btn" onClick={() => setShowKey(prev => ({ ...prev, [p.id]: !prev[p.id] }))}>
 {showKey[p.id] ? '🙈' : '👁️'}
 </button>
 )}
 {p.authType === 'oauth' && (
 <button className="key-oauth-btn" style={{ borderColor: p.color, color: p.color }}>
 🔗 {t('settings.oauth_connect')}
 </button>
 )}
 </div>
 </div>
 ))}
 </div>

 {/* Messaging connectors */}
 <h3 className="panel-title" style={{ marginTop: 20 }}>{t('settings.section_messaging')}</h3>
 <p className="settings-note">{t('settings.messaging_note')}</p>
 <div className="key-list">
 <div className="key-row">
 <label className="key-label" style={{ color: '#229ED9' }}>✈️ Telegram</label>
 <div className="key-input-row">
 <input className="key-input" placeholder={t('settings.telegram_token')} value={keys['telegram_token'] || ''} onChange={(e) => setKeys(prev => ({ ...prev, telegram_token: e.target.value }))} />
 </div>
 <div className="key-input-row" style={{ marginTop: 4 }}>
 <input className="key-input" placeholder={t('settings.telegram_chat_id')} value={keys['telegram_chat_id'] || ''} onChange={(e) => setKeys(prev => ({ ...prev, telegram_chat_id: e.target.value }))} />
 </div>
 </div>
 <div className="key-row">
 <label className="key-label" style={{ color: '#25D366' }}>📱 WhatsApp</label>
 <div className="key-input-row">
 <input className="key-input" placeholder={t('settings.whatsapp_token')} value={keys['whatsapp_token'] || ''} onChange={(e) => setKeys(prev => ({ ...prev, whatsapp_token: e.target.value }))} />
 </div>
 <div className="key-input-row" style={{ marginTop: 4 }}>
 <input className="key-input" placeholder={t('settings.whatsapp_phone_id')} value={keys['whatsapp_phone_id'] || ''} onChange={(e) => setKeys(prev => ({ ...prev, whatsapp_phone_id: e.target.value }))} />
 </div>
 </div>
 <div className="key-row">
 <label className="key-label" style={{ color: '#EA4335' }}>📧 Email</label>
 <div className="key-input-row">
 <input className="key-input" placeholder={t('settings.email_imap_host')} value={keys['email_imap_host'] || ''} onChange={(e) => setKeys(prev => ({ ...prev, email_imap_host: e.target.value }))} />
 </div>
 <div className="key-input-row" style={{ marginTop: 4 }}>
 <input className="key-input" placeholder={t('settings.email_imap_user')} value={keys['email_imap_user'] || ''} onChange={(e) => setKeys(prev => ({ ...prev, email_imap_user: e.target.value }))} />
 </div>
 <div className="key-input-row" style={{ marginTop: 4 }}>
 <input className="key-input" type="password" placeholder={t('settings.email_imap_pass')} value={keys['email_imap_pass'] || ''} onChange={(e) => setKeys(prev => ({ ...prev, email_imap_pass: e.target.value }))} />
 </div>
 </div>
 </div>

 <div className="settings-actions">
 <button className="save-btn" onClick={handleSave}>💾 {t('settings.save')}</button>
 {saved && <span className="save-feedback">{saved}</span>}
 </div>
 </div>
 );
}

function DashboardView({ statuses }: { statuses: ProviderStatus[] }) {
 const configuredProviders = PROVIDERS.filter(p => statuses.find(s => s.name === p.id)?.configured);
 const configuredCount = configuredProviders.length;
 const totalModels = configuredProviders.reduce((sum, p) => sum + p.models.length, 0);
 const cheapestModel = configuredProviders.flatMap(p => p.models).sort((a, b) => (a.inputPrice ?? 999) - (b.inputPrice ?? 999))[0];

 return (
 <div className="dashboard-view">
 <div className="dash-stats">
 <div className="stat-card">
 <span className="stat-value">{configuredCount}/{PROVIDERS.length}</span>
 <span className="stat-label">{t('dash.providers_configured')}</span>
 </div>
 <div className="stat-card">
 <span className="stat-value">{totalModels}</span>
 <span className="stat-label">{t('dash.models_available')}</span>
 </div>
 <div className="stat-card">
 <span className="stat-value">${cheapestModel?.inputPrice ?? '?'}</span>
 <span className="stat-label">{t('dash.min_price')}</span>
 </div>
 </div>
 <h3 className="panel-title" style={{ marginTop: 24 }}>{t('dash.hub_agents')}</h3>
 {configuredCount === 0 && <p className="settings-note">{t('dash.no_providers')}</p>}
 <div className="agent-grid">
 {PROVIDERS.map(p => (
 <AgentCard key={p.id} provider={p} status={statuses.find(s => s.name === p.id)} />
 ))}
 </div>
 </div>
 );
}

function AgentsDetailView({ statuses }: { statuses: ProviderStatus[] }) {
 const configuredProviders = PROVIDERS.filter(p => statuses.find(s => s.name === p.id)?.configured);
 const [selectedProvider, setSelectedProvider] = useState<string>(configuredProviders[0]?.id || PROVIDERS[0].id);
 const [refreshing, setRefreshing] = useState(false);
 const selected = PROVIDERS.find(p => p.id === selectedProvider) || PROVIDERS[0];

 const handleRefresh = useCallback(async () => {
 setRefreshing(true);
 try {
 await fetch(`http://localhost:8003/models/refresh?provider=${selectedProvider}`, { method: 'GET' });
 } catch { /* ignore */ }
 setTimeout(() => setRefreshing(false), 1500);
 }, [selectedProvider]);

 if (configuredProviders.length === 0) {
 return <div className="settings-note" style={{ padding: 40, textAlign: 'center' }}>{t('agents.only_configured')}</div>;
 }

 return (
 <div className="agents-detail">
 <p className="settings-note">{t('agents.only_configured')}</p>
 <div className="provider-tabs">
 {configuredProviders.map(p => (
 <button key={p.id} className={`provider-tab ${selectedProvider === p.id ? 'active' : ''}`} style={{ '--tab-color': p.color } as React.CSSProperties} onClick={() => setSelectedProvider(p.id)}>
 {p.icon} {p.name}
 </button>
 ))}
 </div>
 <ModelTable provider={selected} onRefresh={handleRefresh} refreshing={refreshing} />
 </div>
 );
}

// --- Chat Panel ---

const CHAT_STORAGE_KEY = 'jarvis_chat_history';

function loadChatHistory(): ChatMessage[] {
 try { const stored = localStorage.getItem(CHAT_STORAGE_KEY); return stored ? JSON.parse(stored) : []; } catch { return []; }
}
function saveChatHistory(msgs: ChatMessage[]) {
 try { localStorage.setItem(CHAT_STORAGE_KEY, JSON.stringify(msgs.slice(-200))); } catch { /* ignore */ }
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

 useEffect(() => { saveChatHistory(messages); }, [messages]);
 useEffect(() => { setSelectedModel(currentProvider.models[0]?.id || ''); }, [selectedProvider, currentProvider]);

 const estimateCost = (inputChars: number, outputChars: number): number => {
 return (Math.ceil(inputChars / 4) / 1_000_000) * (currentModel.inputPrice ?? 0) + (Math.ceil(outputChars / 4) / 1_000_000) * (currentModel.outputPrice ?? 0);
 };

 const handleSend = useCallback(async () => {
 if (!input.trim() || loading) return;
 const userMsg: ChatMessage = { role: 'user', content: input.trim(), timestamp: Date.now() };
 setMessages(prev => [...prev, userMsg]);
 setInput(''); setLoading(true); setError(null); setStreamingContent('');

 const allMessages = [...messages, userMsg].map(m => ({ role: m.role, content: m.content }));
 try {
 const resp = await fetch('http://localhost:8003/chat/stream', {
 method: 'POST', headers: { 'Content-Type': 'application/json' },
 body: JSON.stringify({ messages: allMessages, provider: selectedProvider, model: selectedModel }),
 });
 if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
 if (!resp.body) throw new Error('No stream');

 const reader = resp.body.getReader();
 const decoder = new TextDecoder();
 let finalContent = '', finalProvider = selectedProvider, finalModel = selectedModel;

 while (true) {
 const { done, value } = await reader.read();
 if (done) break;
 const chunk = decoder.decode(value, { stream: true });
 for (const line of chunk.split('\n')) {
 if (!line.startsWith('data: ')) continue;
 try {
 const event = JSON.parse(line.slice(6).trim());
 if (event.error) throw new Error(event.error);
 if (event.done && event.content !== undefined) {
 finalContent = event.content;
 finalProvider = event.provider || finalProvider;
 finalModel = event.model || finalModel;
 }
 } catch (e) { if (e instanceof Error && e.message.includes('LLM')) throw e; }
 }
 }

 const totalInputChars = allMessages.reduce((sum, m) => sum + m.content.length, 0);
 setMessages(prev => [...prev, { role: 'assistant', content: finalContent, provider: finalProvider, model: finalModel, costEstimate: estimateCost(totalInputChars, finalContent.length), timestamp: Date.now() }]);
 setStreamingContent('');
 } catch (exc) { setError(exc instanceof Error ? exc.message : 'Error'); setStreamingContent(''); }
 finally { setLoading(false); }
 }, [input, loading, messages, selectedProvider, selectedModel, currentModel]);

 return (
 <div className="chat-panel">
 <h3 className="panel-title">{t('chat.title')}</h3>
 <div className="chat-controls">
 <select className="chat-select" value={selectedProvider} onChange={(e) => setSelectedProvider(e.target.value)}>
 {PROVIDERS.map(p => <option key={p.id} value={p.id}>{p.icon} {p.name}</option>)}
 </select>
 <select className="chat-select" value={selectedModel} onChange={(e) => setSelectedModel(e.target.value)}>
 {currentProvider.models.map(m => <option key={m.id} value={m.id}>{m.name} — {m.inputPrice !== undefined ? `$${m.inputPrice}/M` : t('common.free')}</option>)}
 </select>
 </div>
 <div className="chat-messages">
 {messages.length === 0 && <div className="chat-empty">{t('chat.empty')}</div>}
 {messages.map((msg, i) => (
 <div key={i} className={`chat-msg chat-msg-${msg.role}`}>
 <div className="chat-msg-header">
 <span className="chat-msg-role">{msg.role === 'user' ? `👤 ${t('chat.you')}` : `🤖 ${msg.provider || t('chat.assistant')}`}</span>
 {msg.model && <span className="chat-msg-model">{msg.model}</span>}
 {msg.costEstimate !== undefined && msg.costEstimate > 0 && <span className="chat-msg-cost">~${msg.costEstimate.toFixed(6)}</span>}
 </div>
 <div className="chat-msg-content">{msg.content}</div>
 </div>
 ))}
 {loading && streamingContent && (
 <div className="chat-msg chat-msg-assistant chat-msg-streaming">
 <div className="chat-msg-header"><span className="chat-msg-role">🤖 {selectedProvider}</span><span className="chat-streaming-indicator">● streaming</span></div>
 <div className="chat-msg-content">{streamingContent}</div>
 </div>
 )}
 {loading && !streamingContent && <div className="chat-loading">⏳ {t('chat.connecting')}</div>}
 {error && <div className="chat-error">❌ {error}</div>}
 </div>
 <div className="chat-input-row">
 <input className="chat-input" placeholder={t('chat.placeholder')} value={input} onChange={(e) => setInput(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && handleSend()} disabled={loading} />
 <button className="chat-send-btn" onClick={handleSend} disabled={!input.trim() || loading}>{loading ? '...' : '➤'}</button>
 </div>
 </div>
 );
}

// --- Sessions Panel ---

const AGENT_COLORS: Record<string, string> = { claude: '#d97706', codex: '#10b981', kimi: '#8b5cf6', zai: '#06b6d4' };
const AGENT_ICONS: Record<string, string> = { claude: '🟠', codex: '🟢', kimi: '🟣', zai: '🩵' };

function SessionsPanel() {
 const [data, setData] = useState<SessionsData | null>(null);
 const [connected, setConnected] = useState(false);
 const [error, setError] = useState<string | null>(null);

 useEffect(() => {
 let abortController: AbortController | null = null;
 async function connectSSE() {
 try {
 abortController = new AbortController();
 let headers: Record<string, string> = {};
 try { const k = JSON.parse(localStorage.getItem('jarvis_api_keys') || '{}'); if (k.agent_sessions_token) headers['X-Jarvis-Token'] = k.agent_sessions_token; } catch {}
 const resp = await fetch('http://localhost:8007/sessions/stream', { signal: abortController.signal, headers });
 if (!resp.ok || !resp.body) throw new Error(`SSE failed: HTTP ${resp.status}`);
 setConnected(true); setError(null);
 const reader = resp.body.getReader(); const decoder = new TextDecoder(); let buffer = '';
 while (true) {
 const { done, value } = await reader.read(); if (done) break;
 buffer += decoder.decode(value, { stream: true });
 const lines = buffer.split('\n'); buffer = lines.pop() || '';
 for (const line of lines) {
 if (!line.startsWith('data: ')) continue;
 try { const parsed = JSON.parse(line.slice(6).trim()); if (parsed.error) setError(parsed.error); else { setData(parsed); setError(null); } } catch {}
 }
 }
 } catch (exc) { if (exc instanceof Error && exc.name !== 'AbortError') { setError(exc.message); setConnected(false); setTimeout(connectSSE, 5000); } }
 }
 connectSSE();
 return () => { abortController?.abort(); };
 }, []);

 return (
 <div className="sessions-panel">
 <h3 className="panel-title">{t('sessions.title')}</h3>
 <div className="sessions-status-bar">
 <span className={`sessions-conn ${connected ? 'conn-ok' : 'conn-err'}`}>{connected ? t('sessions.connected') : t('sessions.disconnected')}</span>
 {data?.proxy_relay && <span className="sessions-relay">🔗 {t('sessions.relay_active')} (PID {data.proxy_relay.pid})</span>}
 {data && <span className="sessions-count">{data.total_active} {t('sessions.active_count')}</span>}
 </div>
 {error && <div className="chat-error">❌ {error}</div>}
 <div className="sessions-grid">
 {!data || data.sessions.length === 0 ? <div className="sessions-empty">{t('sessions.empty')}</div> : (
 data.sessions.map((session) => (
 <div key={session.session_id} className="session-card" style={{ '--agent-color': AGENT_COLORS[session.agent_type] || '#666' } as React.CSSProperties}>
 <div className="session-card-header">
 <span className="session-icon">{AGENT_ICONS[session.agent_type] || '⚪'}</span>
 <span className="session-agent-name">{session.agent_type.toUpperCase()}</span>
 <span className={`session-status-badge status-${session.status}`}>{session.status}</span>
 </div>
 <div className="session-details">
 {session.pid && <div className="session-detail"><span className="detail-label">{t('sessions.pid')}</span><span className="detail-value">{session.pid}</span></div>}
 {session.model && <div className="session-detail"><span className="detail-label">{t('sessions.model')}</span><span className="detail-value">{session.model}</span></div>}
 {session.proxy_url && <div className="session-detail"><span className="detail-label">{t('sessions.proxy')}</span><span className="detail-value detail-proxy">{session.proxy_url}</span></div>}
 {session.started_at && <div className="session-detail"><span className="detail-label">{t('sessions.started')}</span><span className="detail-value">{new Date(session.started_at).toLocaleTimeString()}</span></div>}
 </div>
 </div>
 ))
 )}
 </div>
 {data && <div className="sessions-summary">{Object.entries(data.by_agent).map(([agent, count]) => (<div key={agent} className="summary-chip" style={{ borderColor: AGENT_COLORS[agent] || '#666' }}>{AGENT_ICONS[agent] || '⚪'} {agent}: {count}</div>))}</div>}
 </div>
 );
}

// --- Memory View ---

function MemoryView() {
 const [memories, setMemories] = useState<MemoryItem[]>([]);
 const [loading, setLoading] = useState(false);
 const [query, setQuery] = useState('');

 const loadMemories = useCallback(async (q: string) => {
 try { setLoading(true);
 const resp = await fetch('http://localhost:8004/recall', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ query: q || '*', limit: 20 }) });
 if (resp.ok) { const data = await resp.json(); setMemories(data.results || []); }
 } catch {} finally { setLoading(false); }
 }, []);

 useEffect(() => { loadMemories(''); }, [loadMemories]);

 return (
 <div className="memory-view">
 <h3 className="panel-title">{t('memory.title')}</h3>
 <div className="memory-search">
 <input className="memory-search-input" placeholder={t('memory.search_placeholder')} value={query} onChange={(e) => setQuery(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && loadMemories(query)} />
 <button className="memory-search-btn" onClick={() => loadMemories(query)}>🔍</button>
 </div>
 <div className="memory-list">
 {loading ? <div className="memory-loading">{t('memory.loading')}</div> : memories.length === 0 ? <div className="memory-empty">{t('memory.empty')}</div> : (
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

// --- Messaging Panel ---

function MessagingPanel() {
 const [messages, setMessages] = useState<InboxMessage[]>([]);
 const [loading, setLoading] = useState(false);
 const [channels, setChannels] = useState<Record<string, { configured: boolean }>>({});
 const [composeChannel, setComposeChannel] = useState('telegram');
 const [composeTo, setComposeTo] = useState('');
 const [composeBody, setComposeBody] = useState('');
 const [composeSubject, setComposeSubject] = useState('');
 const [sendStatus, setSendStatus] = useState<string | null>(null);

 useEffect(() => {
 async function loadData() {
 try {
 const chResp = await fetch('http://localhost:8008/channels');
 if (chResp.ok) { const d = await chResp.json(); setChannels(d.channels || {}); }
 } catch {}
 }
 loadData();
 }, []);

 const fetchInbox = useCallback(async () => {
 setLoading(true);
 try {
 const resp = await fetch('http://localhost:8008/inbox');
 if (resp.ok) { const d = await resp.json(); setMessages(d.messages || []); }
 } catch {} finally { setLoading(false); }
 }, []);

 useEffect(() => { fetchInbox(); }, [fetchInbox]);

 const handleSend = useCallback(async () => {
 if (!composeTo.trim() || !composeBody.trim()) return;
 try {
 const resp = await fetch('http://localhost:8008/send', {
 method: 'POST', headers: { 'Content-Type': 'application/json' },
 body: JSON.stringify({ channel: composeChannel, to: composeTo, content: composeBody, subject: composeSubject || undefined }),
 });
 if (resp.ok) { setSendStatus('✅ Sent'); setComposeTo(''); setComposeBody(''); setComposeSubject(''); setTimeout(() => setSendStatus(null), 3000); }
 else { const d = await resp.json().catch(() => ({})); setSendStatus(`❌ ${d.detail || 'Failed'}`); }
 } catch { setSendStatus('❌ Network error'); }
 }, [composeChannel, composeTo, composeBody, composeSubject]);

 const activeChannels = Object.entries(channels).filter(([, v]) => v.configured);

 return (
 <div className="messaging-panel">
 <h3 className="panel-title">{t('messaging.title')}</h3>

 {/* Channel status */}
 <div className="messaging-channels">
 <span className="messaging-channels-label">{t('messaging.channels')}:</span>
 {activeChannels.length === 0 ? <span className="settings-note">{t('messaging.no_channels')}</span> : (
 activeChannels.map(([name]) => (
 <span key={name} className="channel-badge">
 {name === 'telegram' ? '✈️' : name === 'whatsapp' ? '📱' : '📧'} {t(`messaging.channel_${name}` as any)} — {t('messaging.status_connected')}
 </span>
 ))
 )}
 <button className="refresh-btn-sm" onClick={fetchInbox} disabled={loading}>{loading ? '...' : '🔄'}</button>
 </div>

 <div className="messaging-layout">
 {/* Inbox */}
 <div className="messaging-inbox">
 <h4 className="inbox-title">{t('messaging.inbox')} ({messages.length})</h4>
 {messages.length === 0 ? <div className="memory-empty">{t('memory.empty')}</div> : (
 messages.map((msg, i) => (
 <div key={i} className="inbox-item">
 <div className="inbox-meta">
 <span className="inbox-channel">{msg.channel === 'telegram' ? '✈️' : msg.channel === 'whatsapp' ? '📱' : '📧'}</span>
 <span className="inbox-sender">{msg.sender}</span>
 <span className="inbox-time">{msg.timestamp ? new Date(msg.timestamp).toLocaleString() : ''}</span>
 </div>
 {msg.subject && <div className="inbox-subject">{msg.subject}</div>}
 <div className="inbox-content">{msg.content.slice(0, 200)}{msg.content.length > 200 ? '...' : ''}</div>
 </div>
 ))
 )}
 </div>

 {/* Compose */}
 <div className="messaging-compose">
 <h4 className="inbox-title">{t('messaging.compose')}</h4>
 <select className="chat-select" value={composeChannel} onChange={(e) => setComposeChannel(e.target.value)}>
 <option value="telegram">✈️ Telegram</option>
 <option value="whatsapp">📱 WhatsApp</option>
 <option value="email">📧 Email</option>
 </select>
 <input className="chat-input" placeholder={t('messaging.to')} value={composeTo} onChange={(e) => setComposeTo(e.target.value)} style={{ marginTop: 6 }} />
 {composeChannel === 'email' && <input className="chat-input" placeholder={t('messaging.subject')} value={composeSubject} onChange={(e) => setComposeSubject(e.target.value)} style={{ marginTop: 6 }} />}
 <textarea className="chat-input messaging-textarea" placeholder={t('messaging.body')} value={composeBody} onChange={(e) => setComposeBody(e.target.value)} rows={4} style={{ marginTop: 6 }} />
 <div style={{ display: 'flex', gap: 8, marginTop: 8, alignItems: 'center' }}>
 <button className="save-btn" onClick={handleSend}>{t('messaging.send')}</button>
 {sendStatus && <span className="save-feedback">{sendStatus}</span>}
 </div>
 </div>
 </div>
 </div>
 );
}

// --- Main App ---

export default function App() {
 const [activeTab, setActiveTab] = useState<Tab>('dashboard');
 const [currentTime, setCurrentTime] = useState(new Date());
 const [providerStatuses, setProviderStatuses] = useState<ProviderStatus[]>([]);

 useEffect(() => { initLocale(); }, []);
 useEffect(() => { const interval = setInterval(() => setCurrentTime(new Date()), 1000); return () => clearInterval(interval); }, []);

 useEffect(() => {
 async function fetchStatuses() {
 try { const resp = await fetch('http://localhost:8003/providers'); if (resp.ok) { const data = await resp.json(); setProviderStatuses(data.providers || []); } } catch {}
 }
 fetchStatuses();
 const interval = setInterval(fetchStatuses, 30000);
 return () => clearInterval(interval);
 }, []);

 const tabs: { id: Tab; labelKey: string; icon: string }[] = [
 { id: 'dashboard', labelKey: 'nav.dashboard', icon: '◈' },
 { id: 'chat', labelKey: 'nav.chat', icon: '💬' },
 { id: 'sessions', labelKey: 'nav.sessions', icon: '📡' },
 { id: 'agents', labelKey: 'nav.agents', icon: '🤖' },
 { id: 'messaging', labelKey: 'nav.messaging', icon: '✉️' },
 { id: 'settings', labelKey: 'nav.settings', icon: '🔑' },
 { id: 'memory', labelKey: 'nav.memory', icon: '🧠' },
 ];

 return (
 <div className="jarvis-hud">
 <header className="hud-header">
 <div className="hud-logo">◈ JARVIS</div>
 <nav className="hud-nav">
 {tabs.map(tab => (
 <button key={tab.id} className={`nav-tab ${activeTab === tab.id ? 'active' : ''}`} onClick={() => setActiveTab(tab.id)}>
 <span className="nav-icon">{tab.icon}</span>
 <span className="nav-label">{t(tab.labelKey)}</span>
 </button>
 ))}
 </nav>
 <div className="hud-clock-group">
 <div className="hud-clock">{currentTime.toLocaleTimeString(getLocale() === 'fr' ? 'fr-FR' : 'en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}</div>
 <div className="hud-date">{currentTime.toLocaleDateString(getLocale() === 'fr' ? 'fr-FR' : 'en-US', { weekday: 'short', day: 'numeric', month: 'short' })}</div>
 </div>
 </header>

 <main className="hud-main">
 {activeTab === 'dashboard' && <DashboardView statuses={providerStatuses} />}
 {activeTab === 'chat' && <ChatPanel />}
 {activeTab === 'sessions' && <SessionsPanel />}
 {activeTab === 'agents' && <AgentsDetailView statuses={providerStatuses} />}
 {activeTab === 'messaging' && <MessagingPanel />}
 {activeTab === 'settings' && <SettingsPanel />}
 {activeTab === 'memory' && <MemoryView />}
 </main>

 <footer className="hud-footer">
 <span>{t('footer.sys')}: {t('footer.online')}</span>
 <span>STT: :8001</span><span>TTS: :8002</span><span>CORE: :8003</span><span>MEM: :8004</span><span>CONN: :8005</span><span>SESS: :8007</span><span>MSG: :8008</span>
 </footer>
 </div>
 );
}