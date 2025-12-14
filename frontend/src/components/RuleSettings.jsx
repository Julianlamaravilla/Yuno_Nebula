import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { X, Plus, Trash2, Clock, Filter, AlertCircle, RefreshCw } from 'lucide-react';

function RuleSettings({ isOpen, onClose }) {
  const [rules, setRules] = useState([]);
  const [loading, setLoading] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [formData, setFormData] = useState({
    merchant_id: '',
    rule_name: '',
    filter_country: '',
    filter_provider: '',
    filter_issuer: '',
    metric_type: 'APPROVAL_RATE',
    operator: '<',
    threshold_value: 0.95,
    min_transactions: 10,
    is_time_based: false,
    start_hour: 9,
    end_hour: 18,
    severity: 'WARNING'
  });

  useEffect(() => {
    if (isOpen) {
      fetchRules();
    }
  }, [isOpen]);

  const fetchRules = async () => {
    try {
      setLoading(true);
      const response = await axios.get('/api/rules');
      setRules(response.data);
    } catch (error) {
      console.error('Error fetching rules:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      const payload = {
        ...formData,
        merchant_id: formData.merchant_id || null,
        filter_country: formData.filter_country || null,
        filter_provider: formData.filter_provider || null,
        filter_issuer: formData.filter_issuer || null,
        threshold_value: parseFloat(formData.threshold_value)
      };

      await axios.post('/api/rules', payload);
      fetchRules();
      setShowForm(false);
      resetForm();
    } catch (error) {
      console.error('Error creating rule:', error);
      alert('Error creating rule: ' + (error.response?.data?.detail || error.message));
    }
  };

  const handleDelete = async (ruleId) => {
    if (!confirm('Are you sure you want to delete this rule?')) return;

    try {
      await axios.delete(`/api/rules/${ruleId}`);
      fetchRules();
    } catch (error) {
      console.error('Error deleting rule:', error);
      alert('Error deleting rule');
    }
  };

  const resetForm = () => {
    setFormData({
      merchant_id: '',
      rule_name: '',
      filter_country: '',
      filter_provider: '',
      filter_issuer: '',
      metric_type: 'APPROVAL_RATE',
      operator: '<',
      threshold_value: 0.95,
      min_transactions: 10,
      is_time_based: false,
      start_hour: 9,
      end_hour: 18,
      severity: 'WARNING'
    });
  };

  const formatThreshold = (type, value) => {
    if (type === 'TOTAL_VOLUME') return `${value} txns`;
    return `${(value * 100).toFixed(0)}%`;
  };

  const getMetricLabel = (type) => {
    const labels = {
      'APPROVAL_RATE': 'Approval Rate',
      'ERROR_RATE': 'Error Rate',
      'DECLINE_RATE': 'Decline Rate',
      'TOTAL_VOLUME': 'Total Volume'
    };
    return labels[type] || type;
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-5xl max-h-[90vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-blue-100">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-blue-50 flex items-center justify-center">
              <Filter size={20} className="text-blue-500" />
            </div>
            <div>
              <h2 className="text-xl font-semibold text-slate-800">Alert Rules Configuration</h2>
              <p className="text-xs text-slate-500 mt-0.5">Manage dynamic detection thresholds</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-slate-100 rounded-lg transition-colors"
          >
            <X size={20} className="text-slate-600" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {/* New Rule Button */}
          {!showForm && (
            <button
              onClick={() => setShowForm(true)}
              className="mb-6 w-full py-3 px-4 bg-blue-50 hover:bg-blue-100 border-2 border-dashed border-blue-300 rounded-lg text-blue-600 font-medium text-sm flex items-center justify-center gap-2 transition-colors"
            >
              <Plus size={18} />
              Create New Rule
            </button>
          )}

          {/* Form */}
          {showForm && (
            <form onSubmit={handleSubmit} className="mb-6 bg-blue-50 border border-blue-200 rounded-lg p-6">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
                <div className="md:col-span-2">
                  <label className="block text-xs font-medium text-slate-700 mb-1.5">Rule Name *</label>
                  <input
                    type="text"
                    required
                    value={formData.rule_name}
                    onChange={(e) => setFormData({ ...formData, rule_name: e.target.value })}
                    className="w-full px-3 py-2 border border-blue-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
                    placeholder="e.g., Peak Hours - Strict SLA"
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1.5">Merchant</label>
                  <select
                    value={formData.merchant_id}
                    onChange={(e) => setFormData({ ...formData, merchant_id: e.target.value })}
                    className="w-full px-3 py-2 border border-blue-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
                  >
                    <option value="">Global (All)</option>
                    <option value="merchant_shopito">Shopito</option>
                    <option value="merchant_techstore">TechStore</option>
                    <option value="merchant_fashionhub">FashionHub</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1.5">Country</label>
                  <select
                    value={formData.filter_country}
                    onChange={(e) => setFormData({ ...formData, filter_country: e.target.value })}
                    className="w-full px-3 py-2 border border-blue-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
                  >
                    <option value="">All Countries</option>
                    <option value="MX">Mexico (MX)</option>
                    <option value="CO">Colombia (CO)</option>
                    <option value="BR">Brazil (BR)</option>
                    <option value="AR">Argentina (AR)</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1.5">Provider</label>
                  <select
                    value={formData.filter_provider}
                    onChange={(e) => setFormData({ ...formData, filter_provider: e.target.value })}
                    className="w-full px-3 py-2 border border-blue-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
                  >
                    <option value="">All Providers</option>
                    <option value="STRIPE">Stripe</option>
                    <option value="DLOCAL">dLocal</option>
                    <option value="ADYEN">Adyen</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1.5">Issuer (Optional)</label>
                  <input
                    type="text"
                    value={formData.filter_issuer}
                    onChange={(e) => setFormData({ ...formData, filter_issuer: e.target.value })}
                    className="w-full px-3 py-2 border border-blue-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
                    placeholder="e.g., BBVA, Santander"
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1.5">Metric Type *</label>
                  <select
                    value={formData.metric_type}
                    onChange={(e) => setFormData({ ...formData, metric_type: e.target.value })}
                    className="w-full px-3 py-2 border border-blue-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
                  >
                    <option value="APPROVAL_RATE">Approval Rate (%)</option>
                    <option value="ERROR_RATE">Error Rate (%)</option>
                    <option value="DECLINE_RATE">Decline Rate (%)</option>
                    <option value="TOTAL_VOLUME">Total Volume (txns)</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1.5">Operator *</label>
                  <select
                    value={formData.operator}
                    onChange={(e) => setFormData({ ...formData, operator: e.target.value })}
                    className="w-full px-3 py-2 border border-blue-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
                  >
                    <option value="<">Less than (&lt;)</option>
                    <option value=">">Greater than (&gt;)</option>
                    <option value="<=">Less or equal (≤)</option>
                    <option value=">=">Greater or equal (≥)</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1.5">
                    Threshold Value * {formData.metric_type !== 'TOTAL_VOLUME' && '(0-1)'}
                  </label>
                  <input
                    type="number"
                    step={formData.metric_type === 'TOTAL_VOLUME' ? '1' : '0.01'}
                    min="0"
                    max={formData.metric_type === 'TOTAL_VOLUME' ? '10000' : '1'}
                    required
                    value={formData.threshold_value}
                    onChange={(e) => setFormData({ ...formData, threshold_value: e.target.value })}
                    className="w-full px-3 py-2 border border-blue-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1.5">Min Transactions</label>
                  <input
                    type="number"
                    min="1"
                    value={formData.min_transactions}
                    onChange={(e) => setFormData({ ...formData, min_transactions: parseInt(e.target.value) })}
                    className="w-full px-3 py-2 border border-blue-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1.5">Severity *</label>
                  <select
                    value={formData.severity}
                    onChange={(e) => setFormData({ ...formData, severity: e.target.value })}
                    className="w-full px-3 py-2 border border-blue-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
                  >
                    <option value="WARNING">⚠️ Warning</option>
                    <option value="CRITICAL">🔴 Critical</option>
                  </select>
                </div>

                <div className="md:col-span-2">
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={formData.is_time_based}
                      onChange={(e) => setFormData({ ...formData, is_time_based: e.target.checked })}
                      className="w-4 h-4 text-blue-500 rounded focus:ring-2 focus:ring-blue-400"
                    />
                    <span className="text-sm font-medium text-slate-700">Time-Based Rule (Active only during specific hours)</span>
                  </label>
                  <div className="mt-2 p-3 bg-amber-50 border border-amber-200 rounded-lg">
                    <div className="flex items-start gap-2">
                      <AlertCircle size={16} className="text-amber-600 mt-0.5 flex-shrink-0" />
                      <div className="text-xs text-amber-800">
                        <strong>⚠️ Timezone Warning:</strong> Hours use server time (UTC in Docker).
                        For demos, leave this OFF unless you're sure of server time.
                        Current server time: <strong className="font-mono">{new Date().toUTCString()}</strong>
                      </div>
                    </div>
                  </div>
                </div>

                {formData.is_time_based && (
                  <>
                    <div>
                      <label className="block text-xs font-medium text-slate-700 mb-1.5">Start Hour (0-23)</label>
                      <input
                        type="number"
                        min="0"
                        max="23"
                        value={formData.start_hour}
                        onChange={(e) => setFormData({ ...formData, start_hour: parseInt(e.target.value) })}
                        className="w-full px-3 py-2 border border-blue-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-slate-700 mb-1.5">End Hour (0-23)</label>
                      <input
                        type="number"
                        min="0"
                        max="23"
                        value={formData.end_hour}
                        onChange={(e) => setFormData({ ...formData, end_hour: parseInt(e.target.value) })}
                        className="w-full px-3 py-2 border border-blue-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
                      />
                    </div>
                  </>
                )}
              </div>

              <div className="flex gap-3">
                <button
                  type="submit"
                  className="flex-1 py-2.5 px-4 bg-blue-500 hover:bg-blue-600 text-white font-medium rounded-lg text-sm transition-colors"
                >
                  Create Rule
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setShowForm(false);
                    resetForm();
                  }}
                  className="px-4 py-2.5 border border-slate-300 hover:bg-slate-50 text-slate-700 font-medium rounded-lg text-sm transition-colors"
                >
                  Cancel
                </button>
              </div>
            </form>
          )}

          {/* Rules List */}
          <div>
            <h3 className="text-sm font-semibold text-slate-700 mb-3 flex items-center gap-2">
              <AlertCircle size={16} className="text-blue-400" />
              Active Rules ({rules.length})
            </h3>

            {loading ? (
              <div className="text-center py-8 text-slate-500 text-sm">Loading rules...</div>
            ) : rules.length === 0 ? (
              <div className="text-center py-12 border-2 border-dashed border-slate-200 rounded-lg">
                <AlertCircle size={40} className="text-slate-300 mx-auto mb-3" />
                <p className="text-slate-500 text-sm">No rules configured yet</p>
                <p className="text-slate-400 text-xs mt-1">Create your first rule to start monitoring</p>
              </div>
            ) : (
              <div className="space-y-3">
                {rules.map((rule) => (
                  <div key={rule.rule_id} className="bg-white border border-blue-100 rounded-lg p-4 hover:shadow-md transition-shadow">
                    <div className="flex items-start justify-between mb-3">
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-1">
                          <h4 className="font-semibold text-slate-800 text-sm">{rule.rule_name}</h4>
                          <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                            rule.severity === 'CRITICAL'
                              ? 'bg-red-100 text-red-700'
                              : 'bg-amber-100 text-amber-700'
                          }`}>
                            {rule.severity}
                          </span>
                        </div>
                        <div className="flex flex-wrap gap-2 text-xs">
                          {rule.merchant_id && (
                            <span className="px-2 py-1 bg-blue-50 text-blue-700 rounded-md border border-blue-200">
                              {rule.merchant_id}
                            </span>
                          )}
                          {rule.filter_country && (
                            <span className="px-2 py-1 bg-slate-100 text-slate-700 rounded-md">
                              🌍 {rule.filter_country}
                            </span>
                          )}
                          {rule.filter_provider && (
                            <span className="px-2 py-1 bg-slate-100 text-slate-700 rounded-md">
                              💳 {rule.filter_provider}
                            </span>
                          )}
                          {rule.filter_issuer && (
                            <span className="px-2 py-1 bg-slate-100 text-slate-700 rounded-md">
                              🏦 {rule.filter_issuer}
                            </span>
                          )}
                          {rule.is_time_based && (
                            <span className="px-2 py-1 bg-purple-50 text-purple-700 rounded-md border border-purple-200 flex items-center gap-1">
                              <Clock size={12} />
                              {rule.start_hour}:00 - {rule.end_hour}:00
                            </span>
                          )}
                        </div>
                      </div>
                      <button
                        onClick={() => handleDelete(rule.rule_id)}
                        className="p-2 hover:bg-red-50 text-red-500 rounded-lg transition-colors ml-3"
                        title="Delete rule"
                      >
                        <Trash2 size={16} />
                      </button>
                    </div>

                    <div className="flex items-center gap-2 text-sm">
                      <span className="px-2.5 py-1 bg-blue-50 text-blue-700 rounded font-medium border border-blue-200">
                        {getMetricLabel(rule.metric_type)}
                      </span>
                      <span className="text-slate-600 font-mono">{rule.operator}</span>
                      <span className="px-2.5 py-1 bg-slate-100 text-slate-800 rounded font-semibold">
                        {formatThreshold(rule.metric_type, rule.threshold_value)}
                      </span>
                      <span className="text-xs text-slate-500">
                        (min {rule.min_transactions} txns)
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-blue-100 bg-blue-50">
          <div className="flex items-center justify-center gap-2 text-xs text-blue-700">
            <RefreshCw size={12} className="animate-spin" />
            <span>
              <strong>Worker refresh:</strong> Rules reload every 10 seconds.
              Wait 10-15s after creating a rule before launching chaos scenarios.
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

export default RuleSettings;
