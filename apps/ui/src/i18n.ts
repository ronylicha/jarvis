/**
 * Jarvis i18n — lightweight FR/EN translation system.
 * No external dependency; translations are inline for zero-bundle overhead.
 */

export type Locale = 'fr' | 'en';

const TRANSLATIONS: Record<Locale, Record<string, string>> = {
 fr: {
 // Navigation
 'nav.dashboard': 'TABLEAU DE BORD',
 'nav.chat': 'CHAT',
 'nav.sessions': 'SESSIONS',
 'nav.agents': 'AGENTS & MODÈLES',
 'nav.settings': 'CLÉS API',
 'nav.memory': 'MÉMOIRE',
 'nav.messaging': 'MESSAGERIE',

 // Dashboard
 'dash.providers_configured': 'Providers configurés',
 'dash.models_available': 'Modèles disponibles',
 'dash.min_price': 'Prix min input/M',
 'dash.hub_agents': 'HUB AGENTS',
 'dash.no_providers': 'Aucun provider configuré. Ajoutez des clés API dans l\'onglet Clés API.',

 // Chat
 'chat.title': 'CHAT INTERACTIF',
 'chat.placeholder': 'Écrivez votre message...',
 'chat.sending': 'Réponse en cours...',
 'chat.connecting': 'Connexion au provider...',
 'chat.empty': 'Envoyez un message pour commencer une conversation',
 'chat.you': 'Vous',
 'chat.assistant': 'Assistant',

 // Sessions
 'sessions.title': 'SESSIONS AGENTS EN TEMPS RÉEL',
 'sessions.connected': '● Connecté SSE',
 'sessions.disconnected': '○ Déconnecté',
 'sessions.relay_active': 'Relay ghostcli actif',
 'sessions.active_count': 'session(s) active(s)',
 'sessions.empty': 'Aucune session agent détectée. Lancez Claude, Codex, Kimi ou ZAI pour les voir apparaître ici.',
 'sessions.pid': 'PID',
 'sessions.model': 'Modèle',
 'sessions.proxy': 'Proxy',
 'sessions.started': 'Démarré',

 // Settings
 'settings.title': 'CONFIGURATION CLÉS API',
 'settings.note': 'Les clés sont stockées localement. En production, utiliser un vault sécurisé.',
 'settings.save': 'Sauvegarder les clés',
 'settings.saved': 'Clés sauvegardées localement',
 'settings.error': 'Erreur de sauvegarde',
 'settings.oauth_connect': 'OAuth Connect',
 'settings.language': 'Langue / Language',
 'settings.stt_language': 'Langue transcription (STT)',
 'settings.tts_voice': 'Voix synthèse (TTS)',
 'settings.voice_speed': 'Vitesse voix',
 'settings.section_voice': 'PARAMÈTRES VOIX',
 'settings.section_keys': 'CLÉS API PROVIDERS',
 'settings.section_messaging': 'CONNECTEURS MESSAGERIE',
 'settings.telegram_token': 'Telegram Bot Token',
 'settings.telegram_chat_id': 'Telegram Chat ID',
 'settings.whatsapp_token': 'WhatsApp Business Token',
 'settings.whatsapp_phone_id': 'WhatsApp Phone Number ID',
 'settings.email_imap_host': 'Serveur IMAP',
 'settings.email_imap_user': 'Email utilisateur',
 'settings.email_imap_pass': 'Mot de passe email',
 'settings.email_smtp_host': 'Serveur SMTP',
 'settings.messaging_note': 'Configurez vos connecteurs messagerie pour recevoir des instructions via Telegram, WhatsApp ou email.',

 // Agents & Models
 'agents.models_title': 'Modèles & Tarifs',
 'agents.th_model': 'Modèle',
 'agents.th_input': 'Input $/M',
 'agents.th_output': 'Output $/M',
 'agents.th_context': 'Contexte',
 'agents.th_tags': 'Tags',
 'agents.refresh_models': '🔄 Actualiser depuis l\'API',
 'agents.refreshing': 'Actualisation...',
 'agents.only_configured': 'Seuls les providers avec clé API configurée sont affichés',

 // Memory
 'memory.title': 'MÉMOIRE GLOBALE',
 'memory.search_placeholder': 'Recherche sémantique...',
 'memory.loading': 'Chargement...',
 'memory.empty': 'Aucune mémoire trouvée',

 // Messaging
 'messaging.title': 'CENTRE DE MESSAGERIE',
 'messaging.inbox': 'Boîte de réception',
 'messaging.compose': 'Nouveau message',
 'messaging.channels': 'Canaux actifs',
 'messaging.no_channels': 'Aucun canal configuré. Configurez Telegram, WhatsApp ou email dans les Paramètres.',
 'messaging.send': 'Envoyer',
 'messaging.reply': 'Répondre',
 'messaging.from': 'De',
 'messaging.to': 'À',
 'messaging.subject': 'Sujet',
 'messaging.body': 'Message',
 'messaging.channel_telegram': 'Telegram',
 'messaging.channel_whatsapp': 'WhatsApp',
 'messaging.channel_email': 'Email',
 'messaging.status_connected': 'Connecté',
 'messaging.status_disconnected': 'Déconnecté',
 'messaging.instructions_received': 'instruction(s) reçue(s)',

 // Footer
 'footer.sys': 'SYS',
 'footer.online': 'ONLINE',

 // Common
 'common.models': 'modèles',
 'common.free': 'gratuit',
 },
 en: {
 // Navigation
 'nav.dashboard': 'DASHBOARD',
 'nav.chat': 'CHAT',
 'nav.sessions': 'SESSIONS',
 'nav.agents': 'AGENTS & MODELS',
 'nav.settings': 'API KEYS',
 'nav.memory': 'MEMORY',
 'nav.messaging': 'MESSAGING',

 // Dashboard
 'dash.providers_configured': 'Providers configured',
 'dash.models_available': 'Models available',
 'dash.min_price': 'Min input price/M',
 'dash.hub_agents': 'AGENT HUB',
 'dash.no_providers': 'No providers configured. Add API keys in the API Keys tab.',

 // Chat
 'chat.title': 'INTERACTIVE CHAT',
 'chat.placeholder': 'Type your message...',
 'chat.sending': 'Generating response...',
 'chat.connecting': 'Connecting to provider...',
 'chat.empty': 'Send a message to start a conversation',
 'chat.you': 'You',
 'chat.assistant': 'Assistant',

 // Sessions
 'sessions.title': 'REAL-TIME AGENT SESSIONS',
 'sessions.connected': '● SSE Connected',
 'sessions.disconnected': '○ Disconnected',
 'sessions.relay_active': 'GhostCLI relay active',
 'sessions.active_count': 'active session(s)',
 'sessions.empty': 'No agent sessions detected. Launch Claude, Codex, Kimi or ZAI to see them here.',
 'sessions.pid': 'PID',
 'sessions.model': 'Model',
 'sessions.proxy': 'Proxy',
 'sessions.started': 'Started',

 // Settings
 'settings.title': 'API KEYS CONFIGURATION',
 'settings.note': 'Keys stored locally. Use a secure vault in production.',
 'settings.save': 'Save keys',
 'settings.saved': 'Keys saved locally',
 'settings.error': 'Save error',
 'settings.oauth_connect': 'OAuth Connect',
 'settings.language': 'Language / Langue',
 'settings.stt_language': 'Transcription language (STT)',
 'settings.tts_voice': 'Synthesis voice (TTS)',
 'settings.voice_speed': 'Voice speed',
 'settings.section_voice': 'VOICE SETTINGS',
 'settings.section_keys': 'PROVIDER API KEYS',
 'settings.section_messaging': 'MESSAGING CONNECTORS',
 'settings.telegram_token': 'Telegram Bot Token',
 'settings.telegram_chat_id': 'Telegram Chat ID',
 'settings.whatsapp_token': 'WhatsApp Business Token',
 'settings.whatsapp_phone_id': 'WhatsApp Phone Number ID',
 'settings.email_imap_host': 'IMAP Server',
 'settings.email_imap_user': 'Email user',
 'settings.email_imap_pass': 'Email password',
 'settings.email_smtp_host': 'SMTP Server',
 'settings.messaging_note': 'Configure messaging connectors to receive instructions via Telegram, WhatsApp or email.',

 // Agents & Models
 'agents.models_title': 'Models & Pricing',
 'agents.th_model': 'Model',
 'agents.th_input': 'Input $/M',
 'agents.th_output': 'Output $/M',
 'agents.th_context': 'Context',
 'agents.th_tags': 'Tags',
 'agents.refresh_models': '🔄 Refresh from API',
 'agents.refreshing': 'Refreshing...',
 'agents.only_configured': 'Only providers with configured API keys are shown',

 // Memory
 'memory.title': 'GLOBAL MEMORY',
 'memory.search_placeholder': 'Semantic search...',
 'memory.loading': 'Loading...',
 'memory.empty': 'No memories found',

 // Messaging
 'messaging.title': 'MESSAGING CENTER',
 'messaging.inbox': 'Inbox',
 'messaging.compose': 'New message',
 'messaging.channels': 'Active channels',
 'messaging.no_channels': 'No channels configured. Set up Telegram, WhatsApp or email in Settings.',
 'messaging.send': 'Send',
 'messaging.reply': 'Reply',
 'messaging.from': 'From',
 'messaging.to': 'To',
 'messaging.subject': 'Subject',
 'messaging.body': 'Message',
 'messaging.channel_telegram': 'Telegram',
 'messaging.channel_whatsapp': 'WhatsApp',
 'messaging.channel_email': 'Email',
 'messaging.status_connected': 'Connected',
 'messaging.status_disconnected': 'Disconnected',
 'messaging.instructions_received': 'instruction(s) received',

 // Footer
 'footer.sys': 'SYS',
 'footer.online': 'ONLINE',

 // Common
 'common.models': 'models',
 'common.free': 'free',
 },
};

let currentLocale: Locale = 'fr';

export function setLocale(locale: Locale): void {
 currentLocale = locale;
 try {
 localStorage.setItem('jarvis_locale', locale);
 } catch { /* ignore */ }
}

export function getLocale(): Locale {
 return currentLocale;
}

export function initLocale(): Locale {
 try {
 const stored = localStorage.getItem('jarvis_locale') as Locale | null;
 if (stored && (stored === 'fr' || stored === 'en')) {
 currentLocale = stored;
 }
 } catch { /* ignore */ }
 return currentLocale;
}

export function t(key: string): string {
 return TRANSLATIONS[currentLocale]?.[key] ?? TRANSLATIONS['fr']?.[key] ?? key;
}