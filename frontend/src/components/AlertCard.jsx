import React, { useState } from 'react';

const AlertCard = ({ alert }) => {
  const [showToast, setShowToast] = useState(false);

  const handleAction = () => {
    setShowToast(true);
    setTimeout(() => setShowToast(false), 3000);
  };

  const severityColors = {
    CRITICAL: 'bg-red-900 border-red-500 text-red-100',
    WARNING: 'bg-yellow-900 border-yellow-500 text-yellow-100'
  };

  const severityBadge = {
    CRITICAL: 'bg-red-500 text-white',
    WARNING: 'bg-yellow-500 text-black'
  };

  return (
    <div className={`relative border-2 rounded-lg p-4 ${severityColors[alert.severity] || 'bg-gray-800 border-gray-600'} shadow-lg`}>
      {/* Header */}
      <div className="flex justify-between items-start mb-3">
        <div>
          <span className={`inline-block px-2 py-1 rounded text-xs font-bold ${severityBadge[alert.severity]}`}>
            {alert.severity}
          </span>
          <h3 className="text-lg font-bold mt-2">{alert.title}</h3>
          <p className="text-xs text-gray-400">
            {new Date(alert.created_at).toLocaleString()}
          </p>
        </div>
        <div className="text-right">
          <div className="text-2xl font-bold text-red-400">
            ${alert.revenue_at_risk_usd?.toFixed(2)}
          </div>
          <div className="text-xs text-gray-400">at risk</div>
        </div>
      </div>

      {/* LLM Explanation */}
      <div className="mb-4 p-3 bg-black bg-opacity-30 rounded">
        <p className="text-sm leading-relaxed">{alert.llm_explanation || 'No explanation available'}</p>
      </div>

      {/* Metrics */}
      <div className="grid grid-cols-2 gap-2 mb-4 text-sm">
        <div>
          <span className="text-gray-400">Affected Transactions:</span>
          <span className="ml-2 font-semibold">{alert.affected_transactions}</span>
        </div>
        <div>
          <span className="text-gray-400">Confidence:</span>
          <span className="ml-2 font-semibold">{(alert.confidence_score * 100).toFixed(0)}%</span>
        </div>
      </div>

      {/* Root Cause */}
      {alert.root_cause && (
        <div className="mb-4 text-xs">
          <div className="text-gray-400">
            <span className="font-semibold">Provider:</span> {alert.root_cause.provider} |
            <span className="font-semibold ml-2">Scope:</span> {alert.root_cause.scope}
          </div>
        </div>
      )}

      {/* Action Button */}
      {alert.suggested_action && (
        <button
          onClick={handleAction}
          className="w-full bg-blue-600 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded transition-colors"
        >
          ⚡ {alert.suggested_action.label}
        </button>
      )}

      {/* Toast Notification */}
      {showToast && (
        <div className="absolute bottom-4 right-4 bg-green-500 text-white px-4 py-2 rounded shadow-lg animate-bounce">
          ✅ Action executed successfully!
        </div>
      )}
    </div>
  );
};

export default AlertCard;
