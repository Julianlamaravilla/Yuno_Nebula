import React, { useState, useEffect } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import axios from 'axios';

const MetricsChart = () => {
  const [metricsData, setMetricsData] = useState([]);
  const [loading, setLoading] = useState(true);

  const fetchMetrics = async () => {
    try {
      // Fetch recent events to calculate approval rate over time
      const response = await axios.get('/api/metrics/recent');

      // Transform data to approval rate per minute
      const transformedData = response.data.map(metric => ({
        time: new Date(metric.timestamp).toLocaleTimeString('en-US', {
          hour: '2-digit',
          minute: '2-digit'
        }),
        approvalRate: parseFloat(metric.approval_rate.toFixed(2)),
        errorRate: parseFloat(metric.error_rate.toFixed(2)),
        totalTransactions: metric.total_count
      }));

      setMetricsData(transformedData.slice(-20)); // Keep last 20 data points
      setLoading(false);
    } catch (error) {
      console.error('Error fetching metrics:', error);
      // Use mock data for development
      setMetricsData(generateMockData());
      setLoading(false);
    }
  };

  const generateMockData = () => {
    const data = [];
    const now = new Date();

    for (let i = 19; i >= 0; i--) {
      const timestamp = new Date(now - i * 60000);
      const time = timestamp.toLocaleTimeString('en-US', {
        hour: '2-digit',
        minute: '2-digit'
      });

      // Simulate healthy rate then drop (chaos injection effect)
      let approvalRate = 95 + Math.random() * 3;
      if (i < 5) {
        // Recent chaos - dramatic drop
        approvalRate = 45 + Math.random() * 15;
      }

      data.push({
        time,
        approvalRate: parseFloat(approvalRate.toFixed(2)),
        errorRate: parseFloat((100 - approvalRate).toFixed(2)),
        totalTransactions: Math.floor(500 + Math.random() * 200)
      });
    }

    return data;
  };

  useEffect(() => {
    fetchMetrics();
    const interval = setInterval(fetchMetrics, 5000); // Refresh every 5 seconds
    return () => clearInterval(interval);
  }, []);

  const CustomTooltip = ({ active, payload }) => {
    if (active && payload && payload.length) {
      return (
        <div className="bg-gray-900 border border-gray-700 p-3 rounded shadow-lg">
          <p className="text-gray-300 text-sm font-semibold">{payload[0].payload.time}</p>
          <p className="text-green-400 text-sm">
            Approval Rate: <span className="font-bold">{payload[0].value}%</span>
          </p>
          <p className="text-red-400 text-sm">
            Error Rate: <span className="font-bold">{payload[0].payload.errorRate}%</span>
          </p>
          <p className="text-gray-400 text-xs mt-1">
            Transactions: {payload[0].payload.totalTransactions}
          </p>
        </div>
      );
    }
    return null;
  };

  if (loading) {
    return (
      <div className="bg-gray-800 border border-gray-700 rounded-lg p-6 flex items-center justify-center">
        <div className="text-gray-400 animate-pulse">Loading metrics...</div>
      </div>
    );
  }

  return (
    <div className="bg-gray-800 border border-gray-700 rounded-lg p-6 shadow-lg">
      <h2 className="text-xl font-bold text-white mb-4">📊 Approval Rate Timeline</h2>
      <p className="text-xs text-gray-400 mb-4">
        Real-time health monitoring - Watch for dramatic drops during chaos injection
      </p>

      <ResponsiveContainer width="100%" height={300}>
        <LineChart data={metricsData}>
          <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
          <XAxis
            dataKey="time"
            stroke="#9CA3AF"
            style={{ fontSize: '12px' }}
          />
          <YAxis
            stroke="#9CA3AF"
            style={{ fontSize: '12px' }}
            domain={[0, 100]}
            label={{ value: 'Approval Rate (%)', angle: -90, position: 'insideLeft', style: { fill: '#9CA3AF' } }}
          />
          <Tooltip content={<CustomTooltip />} />
          <Legend
            wrapperStyle={{ color: '#9CA3AF', fontSize: '12px' }}
          />
          <Line
            type="monotone"
            dataKey="approvalRate"
            stroke="#10B981"
            strokeWidth={3}
            name="Approval Rate"
            dot={{ fill: '#10B981', r: 4 }}
            activeDot={{ r: 6 }}
          />
        </LineChart>
      </ResponsiveContainer>

      <div className="mt-4 grid grid-cols-3 gap-4 text-center">
        <div className="bg-gray-900 p-3 rounded">
          <div className="text-2xl font-bold text-green-400">
            {metricsData.length > 0 ? metricsData[metricsData.length - 1].approvalRate : 0}%
          </div>
          <div className="text-xs text-gray-400">Current Rate</div>
        </div>
        <div className="bg-gray-900 p-3 rounded">
          <div className="text-2xl font-bold text-red-400">
            {metricsData.length > 0 ? metricsData[metricsData.length - 1].errorRate : 0}%
          </div>
          <div className="text-xs text-gray-400">Error Rate</div>
        </div>
        <div className="bg-gray-900 p-3 rounded">
          <div className="text-2xl font-bold text-blue-400">
            {metricsData.length > 0 ? metricsData[metricsData.length - 1].totalTransactions : 0}
          </div>
          <div className="text-xs text-gray-400">Transactions/min</div>
        </div>
      </div>
    </div>
  );
};

export default MetricsChart;
