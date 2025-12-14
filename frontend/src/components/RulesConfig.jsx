import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Settings, Save, AlertCircle, CheckCircle2, Loader2, Trash2 } from 'lucide-react';

const RulesConfig = () => {
  const [rules, setRules] = useState([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState(null);

  // Form state
  const [formData, setFormData] = useState({
    merchant_id: 'merchant_shopito',
    rule_name: '',
    filter_country: 'MX',
    filter_provider: 'STRIPE',
    threshold_error_rate: 15
  });

  // Fetch existing rules
  const fetchRules = async () => {
    setLoading(true);
    try {
      // TODO: Conectar con GET /api/rules cuando esté disponible
      // const response = await axios.get('/api/rules');
      // setRules(response.data.rules || []);
      
      // Placeholder: Simulate empty data for now
      setRules([]);
      setError(null);
    } catch (err) {
      console.error('Error fetching rules:', err);
      setError('Error loading rules');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchRules();
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSaving(true);
    setSuccess(false);
    setError(null);

    try {
      // TODO: Conectar con POST /api/rules cuando esté disponible
      // await axios.post('/api/rules', formData);
      
      // Placeholder: Simulate success
      setTimeout(() => {
        setSuccess(true);
        setSaving(false);
        setFormData({
          merchant_id: 'merchant_shopito',
          rule_name: '',
          filter_country: 'MX',
          filter_provider: 'STRIPE',
          threshold_error_rate: 15
        });
        fetchRules();
        
        // Hide success message after 3 seconds
        setTimeout(() => setSuccess(false), 3000);
      }, 1000);
    } catch (err) {
      console.error('Error creating rule:', err);
      setError('Error creating rule');
      setSaving(false);
    }
  };

  const handleDelete = async (ruleId) => {
    if (!window.confirm('Are you sure you want to delete this rule?')) {
      return;
    }

    try {
      // TODO: Connect with DELETE /api/rules/:id when available
      // await axios.delete(`/api/rules/${ruleId}`);
      fetchRules();
    } catch (err) {
      console.error('Error deleting rule:', err);
      setError('Error deleting rule');
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-6 py-8">
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center gap-3 mb-2">
          <Settings size={28} className="text-blue-400" />
          <h1 className="text-2xl font-bold text-slate-800">Monitoring Rules Configuration</h1>
        </div>
        <p className="text-sm text-slate-600">
          Create custom rules to detect anomalies by country and provider
        </p>
      </div>

      {/* Success/Error Messages */}
      {success && (
        <div className="mb-6 p-4 bg-blue-50 border border-blue-200 rounded-lg flex items-center gap-3">
          <CheckCircle2 size={20} className="text-blue-500" />
          <span className="text-sm font-medium text-blue-700">Rule created successfully</span>
        </div>
      )}

      {error && (
        <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg flex items-center gap-3">
          <AlertCircle size={20} className="text-red-500" />
          <span className="text-sm font-medium text-red-700">{error}</span>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Form Section - Left */}
        <div className="lg:col-span-2">
          <div className="bg-white border border-blue-100 rounded-lg p-6 shadow-sm">
            <h2 className="text-lg font-semibold text-slate-800 mb-6 flex items-center gap-2">
              <Settings size={20} className="text-blue-400" />
              Create New Rule
            </h2>

            <form onSubmit={handleSubmit} className="space-y-6">
              {/* Merchant ID */}
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">
                  Merchant ID
                </label>
                <input
                  type="text"
                  value={formData.merchant_id}
                  onChange={(e) => setFormData({ ...formData, merchant_id: e.target.value })}
                  className="w-full px-4 py-2 border border-blue-200 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-blue-400 focus:border-transparent"
                  required
                />
              </div>

              {/* Rule Name */}
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">
                  Rule Name
                </label>
                <input
                  type="text"
                  value={formData.rule_name}
                  onChange={(e) => setFormData({ ...formData, rule_name: e.target.value })}
                  placeholder="e.g., Stripe Mexico Alert"
                  className="w-full px-4 py-2 border border-blue-200 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-blue-400 focus:border-transparent"
                  required
                />
              </div>

              {/* Country Filter */}
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">
                  Country
                </label>
                <select
                  value={formData.filter_country}
                  onChange={(e) => setFormData({ ...formData, filter_country: e.target.value })}
                  className="w-full px-4 py-2 border border-blue-200 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-blue-400 focus:border-transparent"
                  required
                >
                  <option value="MX">Mexico (MX)</option>
                  <option value="CO">Colombia (CO)</option>
                  <option value="BR">Brazil (BR)</option>
                </select>
              </div>

              {/* Provider Filter */}
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">
                  Provider
                </label>
                <select
                  value={formData.filter_provider}
                  onChange={(e) => setFormData({ ...formData, filter_provider: e.target.value })}
                  className="w-full px-4 py-2 border border-blue-200 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-blue-400 focus:border-transparent"
                  required
                >
                  <option value="STRIPE">Stripe</option>
                  <option value="ADYEN">Adyen</option>
                  <option value="DLOCAL">dLocal</option>
                </select>
              </div>

              {/* Threshold Error Rate - Slider */}
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">
                  Error Rate Threshold: {formData.threshold_error_rate}%
                </label>
                <input
                  type="range"
                  min="0"
                  max="100"
                  value={formData.threshold_error_rate}
                  onChange={(e) => setFormData({ ...formData, threshold_error_rate: parseInt(e.target.value) })}
                  className="w-full h-2 bg-blue-100 rounded-lg appearance-none cursor-pointer accent-blue-500"
                />
                <div className="flex justify-between text-xs text-slate-500 mt-1">
                  <span>0%</span>
                  <span>50%</span>
                  <span>100%</span>
                </div>
                <p className="text-xs text-slate-500 mt-2">
                  Alert will trigger when error rate exceeds this threshold
                </p>
              </div>

              {/* Submit Button */}
              <button
                type="submit"
                disabled={saving}
                className="w-full flex items-center justify-center gap-2 bg-blue-500 hover:bg-blue-600 text-white font-medium py-3 px-4 rounded-lg transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed focus:outline-none focus:ring-2 focus:ring-blue-400"
              >
                {saving ? (
                  <>
                    <Loader2 size={18} className="animate-spin" />
                    <span>Saving...</span>
                  </>
                ) : (
                  <>
                    <Save size={18} />
                    <span>Create Rule</span>
                  </>
                )}
              </button>
            </form>
          </div>
        </div>

        {/* Rules List - Right */}
        <div className="lg:col-span-1">
          <div className="bg-white border border-blue-100 rounded-lg p-6 shadow-sm">
            <h2 className="text-lg font-semibold text-slate-800 mb-4">
              Active Rules ({rules.length})
            </h2>

            {loading ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 size={24} className="text-blue-400 animate-spin" />
              </div>
            ) : rules.length === 0 ? (
              <div className="text-center py-8">
                <AlertCircle size={32} className="text-blue-300 mx-auto mb-3" />
                <p className="text-sm text-slate-500">No rules configured</p>
                <p className="text-xs text-slate-400 mt-1">Create your first rule using the form</p>
              </div>
            ) : (
              <div className="space-y-3">
                {rules.map((rule) => (
                  <div
                    key={rule.rule_id}
                    className="p-4 bg-blue-50 border border-blue-100 rounded-lg"
                  >
                    <div className="flex items-start justify-between mb-2">
                      <div className="flex-1">
                        <h3 className="text-sm font-semibold text-slate-800">{rule.rule_name}</h3>
                        <p className="text-xs text-slate-600 mt-1">
                          {rule.filter_country} · {rule.filter_provider}
                        </p>
                      </div>
                      <button
                        onClick={() => handleDelete(rule.rule_id)}
                        className="p-1 hover:bg-red-100 rounded text-red-500 transition-colors"
                        title="Delete rule"
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                    <div className="mt-2 pt-2 border-t border-blue-200">
                      <div className="flex items-center justify-between text-xs">
                        <span className="text-slate-600">Threshold:</span>
                        <span className="font-semibold text-slate-800">{rule.threshold_error_rate}%</span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default RulesConfig;

