import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { X, UserPlus, Link, Users } from 'lucide-react';

function KamManager({ isOpen, onClose }) {
  const [activeTab, setActiveTab] = useState('register');
  const [kams, setKams] = useState([]);
  const [loading, setLoading] = useState(false);

  const [registerForm, setRegisterForm] = useState({
    name: '',
    email: ''
  });

  const [assignForm, setAssignForm] = useState({
    kam_id: '',
    merchant_id: ''
  });

  useEffect(() => {
    if (isOpen) {
      fetchKams();
    }
  }, [isOpen]);

  const fetchKams = async () => {
    try {
      setLoading(true);
      const response = await axios.get('/api/kams');
      setKams(response.data);
    } catch (error) {
      console.error('Error fetching KAMs:', error);
      alert('Failed to fetch KAMs');
    } finally {
      setLoading(false);
    }
  };

  const handleRegisterSubmit = async (e) => {
    e.preventDefault();
    try {
      setLoading(true);
      await axios.post('/api/kams', registerForm);
      alert('KAM registered successfully!');
      setRegisterForm({ name: '', email: '' });
      fetchKams();
    } catch (error) {
      console.error('Error registering KAM:', error);
      alert(error.response?.data?.detail || 'Failed to register KAM');
    } finally {
      setLoading(false);
    }
  };

  const handleAssignSubmit = async (e) => {
    e.preventDefault();
    try {
      setLoading(true);
      await axios.post('/api/merchants/assign', assignForm);
      alert(`Merchant ${assignForm.merchant_id} assigned successfully!`);
      setAssignForm({ kam_id: '', merchant_id: '' });
    } catch (error) {
      console.error('Error assigning merchant:', error);
      alert(error.response?.data?.detail || 'Failed to assign merchant');
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-hidden flex flex-col">
        <div className="flex items-center justify-between p-6 border-b border-blue-100">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-blue-50 flex items-center justify-center">
              <Users size={20} className="text-blue-500" />
            </div>
            <div>
              <h2 className="text-xl font-semibold text-slate-800">KAM Management</h2>
              <p className="text-xs text-slate-500 mt-0.5">Register and assign Key Account Managers</p>
            </div>
          </div>
          <button onClick={onClose} className="p-2 hover:bg-slate-100 rounded-lg transition-colors">
            <X size={20} className="text-slate-600" />
          </button>
        </div>

        <div className="flex border-b border-slate-200">
          <button
            onClick={() => setActiveTab('register')}
            className={`flex-1 py-3 px-4 text-sm font-medium transition-colors ${
              activeTab === 'register'
                ? 'text-blue-600 border-b-2 border-blue-600 bg-blue-50'
                : 'text-slate-600 hover:text-slate-800 hover:bg-slate-50'
            }`}
          >
            <div className="flex items-center justify-center gap-2">
              <UserPlus size={16} />
              Register KAM
            </div>
          </button>
          <button
            onClick={() => setActiveTab('assign')}
            className={`flex-1 py-3 px-4 text-sm font-medium transition-colors ${
              activeTab === 'assign'
                ? 'text-blue-600 border-b-2 border-blue-600 bg-blue-50'
                : 'text-slate-600 hover:text-slate-800 hover:bg-slate-50'
            }`}
          >
            <div className="flex items-center justify-center gap-2">
              <Link size={16} />
              Assign Merchant
            </div>
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-6">
          {activeTab === 'register' && (
            <form onSubmit={handleRegisterSubmit} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1.5">KAM Name *</label>
                <input
                  type="text"
                  required
                  value={registerForm.name}
                  onChange={(e) => setRegisterForm({ ...registerForm, name: e.target.value })}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
                  placeholder="e.g., Julián Admin"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1.5">Email Address *</label>
                <input
                  type="email"
                  required
                  value={registerForm.email}
                  onChange={(e) => setRegisterForm({ ...registerForm, email: e.target.value })}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
                  placeholder="julian@yunosentinel.com"
                />
              </div>

              <button
                type="submit"
                disabled={loading}
                className="w-full py-2.5 px-4 bg-blue-500 hover:bg-blue-600 disabled:bg-slate-300 text-white font-medium rounded-lg text-sm transition-colors flex items-center justify-center gap-2"
              >
                <UserPlus size={16} />
                {loading ? 'Registering...' : 'Register KAM'}
              </button>

              {kams.length > 0 && (
                <div className="mt-6 pt-6 border-t border-slate-200">
                  <h4 className="text-sm font-semibold text-slate-700 mb-3">Registered KAMs ({kams.length})</h4>
                  <div className="space-y-2 max-h-60 overflow-y-auto">
                    {kams.map((kam) => (
                      <div key={kam.kam_id} className="p-3 bg-slate-50 rounded-lg border border-slate-200">
                        <div className="flex items-center justify-between">
                          <div>
                            <p className="font-medium text-slate-800 text-sm">{kam.name}</p>
                            <p className="text-xs text-slate-500">{kam.email}</p>
                          </div>
                          <span className="text-xs text-slate-400 font-mono">{kam.kam_id.slice(0, 8)}...</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </form>
          )}

          {activeTab === 'assign' && (
            <form onSubmit={handleAssignSubmit} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1.5">Select KAM *</label>
                <select
                  required
                  value={assignForm.kam_id}
                  onChange={(e) => setAssignForm({ ...assignForm, kam_id: e.target.value })}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
                >
                  <option value="">-- Select a KAM --</option>
                  {kams.map((kam) => (
                    <option key={kam.kam_id} value={kam.kam_id}>
                      {kam.name} ({kam.email})
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1.5">Merchant ID *</label>
                <input
                  type="text"
                  required
                  value={assignForm.merchant_id}
                  onChange={(e) => setAssignForm({ ...assignForm, merchant_id: e.target.value })}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
                  placeholder="e.g., merchant_shopito"
                />
                <p className="text-xs text-slate-500 mt-1.5">Common: merchant_shopito, merchant_rappi, merchant_uber</p>
              </div>

              <button
                type="submit"
                disabled={loading}
                className="w-full py-2.5 px-4 bg-blue-500 hover:bg-blue-600 disabled:bg-slate-300 text-white font-medium rounded-lg text-sm transition-colors flex items-center justify-center gap-2"
              >
                <Link size={16} />
                {loading ? 'Assigning...' : 'Link Merchant to KAM'}
              </button>
            </form>
          )}
        </div>

        <div className="p-4 border-t border-slate-100 bg-slate-50">
          <p className="text-xs text-slate-500 text-center">KAMs receive email notifications for their assigned merchants</p>
        </div>
      </div>
    </div>
  );
}

export default KamManager;
