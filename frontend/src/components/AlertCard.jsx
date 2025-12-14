import React, { useState } from 'react';
import { AlertTriangle, DollarSign, TrendingUp, Activity, Check, Loader2, Zap } from 'lucide-react';
import axios from 'axios';

const AlertCard = ({ alert }) => {
  const [isResolving, setIsResolving] = useState(false);
  const [isResolved, setIsResolved] = useState(false);

  const handleAction = async () => {
    setIsResolving(true);

    try {
      // Call the resolve endpoint
      await axios.post('/api/simulation/resolve', {
        alert_id: alert.alert_id,
        action_type: alert.suggested_action?.action_type
      });

      // Mark as resolved
      setTimeout(() => {
        setIsResolving(false);
        setIsResolved(true);
      }, 1500);
    } catch (error) {
      console.error('Failed to resolve alert:', error);
      setIsResolving(false);
    }
  };

  const severityConfig = {
    CRITICAL: {
      bgColor: 'bg-red-950/20',
      borderColor: 'border-red-900/50',
      textColor: 'text-red-400',
      badgeBg: 'bg-red-500/10',
      badgeText: 'text-red-400',
      badgeBorder: 'border-red-500/30'
    },
    WARNING: {
      bgColor: 'bg-yellow-950/20',
      borderColor: 'border-yellow-900/50',
      textColor: 'text-yellow-400',
      badgeBg: 'bg-yellow-500/10',
      badgeText: 'text-yellow-400',
      badgeBorder: 'border-yellow-500/30'
    }
  };

  const config = severityConfig[alert.severity] || severityConfig.CRITICAL;

  const cardClasses = isResolved
    ? 'bg-green-950/10 border-green-500/30 opacity-75'
    : `${config.bgColor} ${config.borderColor}`;

  return (
    <div className={`relative border rounded-lg p-5 transition-all duration-300 ${cardClasses}`}>
      {/* Header Section */}
      <div className="flex items-start justify-between mb-4">
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-2">
            <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium border ${config.badgeBg} ${config.badgeText} ${config.badgeBorder}`}>
              <AlertTriangle size={12} />
              {alert.severity}
            </span>
            {isResolved && (
              <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium border bg-green-500/10 text-green-400 border-green-500/30">
                <Check size={12} />
                Resolved
              </span>
            )}
          </div>
          <h3 className="text-base font-semibold text-gray-100 leading-tight">{alert.title}</h3>
          <p className="text-xs text-gray-500 mt-1">
            {new Date(alert.created_at).toLocaleString('en-US', {
              month: 'short',
              day: 'numeric',
              hour: '2-digit',
              minute: '2-digit'
            })}
          </p>
        </div>

        {/* Revenue at Risk */}
        <div className="text-right ml-4">
          <div className="flex items-center justify-end gap-1.5 text-red-400 mb-1">
            <DollarSign size={16} />
            <span className="text-2xl font-bold tabular-nums">
              {alert.revenue_at_risk_usd?.toLocaleString('en-US', {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2
              })}
            </span>
          </div>
          <div className="text-xs text-gray-500">at risk</div>
        </div>
      </div>

      {/* LLM Explanation */}
      <div className="mb-4 p-3.5 bg-black/20 rounded-md border border-gray-800">
        <p className="text-sm text-gray-300 leading-relaxed">
          {alert.llm_explanation || 'No explanation available'}
        </p>
      </div>

      {/* Metrics Grid */}
      <div className="grid grid-cols-2 gap-3 mb-4">
        <div className="flex items-center gap-2">
          <Activity size={14} className="text-gray-500" />
          <div>
            <span className="text-xs text-gray-500">Affected Transactions</span>
            <div className="text-sm font-semibold text-gray-200 tabular-nums">
              {alert.affected_transactions?.toLocaleString()}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <TrendingUp size={14} className="text-gray-500" />
          <div>
            <span className="text-xs text-gray-500">Confidence</span>
            <div className="text-sm font-semibold text-gray-200 tabular-nums">
              {(alert.confidence_score * 100).toFixed(0)}%
            </div>
          </div>
        </div>
      </div>

      {/* Root Cause */}
      {alert.root_cause && (
        <div className="mb-4 text-xs text-gray-500 space-y-1">
          <div>
            <span className="font-medium text-gray-400">Provider:</span>{' '}
            <span className="text-gray-300">{alert.root_cause.provider}</span>
          </div>
          <div>
            <span className="font-medium text-gray-400">Scope:</span>{' '}
            <span className="text-gray-300">{alert.root_cause.scope}</span>
          </div>
        </div>
      )}

      {/* Action Button */}
      {alert.suggested_action && !isResolved && (
        <button
          onClick={handleAction}
          disabled={isResolving}
          className={`
            w-full flex items-center justify-center gap-2
            bg-blue-600/10 hover:bg-blue-600/20 border border-blue-500/30
            text-blue-400 font-medium py-2.5 px-4 rounded-md
            transition-all duration-200
            disabled:opacity-50 disabled:cursor-not-allowed
            focus:outline-none focus:ring-2 focus:ring-blue-500/50
          `}
        >
          {isResolving ? (
            <>
              <Loader2 size={16} className="animate-spin" />
              <span className="text-sm">Resolving...</span>
            </>
          ) : (
            <>
              <Zap size={16} />
              <span className="text-sm">{alert.suggested_action.label}</span>
            </>
          )}
        </button>
      )}

      {isResolved && (
        <div className="flex items-center justify-center gap-2 p-2.5 bg-green-500/10 border border-green-500/30 rounded-md">
          <Check size={16} className="text-green-400" />
          <span className="text-sm font-medium text-green-400">Action executed successfully</span>
        </div>
      )}
    </div>
  );
};

export default AlertCard;
