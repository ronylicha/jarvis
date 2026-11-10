import { useCallback, useEffect, useState } from 'react';
import './App.css';
import { t, setLocale, getLocale, initLocale, type Locale } from './i18n';
import { encryptKeys, decryptKeys, encryptValue, decryptValue } from './crypto';

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

/** Provider metadata — NO hardcoded models. Models are fetched live from APIs. */
interface ProviderMeta {
 id: string;
 name: string;
 color: string;
 icon: string;
 authType: 'api_key' | 'oauth';
 /** OAuth authorization URL (only for oauth providers) */
 oauthUrl?: string;
}

interface LiveModel {
 id: string;
 name: string;
 owned_by?: string;
 /** Pricing/context populated only when available from API */
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

interface OnboardingData {
 userName: string;
 locale: Locale;
 sttLanguage: string;
 ttsVoice: string;
 voiceSpeed: number;
 completed: boolean;
}

// --- Provider metadata (NO models — fetched live from APIs) ---

const PROVIDER_META: ProviderMeta[] = [
 { id: 'anthropic', name: 'Claude', color: '#d97706', icon: '🟠', authType: 'oauth', oauthUrl: 'https://console.anthropic.com/settings/keys' },
 { id: 'openai', name: 'OpenAI / Codex', color: '#10b981', icon: '🟢', authType: 'oauth', oauthUrl: 'https://platform.openai.com/api-keys' },
 { id: 'google', name: 'Gemini', color: '#3b82f6', icon: '🔵', authType: 'oauth', oauthUrl: 'https://aistudio.google.com/apikey' },
 { id: 'moonshot', name: 'Kimi', color: '#8b5cf6', icon: '🟣', authType: 'api_key' },
 { id: 'minimax', name: 'MiniMax', color: '#ec4899', icon: '💗', authType: 'api_key' },
 { id: 'zhipu', name: 'GLM (Zhipu)', color: '#06b6d4', icon: '🩵', authType: 'api_key' },
 { id: 'openrouter', name: 'OpenRouter', color: '#f59e0b', icon: '🔶', authType: 'api_key' },
 { id: 'ollama', name: 'Ollama (Local)', color: '#6b7280', icon: '🦙', authType: 'api_key' },
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

// --- Onboarding ---

const ONBOARDING_KEY = 'jarvis_onboarding';

function loadOnboarding(): OnboardingData {
 try {
 const stored = localStorage.getItem(ONBOARDING_KEY);
 if (stored) return JSON.parse(stored);
 } catch {}
 return { userName: '', locale: 'fr', sttLanguage: '', ttsVoice: '', voiceSpeed: 1.0, completed: false };
}

function saveOnboarding(data: OnboardingData) {
 localStorage.setItem(ONBOARDING_KEY, JSON.stringify(data));
}

function OnboardingWizard({ onComplete }: { onComplete: (data: OnboardingData) => void }) {
 const [step, setStep] = useState(0);
 const [userName, setUserName] = useState('');
 const [locale, setLocaleState] = useState<Locale>('fr');
 const [sttLang, setSttLang] = useState('');
 const [ttsVoice, setTtsVoice] = useState('');
 const [voiceSpeed, setVoiceSpeed] = useState(1.0);
 const [apiKey, setApiKey] = useState('');
 const [selectedProvider, setSelectedProvider] = useState('anthropic');

 const steps = ['welcome', 'language', 'voice', 'provider'];

 const canProceed = () => {
 switch (steps[step]) {
 case 'welcome': return userName.trim().length > 0;
 case 'language': return true; // locale always has default
 case 'voice': return sttLang !== '' && ttsVoice !== '';
 case 'provider': {
 // OAuth providers (Claude, Gemini) don't require pasting a key — user gets it via OAuth link
 const meta = PROVIDER_META.find(p => p.id === selectedProvider);
 if (meta?.authType === 'oauth') return true;
 return apiKey.trim().length > 0 || selectedProvider === 'ollama';
 }
 default: return false;
 }
 };

 const handleNext = async () => {
 if (step < steps.length - 1) {
 setStep(step + 1);
 } else {
 // Save onboarding data
 const data: OnboardingData = {
 userName: userName.trim(),
 locale,
 sttLanguage: sttLang,
 ttsVoice,
 voiceSpeed,
 completed: true,
 };
 saveOnboarding(data);
 setLocale(locale);
 // Save API key (encrypted via AES-GCM)
 try {
 const stored = localStorage.getItem('jarvis_api_keys');
 const keys = stored ? JSON.parse(stored) : {};
 keys[selectedProvider] = await encryptValue(apiKey.trim());
 localStorage.setItem('jarvis_api_keys', JSON.stringify(keys));
 } catch {}
 // Save voice settings
 localStorage.setItem('jarvis_voice_settings', JSON.stringify({ sttLang, ttsVoice, voiceSpeed }));
 onComplete(data);
 }
 };

 const currentProvider = PROVIDER_META.find(p => p.id === selectedProvider) || PROVIDER_META[0];

 return (
 <div className="onboarding-overlay">
 <div className="onboarding-card">
 <div className="onboarding-header">
 <span className="onboarding-logo">◈ JARVIS</span>
 <span className="onboarding-step">{step + 1}/{steps.length}</span>
 </div>

 {step === 0 && (
 <div className="onboarding-step">
 <h2>{locale === 'fr' ? 'Bienvenue sur Jarvis' : 'Welcome to Jarvis'}</h2>
 <p>{locale === 'fr' ? 'Commençons par faire connaissance.' : "Let's get started."}</p>
 <label className="onboarding-label">{locale === 'fr' ? 'Votre nom' : 'Your name'}</label>
 <input className="onboarding-input" placeholder={locale === 'fr' ? 'Ex: Rony' : 'e.g. Rony'} value={userName} onChange={(e) => setUserName(e.target.value)} autoFocus />
 </div>
 )}

 {step === 1 && (
 <div className="onboarding-step">
 <h2>{locale === 'fr' ? 'Langue de l\'interface' : 'Interface language'}</h2>
 <div className="locale-selector">
 <button className={`locale-btn ${locale === 'fr' ? 'active' : ''}`} onClick={() => setLocaleState('fr')}>🇫🇷 Français</button>
 <button className={`locale-btn ${locale === 'en' ? 'active' : ''}`} onClick={() => setLocaleState('en')}>🇬🇧 English</button>
 </div>
 </div>
 )}

 {step === 2 && (
 <div className="onboarding-step">
 <h2>{locale === 'fr' ? 'Paramètres voix' : 'Voice settings'}</h2>
 <label className="onboarding-label">{locale === 'fr' ? 'Langue transcription (STT)' : 'Transcription language (STT)'}</label>
 <select className="onboarding-select" value={sttLang} onChange={(e) => setSttLang(e.target.value)}>
 <option value="">{locale === 'fr' ? '— Choisir —' : '— Select —'}</option>
 {STT_LANGUAGES.map(l => <option key={l.code} value={l.code}>{l.label}</option>)}
 </select>
 <label className="onboarding-label" style={{ marginTop: 12 }}>{locale === 'fr' ? 'Voix synthèse (TTS)' : 'Synthesis voice (TTS)'}</label>
 <select className="onboarding-select" value={ttsVoice} onChange={(e) => setTtsVoice(e.target.value)}>
 <option value="">{locale === 'fr' ? '— Choisir —' : '— Select —'}</option>
 {TTS_VOICES.map(v => <option key={v.id} value={v.id}>{v.label}</option>)}
 </select>
 <label className="onboarding-label" style={{ marginTop: 12 }}>{locale === 'fr' ? `Vitesse: ${voiceSpeed.toFixed(1)}x` : `Speed: ${voiceSpeed.toFixed(1)}x`}</label>
 <input type="range" min="0.5" max="2.0" step="0.1" value={voiceSpeed} onChange={(e) => setVoiceSpeed(parseFloat(e.target.value))} className="voice-slider" />
 </div>
 )}

 {step === 3 && (
 <div className="onboarding-step">
 <h2>{locale === 'fr' ? 'Premier provider IA' : 'First AI provider'}</h2>
 <p className="settings-note">{locale === 'fr' ? 'Choisissez au moins un provider pour commencer.' : 'Choose at least one provider to get started.'}</p>
 <select className="onboarding-select" value={selectedProvider} onChange={(e) => { setSelectedProvider(e.target.value); setApiKey(''); }}>
 {PROVIDER_META.map(p => <option key={p.id} value={p.id}>{p.icon} {p.name} ({p.authType === 'oauth' ? 'OAuth' : p.id === 'ollama' ? 'Local' : 'API Key'})</option>)}
 </select>

 {/* OAuth providers: auto-open browser + paste key field */}
 {currentProvider.authType === 'oauth' && currentProvider.oauthUrl && (
 <div className="oauth-flow">
 <button
 className="oauth-launch-btn"
 style={{ borderColor: currentProvider.color, color: currentProvider.color }}
 onClick={() => window.open(currentProvider.oauthUrl!, '_blank')}
 >
 🔗 {locale === 'fr' ? `Se connecter à ${currentProvider.name}` : `Connect to ${currentProvider.name}`}
 </button>
 <p className="settings-note" style={{ marginTop: 8 }}>
 {locale === 'fr'
 ? `Le navigateur s'ouvre vers la console ${currentProvider.name}. Créez ou copiez votre clé API, puis collez-la ci-dessous.`
 : `Browser opens to ${currentProvider.name} console. Create or copy your API key, then paste it below.`}
 </p>
 <label className="onboarding-label">{locale === 'fr' ? 'Collez votre clé API' : 'Paste your API key'}</label>
 <input className="onboarding-input" type="password" placeholder="sk-ant-... / AIza..." value={apiKey} onChange={(e) => setApiKey(e.target.value)} autoFocus />
 </div>
 )}

 {/* API key providers: direct key input */}
 {currentProvider.authType === 'api_key' && selectedProvider !== 'ollama' && (
 <div>
 <label className="onboarding-label" style={{ marginTop: 12 }}>API Key</label>
 <input className="onboarding-input" type="password" placeholder="sk-..." value={apiKey} onChange={(e) => setApiKey(e.target.value)} autoFocus />
 </div>
 )}

 {/* Ollama: no key needed */}
 {selectedProvider === 'ollama' && (
 <div>
 <p className="settings-note" style={{ marginTop: 12 }}>
 {locale === 'fr' ? '🦙 Ollama tourne localement. Aucune clé API requise.' : '🦙 Ollama runs locally. No API key needed.'}
 </p>
 </div>
 )}
 </div>
 )}

 <div className="onboarding-footer">
 {step > 0 && <button className="onboarding-back-btn" onClick={() => setStep(step - 1)}>{locale === 'fr' ? '← Retour' : '← Back'}</button>}
 <button className="onboarding-next-btn" onClick={handleNext} disabled={!canProceed()}>
 {step === steps.length - 1 ? (locale === 'fr' ? '✓ Terminer' : '✓ Finish') : (locale === 'fr' ? 'Suivant →' : 'Next →')}
 </button>
 </div>
 </div>
 </div>
 );
}

// --- Sub-components ---

function AgentCard({ providerId, status, modelCount }: { providerId: string; status?: ProviderStatus; modelCount: number }) {
 const meta = PROVIDER_META.find(p => p.id === providerId);
 if (!meta) return null;
 const isConfigured = status?.configured ?? false;
 if (!isConfigured) return null;
 return (
 <div className="agent-card" style={{ '--agent-color': meta.color } as React.CSSProperties}>
 <div className="agent-card-header">
 <span className="agent-icon">{meta.icon}</span>
 <div className="agent-info">
 <span className="agent-name">{meta.name}</span>
 <span className="agent-auth-type">{meta.authType === 'oauth' ? 'OAuth' : 'API Key'}</span>
 </div>
 <span className="agent-status-dot status-configured" />
 </div>
 <div className="agent-models-count">{modelCount} {t('common.models')}</div>
 </div>
 );
}

function ModelTable({ providerId, models, onRefresh, refreshing }: { providerId: string; models: LiveModel[]; onRefresh: () => void; refreshing: boolean }) {
 const meta = PROVIDER_META.find(p => p.id === providerId);
 if (!meta) return null;
 return (
 <div className="model-table-container">
 <div className="model-table-header">
 <h4 className="model-table-title" style={{ color: meta.color }}>
 {meta.icon} {meta.name} — {t('agents.models_title')}
 </h4>
 <button className="refresh-btn" onClick={onRefresh} disabled={refreshing}>
 {refreshing ? t('agents.refreshing') : t('agents.refresh_models')}
 </button>
 </div>
 {models.length === 0 ? (
 <div className="settings-note" style={{ padding: 20, textAlign: 'center' }}>
 {refreshing ? t('agents.refreshing') : (t('agents.only_configured') + ' — ' + t('agents.refresh_models'))}
 </div>
 ) : (
 <table className="model-table">
 <thead><tr><th>{t('agents.th_model')}</th><th>ID</th><th>{t('agents.th_context')}</th></tr></thead>
 <tbody>
 {models.map((m) => (
 <tr key={m.id}>
 <td className="model-name">{m.name || m.id}</td>
 <td className="model-context" style={{ fontSize: 10, opacity: 0.6 }}>{m.id}</td>
 <td className="model-context">{m.contextWindow ? `${(m.contextWindow / 1000).toFixed(0)}K` : '—'}</td>
 </tr>
 ))}
 </tbody>
 </table>
 )}
 </div>
 );
}

function SettingsPanel({ onKeysChanged }: { onKeysChanged?: () => void }) {
 const [keys, setKeys] = useState<Record<string, string>>({});
 const [saved, setSaved] = useState<string | null>(null);
 const [showKey, setShowKey] = useState<Record<string, boolean>>({});
 const [locale, setLocaleState] = useState<Locale>(getLocale());
 const [sttLang, setSttLang] = useState('fr');
 const [ttsVoice, setTtsVoice] = useState('fr_FR-siwis-medium');
 const [voiceSpeed, setVoiceSpeed] = useState(1.0);

 useEffect(() => {
 async function loadKeys() {
 try {
 const stored = localStorage.getItem('jarvis_api_keys');
 if (stored) {
 const encrypted = JSON.parse(stored);
 const decrypted = await decryptKeys(encrypted);
 setKeys(decrypted);
 }
 const vs = localStorage.getItem('jarvis_voice_settings');
 if (vs) { const v = JSON.parse(vs); if (v.sttLang) setSttLang(v.sttLang); if (v.ttsVoice) setTtsVoice(v.ttsVoice); if (v.voiceSpeed) setVoiceSpeed(v.voiceSpeed); }
 } catch {}
 }
 loadKeys();
 }, []);

 const handleSave = useCallback(async () => {
 try {
 const encrypted = await encryptKeys(keys);
 localStorage.setItem('jarvis_api_keys', JSON.stringify(encrypted));
 localStorage.setItem('jarvis_voice_settings', JSON.stringify({ sttLang, ttsVoice, voiceSpeed }));
 setSaved(t('settings.saved'));
 setTimeout(() => setSaved(null), 3000);
 onKeysChanged?.();
 } catch { setSaved(t('settings.error')); }
 }, [keys, sttLang, ttsVoice, voiceSpeed, onKeysChanged]);

 const handleLocaleChange = (newLocale: Locale) => { setLocale(newLocale); setLocaleState(newLocale); };

 return (
 <div className="settings-panel">
 <h3 className="panel-title">{t('settings.language')}</h3>
 <div className="locale-selector">
 <button className={`locale-btn ${locale === 'fr' ? 'active' : ''}`} onClick={() => handleLocaleChange('fr')}>🇫🇷 Français</button>
 <button className={`locale-btn ${locale === 'en' ? 'active' : ''}`} onClick={() => handleLocaleChange('en')}>🇬🇧 English</button>
 </div>

 <h3 className="panel-title" style={{ marginTop: 20 }}>{t('settings.section_voice')}</h3>
 <div className="voice-settings">
 <div className="voice-row"><label>{t('settings.stt_language')}</label><select value={sttLang} onChange={(e) => setSttLang(e.target.value)} className="voice-select">{STT_LANGUAGES.map(l => <option key={l.code} value={l.code}>{l.label}</option>)}</select></div>
 <div className="voice-row"><label>{t('settings.tts_voice')}</label><select value={ttsVoice} onChange={(e) => setTtsVoice(e.target.value)} className="voice-select">{TTS_VOICES.map(v => <option key={v.id} value={v.id}>{v.label}</option>)}</select></div>
 <div className="voice-row"><label>{t('settings.voice_speed')}: {voiceSpeed.toFixed(1)}x</label><input type="range" min="0.5" max="2.0" step="0.1" value={voiceSpeed} onChange={(e) => setVoiceSpeed(parseFloat(e.target.value))} className="voice-slider" /></div>
 </div>

 <h3 className="panel-title" style={{ marginTop: 20 }}>{t('settings.section_keys')}</h3>
 <p className="settings-note">{t('settings.note')}</p>
 <div className="key-list">
 {PROVIDER_META.map((p) => (
 <div key={p.id} className="key-row">
 <label className="key-label" style={{ color: p.color }}>{p.icon} {p.name}<span className="key-auth-badge">{p.authType}</span></label>
 <div className="key-input-row">
 <input type={showKey[p.id] ? 'text' : 'password'} className="key-input" placeholder={p.authType === 'oauth' ? 'OAuth / API key' : 'sk-...'} value={keys[p.id] || ''} onChange={(e) => setKeys(prev => ({ ...prev, [p.id]: e.target.value }))} />
 {p.authType === 'api_key' && <button className="key-toggle-btn" onClick={() => setShowKey(prev => ({ ...prev, [p.id]: !prev[p.id] }))}>{showKey[p.id] ? '🙈' : '👁️'}</button>}
 {p.authType === 'oauth' && p.oauthUrl && <a href={p.oauthUrl} target="_blank" rel="noopener noreferrer" className="key-oauth-btn" style={{ borderColor: p.color, color: p.color, textDecoration: 'none', display: 'flex', alignItems: 'center' }}>🔗 {t('settings.oauth_connect')}</a>}
 </div>
 </div>
 ))}
 </div>

 <h3 className="panel-title" style={{ marginTop: 20 }}>{t('settings.section_messaging')}</h3>
 <p className="settings-note">{t('settings.messaging_note')}</p>
 <div className="key-list">
 <div className="key-row"><label className="key-label" style={{ color: '#229ED9' }}>✈️ Telegram</label><div className="key-input-row"><input className="key-input" placeholder={t('settings.telegram_token')} value={keys['telegram_token'] || ''} onChange={(e) => setKeys(prev => ({ ...prev, telegram_token: e.target.value }))} /></div><div className="key-input-row" style={{ marginTop: 4 }}><input className="key-input" placeholder={t('settings.telegram_chat_id')} value={keys['telegram_chat_id'] || ''} onChange={(e) => setKeys(prev => ({ ...prev, telegram_chat_id: e.target.value }))} /></div></div>
 <div className="key-row"><label className="key-label" style={{ color: '#25D366' }}>📱 WhatsApp</label><div className="key-input-row"><input className="key-input" placeholder={t('settings.whatsapp_token')} value={keys['whatsapp_token'] || ''} onChange={(e) => setKeys(prev => ({ ...prev, whatsapp_token: e.target.value }))} /></div><div className="key-input-row" style={{ marginTop: 4 }}><input className="key-input" placeholder={t('settings.whatsapp_phone_id')} value={keys['whatsapp_phone_id'] || ''} onChange={(e) => setKeys(prev => ({ ...prev, whatsapp_phone_id: e.target.value }))} /></div></div>
 <div className="key-row"><label className="key-label" style={{ color: '#EA4335' }}>📧 Email</label><div className="key-input-row"><input className="key-input" placeholder={t('settings.email_imap_host')} value={keys['email_imap_host'] || ''} onChange={(e) => setKeys(prev => ({ ...prev, email_imap_host: e.target.value }))} /></div><div className="key-input-row" style={{ marginTop: 4 }}><input className="key-input" placeholder={t('settings.email_imap_user')} value={keys['email_imap_user'] || ''} onChange={(e) => setKeys(prev => ({ ...prev, email_imap_user: e.target.value }))} /></div><div className="key-input-row" style={{ marginTop: 4 }}><input className="key-input" type="password" placeholder={t('settings.email_imap_pass')} value={keys['email_imap_pass'] || ''} onChange={(e) => setKeys(prev => ({ ...prev, email_imap_pass: e.target.value }))} /></div></div>
 </div>

 <div className="settings-actions"><button className="save-btn" onClick={handleSave}>💾 {t('settings.save')}</button>{saved && <span className="save-feedback">{saved}</span>}</div>
 </div>
 );
}

function DashboardView({ statuses, liveModels }: { statuses: ProviderStatus[]; liveModels: Record<string, LiveModel[]> }) {
 const configuredProviders = statuses.filter(s => s.configured);
 const configuredCount = configuredProviders.length;
 const totalModels = configuredProviders.reduce((sum, s) => sum + (liveModels[s.name]?.length || 0), 0);

 return (
 <div className="dashboard-view">
 <div className="dash-stats">
 <div className="stat-card"><span className="stat-value">{configuredCount}/{PROVIDER_META.length}</span><span className="stat-label">{t('dash.providers_configured')}</span></div>
 <div className="stat-card"><span className="stat-value">{totalModels}</span><span className="stat-label">{t('dash.models_available')}</span></div>
 </div>
 <h3 className="panel-title" style={{ marginTop: 24 }}>{t('dash.hub_agents')}</h3>
 {configuredCount === 0 && <p className="settings-note">{t('dash.no_providers')}</p>}
 <div className="agent-grid">
 {statuses.map(s => <AgentCard key={s.name} providerId={s.name} status={s} modelCount={liveModels[s.name]?.length || 0} />)}
 </div>
 </div>
 );
}

function AgentsDetailView({ statuses, liveModels, onRefresh }: { statuses: ProviderStatus[]; liveModels: Record<string, LiveModel[]>; onRefresh: (provider: string) => void }) {
 const configuredProviders = statuses.filter(s => s.configured);
 const [selectedProvider, setSelectedProvider] = useState<string>(configuredProviders[0]?.name || '');
 const [refreshing, setRefreshing] = useState(false);

 useEffect(() => { if (configuredProviders.length > 0 && !selectedProvider) setSelectedProvider(configuredProviders[0].name); }, [configuredProviders, selectedProvider]);

 const handleRefresh = useCallback(async () => {
 setRefreshing(true);
 await onRefresh(selectedProvider);
 setTimeout(() => setRefreshing(false), 1500);
 }, [selectedProvider, onRefresh]);

 if (configuredProviders.length === 0) return <div className="settings-note" style={{ padding: 40, textAlign: 'center' }}>{t('agents.only_configured')}</div>;

 return (
 <div className="agents-detail">
 <p className="settings-note">{t('agents.only_configured')}</p>
 <div className="provider-tabs">
 {configuredProviders.map(s => {
 const meta = PROVIDER_META.find(p => p.id === s.name);
 if (!meta) return null;
 return <button key={s.name} className={`provider-tab ${selectedProvider === s.name ? 'active' : ''}`} style={{ '--tab-color': meta.color } as React.CSSProperties} onClick={() => setSelectedProvider(s.name)}>{meta.icon} {meta.name}</button>;
 })}
 </div>
 <ModelTable providerId={selectedProvider} models={liveModels[selectedProvider] || []} onRefresh={handleRefresh} refreshing={refreshing} />
 </div>
 );
}

// --- Chat Panel ---

const CHAT_STORAGE_KEY = 'jarvis_chat_history';
function loadChatHistory(): ChatMessage[] { try { const s = localStorage.getItem(CHAT_STORAGE_KEY); return s ? JSON.parse(s) : []; } catch { return []; } }
function saveChatHistory(msgs: ChatMessage[]) { try { localStorage.setItem(CHAT_STORAGE_KEY, JSON.stringify(msgs.slice(-200))); } catch {} }

function ChatPanel({ welcomeMessage }: { welcomeMessage?: string }) {
 const [messages, setMessages] = useState<ChatMessage[]>(() => {
 const hist = loadChatHistory();
 if (hist.length === 0 && welcomeMessage) {
 return [{ role: 'assistant', content: welcomeMessage, provider: 'jarvis', timestamp: Date.now() }];
 }
 return hist;
 });

 // Speak welcome message aloud via TTS service on first load
 useEffect(() => {
 if (!welcomeMessage) return;
 const spokenKey = 'jarvis_welcome_spoken';
 if (sessionStorage.getItem(spokenKey)) return;

 async function speakWelcome() {
 try {
 const vs = localStorage.getItem('jarvis_voice_settings');
 const voice = vs ? JSON.parse(vs).ttsVoice : 'fr_FR-siwis-medium';
 const speed = vs ? JSON.parse(vs).voiceSpeed : 1.0;

 const resp = await fetch('http://localhost:8002/speak', {
 method: 'POST',
 headers: { 'Content-Type': 'application/json' },
 body: JSON.stringify({ text: welcomeMessage, voice, speed }),
 });

 if (resp.ok) {
 const audioBlob = await resp.blob();
 const audioUrl = URL.createObjectURL(audioBlob);
 const audio = new Audio(audioUrl);
 audio.play().catch(() => {}); // Ignore autoplay policy errors
 sessionStorage.setItem(spokenKey, 'true');
 }
 } catch {
 // TTS service may not be running yet — silent fallback
 }
 }

 // Small delay to ensure UI is rendered before speaking
 const timer = setTimeout(speakWelcome, 1500);
 return () => clearTimeout(timer);
 }, [welcomeMessage]);
 const [input, setInput] = useState('');
 const [selectedProvider, setSelectedProvider] = useState('');
 const [selectedModel, setSelectedModel] = useState('');
 const [loading, setLoading] = useState(false);
 const [error, setError] = useState<string | null>(null);
 const [streamingContent, setStreamingContent] = useState('');
 const [providerStatuses, setProviderStatuses] = useState<ProviderStatus[]>([]);
 const [liveModels, setLiveModels] = useState<Record<string, LiveModel[]>>({});

 useEffect(() => { saveChatHistory(messages); }, [messages]);

 useEffect(() => {
 async function load() {
 try {
 const resp = await fetch('http://localhost:8003/providers');
 if (resp.ok) { const d = await resp.json(); setProviderStatuses(d.providers || []); }
 } catch {}
 }
 load();
 }, []);

 const configuredProviders = providerStatuses.filter(s => s.configured);
 useEffect(() => { if (configuredProviders.length > 0 && !selectedProvider) setSelectedProvider(configuredProviders[0].name); }, [configuredProviders, selectedProvider]);

 const currentModels = liveModels[selectedProvider] || [];
 useEffect(() => { if (currentModels.length > 0 && !selectedModel) setSelectedModel(currentModels[0].id); }, [currentModels, selectedModel]);

 // Fetch models when provider changes
 useEffect(() => {
 if (!selectedProvider) return;
 async function fetchModels() {
 try {
 const resp = await fetch(`http://localhost:8003/models/refresh?provider=${selectedProvider}`);
 if (resp.ok) {
 const d = await resp.json();
 const models = d.providers?.[selectedProvider]?.models || [];
 setLiveModels(prev => ({ ...prev, [selectedProvider]: models }));
 }
 } catch {}
 }
 fetchModels();
 }, [selectedProvider]);

 const handleSend = useCallback(async () => {
 if (!input.trim() || loading || !selectedProvider) return;
 const userMsg: ChatMessage = { role: 'user', content: input.trim(), timestamp: Date.now() };
 setMessages(prev => [...prev, userMsg]);
 setInput(''); setLoading(true); setError(null); setStreamingContent('');

 const allMessages = [...messages, userMsg].map(m => ({ role: m.role, content: m.content }));
 try {
 const resp = await fetch('http://localhost:8003/chat/stream', {
 method: 'POST', headers: { 'Content-Type': 'application/json' },
 body: JSON.stringify({ messages: allMessages, provider: selectedProvider, model: selectedModel || undefined }),
 });
 if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
 if (!resp.body) throw new Error('No stream');

 const reader = resp.body.getReader(); const decoder = new TextDecoder();
 let finalContent = '', finalProvider = selectedProvider, finalModel = selectedModel;

 while (true) {
 const { done, value } = await reader.read(); if (done) break;
 const chunk = decoder.decode(value, { stream: true });
 for (const line of chunk.split('\n')) {
 if (!line.startsWith('data: ')) continue;
 try {
 const event = JSON.parse(line.slice(6).trim());
 if (event.error) throw new Error(event.error);
 if (event.done && event.content !== undefined) { finalContent = event.content; finalProvider = event.provider || finalProvider; finalModel = event.model || finalModel; }
 } catch (e) { if (e instanceof Error && e.message.includes('LLM')) throw e; }
 }
 }

 setMessages(prev => [...prev, { role: 'assistant', content: finalContent, provider: finalProvider, model: finalModel, timestamp: Date.now() }]);
 setStreamingContent('');
 } catch (exc) { setError(exc instanceof Error ? exc.message : 'Error'); setStreamingContent(''); }
 finally { setLoading(false); }
 }, [input, loading, messages, selectedProvider, selectedModel]);

 return (
 <div className="chat-panel">
 <h3 className="panel-title">{t('chat.title')}</h3>
 <div className="chat-controls">
 <select className="chat-select" value={selectedProvider} onChange={(e) => setSelectedProvider(e.target.value)}>
 {configuredProviders.map(s => { const m = PROVIDER_META.find(p => p.id === s.name); return <option key={s.name} value={s.name}>{m?.icon} {m?.name || s.name}</option>; })}
 </select>
 <select className="chat-select" value={selectedModel} onChange={(e) => setSelectedModel(e.target.value)}>
 {currentModels.map(m => <option key={m.id} value={m.id}>{m.name || m.id}</option>)}
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
 {loading && streamingContent && <div className="chat-msg chat-msg-assistant chat-msg-streaming"><div className="chat-msg-header"><span className="chat-msg-role">🤖 {selectedProvider}</span><span className="chat-streaming-indicator">● streaming</span></div><div className="chat-msg-content">{streamingContent}</div></div>}
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
 try {
 const stored = localStorage.getItem('jarvis_api_keys');
 if (stored) {
 const encrypted = JSON.parse(stored);
 const decrypted = await decryptKeys(encrypted);
 if (decrypted.agent_sessions_token) headers['X-Jarvis-Token'] = decrypted.agent_sessions_token;
 }
 } catch {}
 const resp = await fetch('http://localhost:8007/sessions/stream', { signal: abortController.signal, headers });
 if (!resp.ok || !resp.body) throw new Error(`SSE failed: HTTP ${resp.status}`);
 setConnected(true); setError(null);
 const reader = resp.body.getReader(); const decoder = new TextDecoder(); let buffer = '';
 while (true) {
 const { done, value } = await reader.read(); if (done) break;
 buffer += decoder.decode(value, { stream: true });
 const lines = buffer.split('\n'); buffer = lines.pop() || '';
 for (const line of lines) { if (!line.startsWith('data: ')) continue; try { const parsed = JSON.parse(line.slice(6).trim()); if (parsed.error) setError(parsed.error); else { setData(parsed); setError(null); } } catch {} }
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
 <div className="session-card-header"><span className="session-icon">{AGENT_ICONS[session.agent_type] || '⚪'}</span><span className="session-agent-name">{session.agent_type.toUpperCase()}</span><span className={`session-status-badge status-${session.status}`}>{session.status}</span></div>
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
 const loadMemories = useCallback(async (q: string) => { try { setLoading(true); const resp = await fetch('http://localhost:8004/recall', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ query: q || '*', limit: 20 }) }); if (resp.ok) { const data = await resp.json(); setMemories(data.results || []); } } catch {} finally { setLoading(false); } }, []);
 useEffect(() => { loadMemories(''); }, [loadMemories]);
 return (
 <div className="memory-view">
 <h3 className="panel-title">{t('memory.title')}</h3>
 <div className="memory-search"><input className="memory-search-input" placeholder={t('memory.search_placeholder')} value={query} onChange={(e) => setQuery(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && loadMemories(query)} /><button className="memory-search-btn" onClick={() => loadMemories(query)}>🔍</button></div>
 <div className="memory-list">
 {loading ? <div className="memory-loading">{t('memory.loading')}</div> : memories.length === 0 ? <div className="memory-empty">{t('memory.empty')}</div> : (
 memories.map((m) => (<div key={m.id} className="memory-item-full"><div className="memory-meta"><span className="memory-agent-tag">{(m.metadata?.agent_id as string) || 'unknown'}</span>{m.score !== undefined && <span className="memory-score">score: {m.score.toFixed(3)}</span>}</div><div className="memory-text">{m.content}</div></div>))
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

 useEffect(() => { async function loadData() { try { const chResp = await fetch('http://localhost:8008/channels'); if (chResp.ok) { const d = await chResp.json(); setChannels(d.channels || {}); } } catch {} } loadData(); }, []);
 const fetchInbox = useCallback(async () => { setLoading(true); try { const resp = await fetch('http://localhost:8008/inbox'); if (resp.ok) { const d = await resp.json(); setMessages(d.messages || []); } } catch {} finally { setLoading(false); } }, []);
 useEffect(() => { fetchInbox(); }, [fetchInbox]);
 const handleSend = useCallback(async () => { if (!composeTo.trim() || !composeBody.trim()) return; try { const resp = await fetch('http://localhost:8008/send', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ channel: composeChannel, to: composeTo, content: composeBody, subject: composeSubject || undefined }) }); if (resp.ok) { setSendStatus('✅ Sent'); setComposeTo(''); setComposeBody(''); setComposeSubject(''); setTimeout(() => setSendStatus(null), 3000); } else { const d = await resp.json().catch(() => ({})); setSendStatus(`❌ ${d.detail || 'Failed'}`); } } catch { setSendStatus('❌ Network error'); } }, [composeChannel, composeTo, composeBody, composeSubject]);
 const activeChannels = Object.entries(channels).filter(([, v]) => v.configured);

 return (
 <div className="messaging-panel">
 <h3 className="panel-title">{t('messaging.title')}</h3>
 <div className="messaging-channels"><span className="messaging-channels-label">{t('messaging.channels')}:</span>{activeChannels.length === 0 ? <span className="settings-note">{t('messaging.no_channels')}</span> : activeChannels.map(([name]) => (<span key={name} className="channel-badge">{name === 'telegram' ? '✈️' : name === 'whatsapp' ? '📱' : '📧'} {t(`messaging.channel_${name}` as any)} — {t('messaging.status_connected')}</span>))}<button className="refresh-btn-sm" onClick={fetchInbox} disabled={loading}>{loading ? '...' : '🔄'}</button></div>
 <div className="messaging-layout">
 <div className="messaging-inbox"><h4 className="inbox-title">{t('messaging.inbox')} ({messages.length})</h4>{messages.length === 0 ? <div className="memory-empty">{t('memory.empty')}</div> : messages.map((msg, i) => (<div key={i} className="inbox-item"><div className="inbox-meta"><span className="inbox-channel">{msg.channel === 'telegram' ? '✈️' : msg.channel === 'whatsapp' ? '📱' : '📧'}</span><span className="inbox-sender">{msg.sender}</span><span className="inbox-time">{msg.timestamp ? new Date(msg.timestamp).toLocaleString() : ''}</span></div>{msg.subject && <div className="inbox-subject">{msg.subject}</div>}<div className="inbox-content">{msg.content.slice(0, 200)}{msg.content.length > 200 ? '...' : ''}</div></div>))}</div>
 <div className="messaging-compose"><h4 className="inbox-title">{t('messaging.compose')}</h4><select className="chat-select" value={composeChannel} onChange={(e) => setComposeChannel(e.target.value)}><option value="telegram">✈️ Telegram</option><option value="whatsapp">📱 WhatsApp</option><option value="email">📧 Email</option></select><input className="chat-input" placeholder={t('messaging.to')} value={composeTo} onChange={(e) => setComposeTo(e.target.value)} style={{ marginTop: 6 }} />{composeChannel === 'email' && <input className="chat-input" placeholder={t('messaging.subject')} value={composeSubject} onChange={(e) => setComposeSubject(e.target.value)} style={{ marginTop: 6 }} />}<textarea className="chat-input messaging-textarea" placeholder={t('messaging.body')} value={composeBody} onChange={(e) => setComposeBody(e.target.value)} rows={4} style={{ marginTop: 6 }} /><div style={{ display: 'flex', gap: 8, marginTop: 8, alignItems: 'center' }}><button className="save-btn" onClick={handleSend}>{t('messaging.send')}</button>{sendStatus && <span className="save-feedback">{sendStatus}</span>}</div></div>
 </div>
 </div>
 );
}

// --- Main App ---

export default function App() {
 const [activeTab, setActiveTab] = useState<Tab>('dashboard');
 const [currentTime, setCurrentTime] = useState(new Date());
 const [providerStatuses, setProviderStatuses] = useState<ProviderStatus[]>([]);
 const [liveModels, setLiveModels] = useState<Record<string, LiveModel[]>>({});
 const [onboarding, setOnboarding] = useState<OnboardingData>(loadOnboarding);

 useEffect(() => { initLocale(); }, []);
 useEffect(() => { const interval = setInterval(() => setCurrentTime(new Date()), 1000); return () => clearInterval(interval); }, []);

 // Fetch provider statuses periodically
 useEffect(() => {
 async function fetchStatuses() {
 try { const resp = await fetch('http://localhost:8003/providers'); if (resp.ok) { const data = await resp.json(); setProviderStatuses(data.providers || []); } } catch {}
 }
 fetchStatuses();
 const interval = setInterval(fetchStatuses, 30000);
 return () => clearInterval(interval);
 }, []);

 // Fetch live models for all configured providers on mount and when keys change
 const refreshModelsForProvider = useCallback(async (provider: string) => {
 try {
 const resp = await fetch(`http://localhost:8003/models/refresh?provider=${provider}`);
 if (resp.ok) {
 const d = await resp.json();
 const models = d.providers?.[provider]?.models || [];
 setLiveModels(prev => ({ ...prev, [provider]: models }));
 }
 } catch {}
 }, []);

 useEffect(() => {
 providerStatuses.filter(s => s.configured).forEach(s => refreshModelsForProvider(s.name));
 }, [providerStatuses, refreshModelsForProvider]);

 const handleOnboardingComplete = (data: OnboardingData) => {
 setOnboarding(data);
 setLocale(data.locale);
 };

 // Welcome message with user's name
 const welcomeMessage = onboarding.completed && onboarding.userName
 ? (onboarding.locale === 'fr'
 ? `Bonjour ${onboarding.userName}, je suis Jarvis. Comment puis-je vous aider aujourd'hui ?`
 : `Hello ${onboarding.userName}, I'm Jarvis. How can I help you today?`)
 : undefined;

 // Show onboarding if not completed
 if (!onboarding.completed) {
 return <OnboardingWizard onComplete={handleOnboardingComplete} />;
 }

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
 {activeTab === 'dashboard' && <DashboardView statuses={providerStatuses} liveModels={liveModels} />}
 {activeTab === 'chat' && <ChatPanel welcomeMessage={welcomeMessage} />}
 {activeTab === 'sessions' && <SessionsPanel />}
 {activeTab === 'agents' && <AgentsDetailView statuses={providerStatuses} liveModels={liveModels} onRefresh={refreshModelsForProvider} />}
 {activeTab === 'messaging' && <MessagingPanel />}
 {activeTab === 'settings' && <SettingsPanel onKeysChanged={() => providerStatuses.filter(s => s.configured).forEach(s => refreshModelsForProvider(s.name))} />}
 {activeTab === 'memory' && <MemoryView />}
 </main>

 <footer className="hud-footer">
 <span>{t('footer.sys')}: {t('footer.online')}</span>
 <span>STT: :8001</span><span>TTS: :8002</span><span>CORE: :8003</span><span>MEM: :8004</span><span>CONN: :8005</span><span>SESS: :8007</span><span>MSG: :8008</span>
 </footer>
 </div>
 );
}