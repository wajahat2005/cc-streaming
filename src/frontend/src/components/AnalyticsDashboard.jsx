import React, { useState, useEffect } from 'react';
import { 
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell, 
  PieChart, Pie, LineChart, Line 
} from 'recharts';
import { fetchAnalytics } from '../services/api';

/**
 * 📊 AnalyticsDashboard: Instagram-Style Telemetry.
 */
const AnalyticsDashboard = () => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const response = await fetchAnalytics();
        setData(response);
      } catch (err) {
        setError(err.message || 'System Offline');
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  if (loading) return <div className="chat-window"><div className="empty-state">SYNCING...</div></div>;
  if (error) return <div className="chat-window"><div className="empty-state">{error}</div></div>;
  if (!data || data.total === 0) return <div className="chat-window"><div className="empty-state">NO SYSTEM TELEMETRY YET.</div></div>;

  // Formatting data for Recharts
  const barData = Object.keys(data.intents).map(key => ({
    name: key.split('_').map(w => w[0].toUpperCase()).join(''), 
    fullName: key.replace('_', ' '),
    count: data.intents[key]
  }));

  const pieData = Object.keys(data.intents).map(key => ({
    name: key,
    value: data.intents[key]
  }));

  const timelineData = (data.timeline || []).map((p, i) => ({
    index: i,
    sentiment: (p.s * 100).toFixed(0)
  }));

  const COLORS = ['#0095f6', '#3b82f6', '#10b981', '#f59e0b', '#ed4956', '#8b5cf6'];

  return (
    <div className="chat-window" style={{ overflowY: 'auto', background: 'var(--bg-pure)' }}>
      <div className="dashboard-header" style={{ padding: '24px 20px 0' }}>
        <h2 style={{ fontSize: '1.2rem', fontWeight: 700, color: 'var(--text-primary)', margin: 0 }}>Analytics</h2>
        <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginTop: '4px' }}>System performance and user engagement</p>
      </div>

      <div className="metrics-container" style={{ padding: '20px' }}>
        <div className="stat-card">
          <span className="stat-val">{data.total}</span>
          <span className="stat-label">Total Messages</span>
        </div>
        <div className="stat-card">
          <span className="stat-val" style={{ color: '#10b981' }}>{(data.accuracy * 100).toFixed(0)}%</span>
          <span className="stat-label">Accuracy</span>
        </div>
        <div className="stat-card">
          <span className="stat-val" style={{ color: 'var(--primary)' }}>{data.avg_sentiment}</span>
          <span className="stat-label">Sentiment</span>
        </div>
        <div className="stat-card">
          <span className="stat-val" style={{ color: data.escalations > 0 ? '#ed4956' : 'var(--text-secondary)' }}>{data.escalations}</span>
          <span className="stat-label">Escalations</span>
        </div>
      </div>

      <div style={{ padding: '0 20px 24px', display: 'flex', flexDirection: 'column', gap: '20px' }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '20px' }}>
          <div className="stat-card" style={{ padding: '20px', minHeight: '260px' }}>
            <h4 style={{ fontSize: '0.7rem', color: 'var(--text-dim)', textTransform: 'uppercase', marginBottom: '16px', letterSpacing: '0.1em' }}>Intent Distribution</h4>
            <ResponsiveContainer width="100%" height="80%">
              <PieChart>
                <Pie data={pieData} innerRadius={60} outerRadius={80} paddingAngle={5} dataKey="value" stroke="none">
                  {pieData.map((entry, index) => <Cell key={index} fill={COLORS[index % COLORS.length]} />)}
                </Pie>
                <Tooltip 
                  contentStyle={{ backgroundColor: '#121212', border: '1px solid #363636', borderRadius: '8px', fontSize: '0.7rem', color: '#fff' }} 
                  itemStyle={{ color: '#fff' }}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>

          <div className="stat-card" style={{ padding: '20px', minHeight: '260px' }}>
            <h4 style={{ fontSize: '0.7rem', color: 'var(--text-dim)', textTransform: 'uppercase', marginBottom: '16px', letterSpacing: '0.1em' }}>Satisfaction Trend</h4>
            <ResponsiveContainer width="100%" height="80%">
              <LineChart data={timelineData}>
                <Tooltip 
                  contentStyle={{ backgroundColor: '#121212', border: '1px solid #363636', borderRadius: '8px', fontSize: '0.7rem' }}
                  itemStyle={{ color: '#fff' }}
                />
                <Line type="monotone" dataKey="sentiment" stroke="var(--primary)" strokeWidth={3} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="stat-card" style={{ padding: '24px' }}>
          <h4 style={{ fontSize: '0.7rem', color: 'var(--text-dim)', textTransform: 'uppercase', marginBottom: '20px', letterSpacing: '0.1em' }}>Neural Stability (By Intent)</h4>
          <div style={{ height: '200px' }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={barData}>
                <XAxis dataKey="name" axisLine={false} tickLine={false} style={{ fontSize: '0.6rem', fill: 'var(--text-dim)' }} />
                <Tooltip 
                  cursor={{ fill: 'rgba(255, 255, 255, 0.05)' }} 
                  contentStyle={{ backgroundColor: '#121212', border: '1px solid #363636', borderRadius: '8px', fontSize: '0.7rem' }}
                  itemStyle={{ color: '#fff' }}
                />
                <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                  {barData.map((entry, index) => <Cell key={index} fill={COLORS[index % COLORS.length]} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
    </div>
  );
};

export default AnalyticsDashboard;
