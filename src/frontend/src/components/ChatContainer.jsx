import React, { useState, useRef, useEffect, useCallback } from 'react';
import { sendMessageToBot, fetchHealth } from '../services/api';

/**
 * 💬 ChatContainer: Instagram DM Style Interaction Hub.
 */
const ChatContainer = () => {
  const createUserId = () => {
    if (window.crypto?.randomUUID) {
      return `user_${window.crypto.randomUUID()}`;
    }
    return `user_${Date.now()}`;
  };

  const [messages, setMessages] = useState([]);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [error, setError] = useState(null);
  const [language, setLanguage] = useState('en');
  const [systemStatus, setSystemStatus] = useState('checking');

  const messagesEndRef = useRef(null);
  const userIdRef = useRef(localStorage.getItem('chatbot_user_id') || createUserId());

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading]);

  useEffect(() => {
    localStorage.setItem('chatbot_user_id', userIdRef.current);
  }, []);

  useEffect(() => {
    let mounted = true;
    const loadHealth = async () => {
      try {
        const health = await fetchHealth();
        if (mounted) {
          setSystemStatus(health.status === 'online' ? 'online' : 'degraded');
        }
      } catch {
        if (mounted) {
          setSystemStatus('offline');
        }
      }
    };
    loadHealth();
    const timer = setInterval(loadHealth, 15000);
    return () => {
      mounted = false;
      clearInterval(timer);
    };
  }, []);

  const handleSend = useCallback(async (forcedMessage = null) => {
    const textToSend = forcedMessage || inputValue.trim();
    if (!textToSend || isLoading) return;

    const timestamp = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    setMessages(prev => [...prev, { text: textToSend, isBot: false, timestamp }]);
    setInputValue('');
    setIsLoading(true);
    setError(null);

    try {
      const data = await sendMessageToBot(textToSend, userIdRef.current, language);
      const botTimestamp = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
      
      setMessages(prev => [...prev, { 
        text: data.response, 
        isBot: true, 
        timestamp: botTimestamp,
        escalated: data.escalated || data.intent === 'escalation',
        is_discovery: data.is_discovery,
        metadata: {
          intent: data.intent,
          confidence: data.confidence,
          debug: data.debug
        }
      }]);
    } catch (err) {
      const botTimestamp = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
      setMessages(prev => [...prev, {
        text: err.message || "System Offline. I'm currently unable to process queries.",
        isBot: true,
        timestamp: botTimestamp,
        metadata: { intent: "system_error" }
      }]);
      setSystemStatus('offline');
      setError("Connectivity issue. Ensure backend services are active.");
    } finally {
      setIsLoading(false);
    }
  }, [inputValue, isLoading, language]);

  const toggleListening = () => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) return;
    if (isListening) {
      setIsListening(false);
      return;
    }
    const recognition = new SpeechRecognition();
    recognition.lang = language === 'en' ? 'en-US' : (language === 'ur' ? 'ur-PK' : 'es-ES');
    recognition.onstart = () => setIsListening(true);
    recognition.onend = () => setIsListening(false);
    recognition.onerror = () => setIsListening(false);
    recognition.onresult = (event) => {
      const transcript = event.results[0][0].transcript;
      if (transcript) handleSend(transcript);
    };
    recognition.start();
  };

  return (
    <div className="chat-window">
      <div className="chat-messages">
        {messages.length === 0 && (
          <div className="empty-state" style={{ textAlign: 'center', marginTop: '60px' }}>
             <div style={{ width: '96px', height: '96px', border: '2px solid var(--border)', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 16px' }}>
                <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1">
                   <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
                </svg>
             </div>
             <h2 style={{ fontSize: '1.2rem', fontWeight: '600' }}>Your Messages</h2>
             <p style={{ color: 'var(--text-secondary)', fontSize: '0.8rem', marginTop: '8px' }}>Send a query to start the conversation.</p>
          </div>
        )}
        
        {messages.map((msg, index) => (
          <div key={index} className={`message-row ${msg.isBot ? 'bot' : 'user'}`}>
            <div className="bubble">
              {msg.is_discovery && (
                <div className="discovery-badge">
                   <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
                      <circle cx="11" cy="11" r="8"></circle>
                      <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
                   </svg>
                   Discovery
                </div>
              )}
              {msg.text}
              {msg.isBot && msg.metadata && (
                <div className="message-meta-info">
                   <span className="meta-intent">{msg.metadata.intent}</span>
                   <span>•</span>
                   <span className="meta-conf">{Math.round(msg.metadata.confidence)}% match</span>
                </div>
              )}
              {msg.isBot && msg.escalated && (
                <div className="escalated-tag">Escalated to Agent</div>
              )}
            </div>
          </div>
        ))}

        {isLoading && (
          <div className="message-row bot">
            <div className="bubble" style={{ opacity: 0.6 }}>Typing...</div>
          </div>
        )}
        
        <div ref={messagesEndRef} />
      </div>

      <div className="interaction-bar">
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '12px' }}>
           <select 
            className="lang-select" 
            value={language} 
            onChange={(e) => setLanguage(e.target.value)}
            style={{ 
               background: 'transparent', 
               border: 'none', 
               color: 'var(--text-secondary)',
               fontSize: '0.7rem',
               cursor: 'pointer'
            }}
          >
            <option value="en">English 🇺🇸</option>
            <option value="ur">Urdu 🇵🇰</option>
            <option value="es">Spanish 🇪🇸</option>
          </select>
          <div className="status-indicator">
            <div className={`dot ${systemStatus === 'online' ? 'online' : ''}`}></div>
            <span style={{ fontSize: '0.65rem', color: 'var(--text-dim)' }}>
              {systemStatus === 'online' ? 'System Active' : 'System Degraded'}
            </span>
          </div>
        </div>

        {error && <div className="error-banner">{error}</div>}

        <form className="input-group" onSubmit={(e) => { e.preventDefault(); handleSend(); }}>
          <button 
            type="button" 
            className="action-btn" 
            onClick={toggleListening}
            style={{ color: isListening ? 'var(--primary)' : 'inherit' }}
          >
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"></path>
              <path d="M19 10v2a7 7 0 0 1-14 0v-2"></path>
              <line x1="12" y1="19" x2="12" y2="23"></line>
            </svg>
          </button>
          
          <input
            type="text"
            placeholder="Message..."
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            disabled={isLoading}
          />

          {inputValue.trim() ? (
            <button type="submit" className="action-btn btn-send" disabled={isLoading}>
              Send
            </button>
          ) : (
            <div style={{ display: 'flex', gap: '8px', paddingRight: '8px' }}>
               <button type="button" className="action-btn">
                  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
                    <circle cx="8.5" cy="8.5" r="1.5"></circle>
                    <polyline points="21 15 16 10 5 21"></polyline>
                  </svg>
               </button>
               <button type="button" className="action-btn">
                  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l8.84-8.84 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"></path>
                  </svg>
               </button>
            </div>
          )}
        </form>
      </div>
    </div>
  );
};

export default ChatContainer;
