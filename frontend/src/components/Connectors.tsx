'use client';

const connectors = [
  { id: 'hubspot', name: 'HubSpot', status: 'connected', lastSync: '5 min ago', records: 1234, icon: '🟠' },
  { id: 'salesforce', name: 'Salesforce', status: 'disconnected', lastSync: 'Never', records: 0, icon: '☁️' },
  { id: 'google_sheets', name: 'Google Sheets', status: 'connected', lastSync: '1 hour ago', records: 456, icon: '📊' },
  { id: 'webhook', name: 'Inbound Webhook', status: 'active', lastSync: '2 min ago', records: 89, icon: '🔗' },
  { id: 'slack', name: 'Slack', status: 'connected', lastSync: 'Real-time', records: 0, icon: '💬' },
  { id: 'zapier', name: 'Zapier', status: 'disconnected', lastSync: 'Never', records: 0, icon: '⚡' },
];

export default function Connectors() {
  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Connectors</h1>
          <p className="text-gray-500 text-sm mt-1">Manage integrations and data sources</p>
        </div>
        <button className="btn-primary text-sm">+ Add Connector</button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {connectors.map((conn) => (
          <div key={conn.id} className="card hover:shadow-md transition-shadow">
            <div className="flex items-start justify-between">
              <div className="flex items-center space-x-3">
                <div className="text-3xl">{conn.icon}</div>
                <div>
                  <h3 className="font-semibold text-gray-900">{conn.name}</h3>
                  <p className="text-xs text-gray-500">Last sync: {conn.lastSync}</p>
                </div>
              </div>
              <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                conn.status === 'connected' || conn.status === 'active'
                  ? 'bg-green-100 text-green-800'
                  : 'bg-gray-100 text-gray-600'
              }`}>{conn.status}</span>
            </div>

            {conn.records > 0 && (
              <div className="mt-4 pt-3 border-t text-sm text-gray-600">
                {conn.records.toLocaleString()} records synced
              </div>
            )}

            <div className="mt-4 flex space-x-2">
              {conn.status === 'connected' || conn.status === 'active' ? (
                <>
                  <button className="btn-secondary text-xs py-1 px-3">Sync Now</button>
                  <button className="text-xs text-gray-500 hover:text-gray-700 px-2">Settings</button>
                </>
              ) : (
                <button className="btn-primary text-xs py-1 px-3">Connect</button>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Webhook URL */}
      <div className="card">
        <h3 className="font-semibold text-gray-900 mb-2">Your Webhook URL</h3>
        <p className="text-sm text-gray-500 mb-3">Send POST requests to this URL to create leads from forms, Zapier, or any tool.</p>
        <div className="flex items-center space-x-3">
          <code className="flex-1 bg-gray-100 px-4 py-2 rounded-lg text-sm font-mono text-gray-700">
            https://api.leadworks.io/api/v1/webhooks/inbound/your-connector-id
          </code>
          <button className="btn-secondary text-sm">Copy</button>
        </div>
      </div>
    </div>
  );
}
