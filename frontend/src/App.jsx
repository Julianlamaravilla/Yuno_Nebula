import React, { useState, useEffect } from 'react';
import axios from 'axios';
import AlertCard from './components/AlertCard';
import MetricsChart from './components/MetricsChart';

function App() {
  const [alerts, setAlerts] = useState([]);
  const [totalRevenueAtRisk, setTotalRevenueAtRisk] = useState(0);
  const [loading, setLoading] = useState(true);
  const [lastUpdate, setLastUpdate] = useState(new Date());

  const fetchAlerts = async () => {
    try {
      const response = await axios.get('/api/alerts');
      const alertsData = response.data;

      setAlerts(alertsData);

      // Calculate total revenue at risk
      const total = alertsData.reduce((sum, alert) => {
        return sum + (alert.revenue_at_risk_usd || 0);
      }, 0);
      setTotalRevenueAtRisk(total);

      setLastUpdate(new Date());
      setLoading(false);
    } catch (error) {
      console.error('Error fetching alerts:', error);
      // Use mock data for development
      setAlerts(getMockAlerts());
      setTotalRevenueAtRisk(12450.75);
      setLoading(false);
    }
  };

  const getMockAlerts = () => {
    return [
      {
        alert_id: '1',
        title: 'STRIPE MX - BBVA Timeout Spike',
        severity: 'CRITICAL',
        confidence_score: 0.92,
        revenue_at_risk_usd: 8750.25,
        affected_transactions: 124,
        created_at: new Date().toISOString(),
        llm_explanation: 'Critical anomaly detected: Stripe Mexico is experiencing 78% timeout rate specifically for BBVA-issued cards. This appears to be an issuer-specific connectivity issue affecting high-value transactions. Immediate action required to prevent SLA breach.',
        root_cause: {
          provider: 'STRIPE',
          scope: 'Issuer-Specific (BBVA)',
          issue: 'TIMEOUT'
        },
        suggested_action: {
          label: 'Switch to DLOCAL for BBVA cards',
          action_type: 'FAILOVER_PROVIDER'
        }
      },
      {
        alert_id: '2',
        title: 'Unusual Decline Rate - merchant_shopito',
        severity: 'WARNING',
        confidence_score: 0.85,
        revenue_at_risk_usd: 3700.50,
        affected_transactions: 67,
        created_at: new Date(Date.now() - 120000).toISOString(),
        llm_explanation: 'Decline rate for merchant_shopito has increased by 35% above baseline. Analysis shows concentration of INSUFFICIENT_FUNDS responses, suggesting potential fraud prevention overreaction or legitimate customer payment method issues.',
        root_cause: {
          provider: 'ADYEN',
          scope: 'Merchant-Wide',
          issue: 'INSUFFICIENT_FUNDS'
        },
        suggested_action: {
          label: 'Review fraud rules configuration',
          action_type: 'TUNE_RULES'
        }
      }
    ];
  };

  useEffect(() => {
    fetchAlerts();
    const interval = setInterval(fetchAlerts, 5000); // Auto-refresh every 5 seconds
    return () => clearInterval(interval);
  }, []);

  const getAlertCountBySeverity = (severity) => {
    return alerts.filter(alert => alert.severity === severity).length;
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-900">
        <div className="text-center">
          <div className="animate-spin rounded-full h-16 w-16 border-b-2 border-blue-500 mx-auto mb-4"></div>
          <p className="text-gray-400 text-lg">Loading Yuno Sentinel Dashboard...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-900">
      {/* Header */}
      <header className="bg-gray-800 border-b border-gray-700 shadow-lg">
        <div className="max-w-7xl mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold text-white flex items-center gap-2">
                🛡️ Yuno Sentinel
              </h1>
              <p className="text-sm text-gray-400 mt-1">
                Real-time Financial Observability & Self-Healing Platform
              </p>
            </div>
            <div className="text-right">
              <div className="text-xs text-gray-500">Last updated</div>
              <div className="text-sm text-gray-300">
                {lastUpdate.toLocaleTimeString()}
              </div>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-8">
        {/* KPI Section */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
          {/* Revenue at Risk - LARGE and RED */}
          <div className="md:col-span-2 bg-gradient-to-br from-red-900 to-red-800 border-2 border-red-500 rounded-lg p-6 shadow-2xl">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-sm font-semibold text-red-200 uppercase tracking-wide mb-2">
                  💰 Revenue at Risk
                </h3>
                <div className="text-5xl font-black text-white mb-1">
                  ${totalRevenueAtRisk.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                </div>
                <p className="text-xs text-red-200">
                  Across {alerts.length} active {alerts.length === 1 ? 'alert' : 'alerts'}
                </p>
              </div>
              <div className="text-6xl">🚨</div>
            </div>
          </div>

          {/* Active Alerts */}
          <div className="bg-gray-800 border border-gray-700 rounded-lg p-6 shadow-lg">
            <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wide mb-2">
              Active Alerts
            </h3>
            <div className="text-4xl font-bold text-white mb-1">
              {alerts.length}
            </div>
            <div className="flex gap-3 text-xs mt-2">
              <span className="text-red-400">
                🔴 {getAlertCountBySeverity('CRITICAL')} Critical
              </span>
              <span className="text-yellow-400">
                🟡 {getAlertCountBySeverity('WARNING')} Warning
              </span>
            </div>
          </div>

          {/* System Health */}
          <div className="bg-gray-800 border border-gray-700 rounded-lg p-6 shadow-lg">
            <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wide mb-2">
              System Health
            </h3>
            <div className="text-4xl font-bold text-green-400 mb-1">
              {alerts.length === 0 ? '100%' : alerts.some(a => a.severity === 'CRITICAL') ? '45%' : '78%'}
            </div>
            <div className="flex items-center gap-2 text-xs mt-2">
              <div className={`w-2 h-2 rounded-full ${alerts.some(a => a.severity === 'CRITICAL') ? 'bg-red-500 animate-pulse' : 'bg-green-500'}`}></div>
              <span className="text-gray-400">
                {alerts.some(a => a.severity === 'CRITICAL') ? 'Degraded' : 'Operational'}
              </span>
            </div>
          </div>
        </div>

        {/* Metrics Chart */}
        <div className="mb-8">
          <MetricsChart />
        </div>

        {/* Alerts Feed */}
        <div>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-2xl font-bold text-white">🚨 Alert Feed</h2>
            <div className="text-sm text-gray-400">
              {alerts.length === 0 ? 'No active alerts' : `${alerts.length} ${alerts.length === 1 ? 'alert' : 'alerts'} requiring attention`}
            </div>
          </div>

          {alerts.length === 0 ? (
            <div className="bg-gray-800 border border-gray-700 rounded-lg p-12 text-center">
              <div className="text-6xl mb-4">✅</div>
              <h3 className="text-xl font-bold text-green-400 mb-2">All Systems Operational</h3>
              <p className="text-gray-400">No anomalies detected in the last 15 minutes</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {alerts.map((alert) => (
                <AlertCard key={alert.alert_id} alert={alert} />
              ))}
            </div>
          )}
        </div>
      </main>

      {/* Footer */}
      <footer className="bg-gray-800 border-t border-gray-700 mt-12">
        <div className="max-w-7xl mx-auto px-6 py-4 text-center text-xs text-gray-500">
          <p>Yuno Sentinel - Powered by Gemini AI | Auto-refreshing every 5 seconds</p>
        </div>
      </footer>
    </div>
  );
}

export default App;
