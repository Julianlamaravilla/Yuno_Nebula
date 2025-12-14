import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Shield, DollarSign, AlertTriangle, CheckCircle2, Activity, RefreshCw } from 'lucide-react';
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
      const alertsData = response.data.alerts || response.data;

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
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAlerts();
    const interval = setInterval(fetchAlerts, 5000);
    return () => clearInterval(interval);
  }, []);

  const getAlertCountBySeverity = (severity) => {
    return alerts.filter(alert => alert.severity === severity).length;
  };

  const criticalCount = getAlertCountBySeverity('CRITICAL');
  const warningCount = getAlertCountBySeverity('WARNING');
  const healthScore = alerts.length === 0 ? 100 : Math.max(0, 100 - (criticalCount * 20 + warningCount * 10));

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#0a0e1a]">
        <div className="text-center">
          <Activity size={40} className="text-blue-500 animate-pulse mx-auto mb-4" />
          <p className="text-gray-400 text-sm font-medium">Initializing Sentinel...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#0a0e1a]">
      {/* Header */}
      <header className="bg-gray-900 border-b border-gray-800">
        <div className="max-w-7xl mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Shield size={28} className="text-blue-500" />
              <div>
                <h1 className="text-xl font-semibold text-gray-100">Yuno Sentinel</h1>
                <p className="text-xs text-gray-500">Real-time Financial Observability Platform</p>
              </div>
            </div>
            <div className="flex items-center gap-4">
              <div className="text-right">
                <div className="text-xs text-gray-500">Last updated</div>
                <div className="text-sm text-gray-300 font-medium tabular-nums flex items-center gap-1.5">
                  <RefreshCw size={12} className="text-gray-500" />
                  {lastUpdate.toLocaleTimeString('en-US', {
                    hour: '2-digit',
                    minute: '2-digit',
                    second: '2-digit'
                  })}
                </div>
              </div>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-8">
        {/* KPI Section */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-5 mb-8">
          {/* Revenue at Risk - Prominent */}
          <div className="md:col-span-2 bg-gradient-to-br from-red-950/30 to-red-900/20 border border-red-900/50 rounded-lg p-6 shadow-sm">
            <div className="flex items-start justify-between">
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-2">
                  <DollarSign size={18} className="text-red-400" />
                  <h3 className="text-xs font-medium text-red-300 uppercase tracking-wide">
                    Revenue at Risk
                  </h3>
                </div>
                <div className="text-4xl font-bold text-red-400 tabular-nums mb-1">
                  ${totalRevenueAtRisk.toLocaleString('en-US', {
                    minimumFractionDigits: 2,
                    maximumFractionDigits: 2
                  })}
                </div>
                <p className="text-xs text-red-300/70">
                  {alerts.length} active {alerts.length === 1 ? 'incident' : 'incidents'}
                </p>
              </div>
            </div>
          </div>

          {/* Active Alerts */}
          <div className="bg-gray-900 border border-gray-800 rounded-lg p-5 shadow-sm">
            <div className="flex items-center gap-2 mb-2">
              <AlertTriangle size={16} className="text-gray-500" />
              <h3 className="text-xs font-medium text-gray-400 uppercase tracking-wide">
                Active Alerts
              </h3>
            </div>
            <div className="text-3xl font-bold text-gray-100 tabular-nums mb-2">
              {alerts.length}
            </div>
            <div className="flex flex-col gap-1 text-xs">
              {criticalCount > 0 && (
                <div className="flex items-center gap-1.5">
                  <div className="w-1.5 h-1.5 rounded-full bg-red-500" />
                  <span className="text-red-400 font-medium">{criticalCount} Critical</span>
                </div>
              )}
              {warningCount > 0 && (
                <div className="flex items-center gap-1.5">
                  <div className="w-1.5 h-1.5 rounded-full bg-yellow-500" />
                  <span className="text-yellow-400 font-medium">{warningCount} Warning</span>
                </div>
              )}
              {alerts.length === 0 && (
                <span className="text-gray-500">No incidents</span>
              )}
            </div>
          </div>

          {/* System Health */}
          <div className="bg-gray-900 border border-gray-800 rounded-lg p-5 shadow-sm">
            <div className="flex items-center gap-2 mb-2">
              <Activity size={16} className="text-gray-500" />
              <h3 className="text-xs font-medium text-gray-400 uppercase tracking-wide">
                System Health
              </h3>
            </div>
            <div className={`text-3xl font-bold tabular-nums mb-2 ${
              healthScore >= 80 ? 'text-green-400' :
              healthScore >= 60 ? 'text-yellow-400' : 'text-red-400'
            }`}>
              {healthScore}%
            </div>
            <div className="flex items-center gap-2">
              <div className={`w-1.5 h-1.5 rounded-full ${
                healthScore >= 80 ? 'bg-green-500' :
                healthScore >= 60 ? 'bg-yellow-500' : 'bg-red-500 animate-pulse'
              }`} />
              <span className="text-xs text-gray-500">
                {healthScore >= 80 ? 'Operational' :
                 healthScore >= 60 ? 'Degraded' : 'Critical'}
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
          <div className="flex items-center justify-between mb-5">
            <h2 className="text-lg font-semibold text-gray-100 flex items-center gap-2">
              <AlertTriangle size={20} />
              Alert Feed
            </h2>
            <div className="text-sm text-gray-500">
              {alerts.length === 0 ? (
                <span className="flex items-center gap-1.5">
                  <CheckCircle2 size={14} className="text-green-500" />
                  No active incidents
                </span>
              ) : (
                `${alerts.length} ${alerts.length === 1 ? 'alert' : 'alerts'} requiring attention`
              )}
            </div>
          </div>

          {alerts.length === 0 ? (
            <div className="bg-gray-900 border border-gray-800 rounded-lg p-12 text-center">
              <CheckCircle2 size={48} className="text-green-500/50 mx-auto mb-4" />
              <h3 className="text-lg font-semibold text-green-400 mb-2">All Systems Operational</h3>
              <p className="text-sm text-gray-500">No anomalies detected in recent monitoring window</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
              {alerts.map((alert) => (
                <AlertCard key={alert.alert_id} alert={alert} />
              ))}
            </div>
          )}
        </div>
      </main>

      {/* Footer */}
      <footer className="bg-gray-900 border-t border-gray-800 mt-12">
        <div className="max-w-7xl mx-auto px-6 py-4 text-center">
          <p className="text-xs text-gray-600">
            Yuno Sentinel v1.0 · Powered by Gemini AI · Auto-refresh: 5s
          </p>
        </div>
      </footer>
    </div>
  );
}

export default App;
