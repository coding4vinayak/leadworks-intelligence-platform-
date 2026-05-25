'use client';

const campaigns = [
  { id: '1', name: 'Welcome Sequence', type: 'drip', status: 'active', enrolled: 234, sent: 702, opened: 421, replied: 45, rate: '6.4%' },
  { id: '2', name: 'Hot Lead Alert', type: 'trigger', status: 'active', enrolled: 89, sent: 89, opened: 89, replied: 0, rate: 'N/A' },
  { id: '3', name: 'Re-engagement', type: 'drip', status: 'paused', enrolled: 156, sent: 312, opened: 98, replied: 12, rate: '3.8%' },
  { id: '4', name: 'Product Launch', type: 'one-shot', status: 'completed', enrolled: 500, sent: 500, opened: 345, replied: 67, rate: '13.4%' },
];

export default function Campaigns() {
  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Campaigns & Automations</h1>
          <p className="text-gray-500 text-sm mt-1">Multi-channel outreach and nurture sequences</p>
        </div>
        <button className="btn-primary text-sm">+ New Campaign</button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-4 gap-4">
        <div className="card text-center">
          <p className="text-2xl font-bold text-gray-900">4</p>
          <p className="text-xs text-gray-500">Total Campaigns</p>
        </div>
        <div className="card text-center">
          <p className="text-2xl font-bold text-green-600">2</p>
          <p className="text-xs text-gray-500">Active</p>
        </div>
        <div className="card text-center">
          <p className="text-2xl font-bold text-gray-900">1,603</p>
          <p className="text-xs text-gray-500">Emails Sent</p>
        </div>
        <div className="card text-center">
          <p className="text-2xl font-bold text-blue-600">7.8%</p>
          <p className="text-xs text-gray-500">Avg Reply Rate</p>
        </div>
      </div>

      {/* Campaign List */}
      <div className="card p-0 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b">
            <tr>
              <th className="px-6 py-3 text-left font-medium text-gray-600">Campaign</th>
              <th className="px-6 py-3 text-left font-medium text-gray-600">Type</th>
              <th className="px-6 py-3 text-left font-medium text-gray-600">Status</th>
              <th className="px-6 py-3 text-left font-medium text-gray-600">Enrolled</th>
              <th className="px-6 py-3 text-left font-medium text-gray-600">Sent</th>
              <th className="px-6 py-3 text-left font-medium text-gray-600">Opened</th>
              <th className="px-6 py-3 text-left font-medium text-gray-600">Replied</th>
              <th className="px-6 py-3 text-left font-medium text-gray-600">Rate</th>
              <th className="px-6 py-3 text-left font-medium text-gray-600">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {campaigns.map((campaign) => (
              <tr key={campaign.id} className="hover:bg-gray-50">
                <td className="px-6 py-4 font-medium text-gray-900">{campaign.name}</td>
                <td className="px-6 py-4">
                  <span className="text-xs bg-gray-100 px-2 py-0.5 rounded capitalize">{campaign.type}</span>
                </td>
                <td className="px-6 py-4">
                  <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                    campaign.status === 'active' ? 'bg-green-100 text-green-800' :
                    campaign.status === 'paused' ? 'bg-yellow-100 text-yellow-800' :
                    'bg-gray-100 text-gray-600'
                  }`}>{campaign.status}</span>
                </td>
                <td className="px-6 py-4 text-gray-600">{campaign.enrolled}</td>
                <td className="px-6 py-4 text-gray-600">{campaign.sent}</td>
                <td className="px-6 py-4 text-gray-600">{campaign.opened}</td>
                <td className="px-6 py-4 text-gray-600">{campaign.replied}</td>
                <td className="px-6 py-4 font-medium text-gray-900">{campaign.rate}</td>
                <td className="px-6 py-4">
                  {campaign.status === 'active' ? (
                    <button className="text-yellow-600 text-xs hover:underline">Pause</button>
                  ) : campaign.status === 'paused' ? (
                    <button className="text-green-600 text-xs hover:underline">Resume</button>
                  ) : (
                    <button className="text-blue-600 text-xs hover:underline">View</button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
