import React, { useState } from 'react';
import ChatContainer from './components/ChatContainer';
import AnalyticsDashboard from './components/AnalyticsDashboard';

const App = () => {
  const [view, setView] = useState('chat');

  return (
    <div id="root">
      {/* --- Side Navigation (Instagram Rail) --- */}
      <nav className="side-nav">
        <div className="nav-logo" style={{ marginBottom: '20px' }}>
          {/* Logo Removed */}
        </div>
        
        <button 
          className={`nav-item ${view === 'chat' ? 'active' : ''}`}
          onClick={() => setView('chat')}
          title="Direct Messages"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
          </svg>
        </button>

        <button 
          className={`nav-item ${view === 'analytics' ? 'active' : ''}`}
          onClick={() => setView('analytics')}
          title="Analytics"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M18 20V10M12 20V4M6 20v-6"></path>
          </svg>
        </button>
      </nav>

      <div className="app-main-wrapper">
        <div className="app-container">
          <header className="app-header">
            <div className="brand">
              <h1>Smart Support AI</h1>
            </div>
            <div className="header-actions">
              <button className="action-btn" title="More options">
                 <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                   <circle cx="12" cy="12" r="1"></circle>
                   <circle cx="12" cy="5" r="1"></circle>
                   <circle cx="12" cy="19" r="1"></circle>
                 </svg>
              </button>
            </div>
          </header>
          
          <main className="chat-window">
            {view === 'chat' ? (
              <ChatContainer />
            ) : (
              <AnalyticsDashboard />
            )}
          </main>
        </div>
      </div>
    </div>
  );
};

export default App;
