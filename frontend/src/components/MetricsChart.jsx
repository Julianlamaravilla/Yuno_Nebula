import React, { useState, useEffect } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { TrendingDown, Activity, AlertCircle } from 'lucide-react';
import axios from 'axios';

const MetricsChart = () => {
  const [metricsData, setMetricsData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchMetrics = async () => {
    try {
      const response = await axios.get('/api/metrics/recent', {
        params: { minutes: 30 }
      });

      // AHORA SÍ: response.data es un Array real del backend
      if (Array.isArray(response.data) && response.data.length > 0) {
        const transformedData = response.data.map(metric => ({
          time: new Date(metric.timestamp).toLocaleTimeString('en-US', {
            hour: '2-digit',
            minute: '2-digit'
          }),
          approvalRate: parseFloat(metric.approval_rate.toFixed(2)),
          errorRate: parseFloat(metric.error_rate.toFixed(2)),
          totalTransactions: metric.total_count
        }));

        setMetricsData(transformedData);
        setError(null);
      } else {
        setMetricsData([]); // Datos vacíos pero válidos
      }
      setLoading(false);
    } catch (err) {
      console.error('Error fetching metrics:', err);
      setError(err.message);
      setMetricsData([]);
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchMetrics();
    const interval = setInterval(fetchMetrics, 5000);
    return () => clearInterval(interval);
  }, []);

  const CustomTooltip = ({ active, payload }) => {
    if (active && payload && payload.length) {
      return (
        <div className="bg-gray-900 border border-gray-700 p-3 rounded-md shadow-xl">
          <p className="text-gray-300 text-xs font-medium mb-1.5">{payload[0].payload.time}</p>
          <p className="text-green-400 text-sm font-semibold">
            Approval Rate: {payload[0].value}%
          </p>
          <p className="text-red-400 text-sm font-semibold">
            Error Rate: {payload[0].payload.errorRate}%
          </p>
          <p className="text-gray-400 text-xs mt-1.5">
            {payload[0].payload.totalTransactions} transactions
          </p>
        </div>
      );
    }
    return null;
  };

  if (loading) {
    return (
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-6 flex items-center justify-center min-h-[400px]">
        <div className="flex flex-col items-center gap-3">
          <Activity size={24} className="text-gray-600 animate-pulse" />
          <div className="text-gray-500 text-sm">Loading metrics...</div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-6 min-h-[400px]">
        <h2 className="text-lg font-semibold text-gray-100 mb-4 flex items-center gap-2">
          <TrendingDown size={20} />
          Approval Rate Timeline
        </h2>
        <div className="flex flex-col items-center justify-center h-64 gap-3">
          <AlertCircle size={32} className="text-red-500/50" />
          <p className="text-sm text-gray-500">Failed to load metrics data</p>
          <p className="text-xs text-gray-600">{error}</p>
        </div>
      </div>
    );
  }

  if (metricsData.length === 0) {
    return (
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-6 min-h-[400px]">
        <h2 className="text-lg font-semibold text-gray-100 mb-4 flex items-center gap-2">
          <TrendingDown size={20} />
          Approval Rate Timeline
        </h2>
        <div className="flex flex-col items-center justify-center h-64 gap-3">
          <Activity size={32} className="text-gray-600" />
          <p className="text-sm text-gray-500">No metrics data available</p>
          <p className="text-xs text-gray-600">Waiting for transaction data...</p>
        </div>
      </div>
    );
  }

  const latestMetric = metricsData[metricsData.length - 1] || {};
  const healthStatus = latestMetric.approvalRate >= 85 ? 'healthy' : latestMetric.approvalRate >= 70 ? 'degraded' : 'critical';

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-6 shadow-sm">
      <div className="flex items-center justify-between mb-5">
        <h2 className="text-lg font-semibold text-gray-100 flex items-center gap-2">
          <TrendingDown size={20} />
          Approval Rate Timeline
        </h2>
        <div className="flex items-center gap-2">
          <div className={`w-2 h-2 rounded-full ${healthStatus === 'healthy' ? 'bg-green-500' :
              healthStatus === 'degraded' ? 'bg-yellow-500' : 'bg-red-500 animate-pulse'
            }`} />
          <span className="text-xs text-gray-500 capitalize">{healthStatus}</span>
        </div>
      </div>

      <ResponsiveContainer width="100%" height={280}>
        <LineChart data={metricsData}>
          <CartesianGrid strokeDasharray="3 3" stroke="#374151" vertical={false} />
          <XAxis
            dataKey="time"
            stroke="#6b7280"
            style={{ fontSize: '11px', fontFamily: 'Inter' }}
            tickLine={false}
          />
          <YAxis
            stroke="#6b7280"
            style={{ fontSize: '11px', fontFamily: 'Inter' }}
            domain={[0, 100]}
            tickLine={false}
            label={{
              value: 'Approval Rate (%)',
              angle: -90,
              position: 'insideLeft',
              style: { fill: '#6b7280', fontSize: '11px', fontFamily: 'Inter' }
            }}
          />
          <Tooltip content={<CustomTooltip />} />
          <Line
            type="monotone"
            dataKey="approvalRate"
            stroke="#10b981"
            strokeWidth={2}
            dot={false}
            activeDot={{ r: 4, fill: '#10b981' }}
          />
        </LineChart>
      </ResponsiveContainer>

      {/* Stats Row */}
      <div className="mt-5 grid grid-cols-3 gap-4">
        <div className="bg-gray-950/50 p-3 rounded-md border border-gray-800">
          <div className="text-xs text-gray-500 mb-1">Current Rate</div>
          <div className="text-xl font-bold text-green-400 tabular-nums">
            {latestMetric.approvalRate || 0}%
          </div>
        </div>
        <div className="bg-gray-950/50 p-3 rounded-md border border-gray-800">
          <div className="text-xs text-gray-500 mb-1">Error Rate</div>
          <div className="text-xl font-bold text-red-400 tabular-nums">
            {latestMetric.errorRate || 0}%
          </div>
        </div>
        <div className="bg-gray-950/50 p-3 rounded-md border border-gray-800">
          <div className="text-xs text-gray-500 mb-1">Transactions/min</div>
          <div className="text-xl font-bold text-blue-400 tabular-nums">
            {latestMetric.totalTransactions || 0}
          </div>
        </div>
      </div>
    </div>
  );
};

export default MetricsChart;
