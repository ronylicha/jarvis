import { useEffect, useState } from 'react';
import './App.css';

interface AgentStatus {
 name: string;
 provider: string;
 status: 'online' | 'offline' | 'busy';
 lastActive?: string;
}

const AGENTS: AgentStatus[] = [
 { name: 'Claude', provider: 'anthropic', status: 'online' },
 { name: 'Codex', provider: 'openai', status: 'online' },
 { name: 'Gemini', provider: 'google', status: 'offline' },
 { name: 'Kimi', provider: 'moonshot', status: 'offline' },
];

function WaveformVisualizer() {
 return (
 <div className="waveform-container">
 <div className="waveform-bar" style={{ animationDelay: '0s' }} />
 <div className="waveform-bar" style={{ animationDelay: '0.1s' }} />
 <div className="waveform-bar" style={{ animationDelay: '0.2s' }} />
 <div className="waveform-bar" style={{ animationDelay: '0.3s' }} />
 <div className="waveform-bar" style={{ animationDelay: '0.4s' }} />
 <div className="waveform-bar" style={{ animationDelay: '0.3s' }} />
 <div className="waveform-bar" style={{ animationDelay: '0.2s' }} />
 <div className="waveform-bar" style={{ animationDelay: '0.1s' }} />
 </div>
 );
}

function AgentPanel() {
 return (
 <div className="agent-panel">
 <h3 className="panel-title">AGENTS</h3>
 {AGENTS.map((agent) => (
 <div key={agent.name} className="agent-row">
 <span className={`status-dot status-${agent.status}`} />
 <span className="agent-name">{agent.name}</span>
 <span className="agent-provider">{agent.provider}</span>
 </div>
 ))}
 </div>
 );
}

function MemoryBrowser() {
 const [memories, setMemories] = useState<{ id: string; content: string; agent_id: string }[]>([]);
 const [loading, setLoading] = useState(false);

 useEffect(() => {
 async function loadRecent() {
 try {
 setLoading(true);
 const resp = await fetch('http://localhost:8004/recall', {
 method: 'POST',
 headers: { 'Content-Type': 'application/json' },
 body: JSON.stringify({ query: '', limit: 5 }),
 });
 if (resp.ok) {
 const data = await resp.json();
 setMemories(data.results || []);
 }
 } catch {
 // Memory service may not be running yet
 } finally {
 setLoading(false);
 }
 }
 loadRecent();
 }, []);

 return (
 <div className="memory-panel">
 <h3 className="panel-title">MEMORY</h3>
 {loading ? (
 <div className="memory-loading">Loading...</div>
 ) : memories.length === 0 ? (
 <div className="memory-empty">No memories stored yet</div>
 ) : (
 memories.map((m) => (
 <div key={m.id} className="memory-item">
 <span className="memory-agent">[{m.agent_id}]</span>
 <span className="memory-content">{m.content.slice(0, 80)}{m.content.length > 80 ? '...' : ''}</span>
 </div>
 ))
 )}
 </div>
 );
}

export default function App() {
 const [currentTime, setCurrentTime] = useState(new Date());

 useEffect(() => {
 const interval = setInterval(() => setCurrentTime(new Date()), 1000);
 return () => clearInterval(interval);
 }, []);

 return (
 <div className="jarvis-hud">
 {/* Top bar */}
 <header className="hud-header">
 <div className="hud-logo">◈ JARVIS</div>
 <div className="hud-clock">
 {currentTime.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
 </div>
 <div className="hud-date">
 {currentTime.toLocaleDateString('fr-FR', { weekday: 'long', day: 'numeric', month: 'long' })}
 </div>
 </header>

 {/* Main grid */}
 <main className="hud-grid">
 <section className="hud-left">
 <WaveformVisualizer />
 <AgentPanel />
 </section>

 <section className="hud-center">
 <div className="center-orb">
 <div className="orb-ring orb-ring-1" />
 <div className="orb-ring orb-ring-2" />
 <div className="orb-core" />
 </div>
 <div className="center-status">LISTENING</div>
 </section>

 <section className="hud-right">
 <MemoryBrowser />
 </section>
 </main>

 {/* Footer */}
 <footer className="hud-footer">
 <span>SYS: ONLINE</span>
 <span>STT: READY</span>
 <span>TTS: READY</span>
 <span>MEM: ACTIVE</span>
 </footer>
 </div>
 );
}