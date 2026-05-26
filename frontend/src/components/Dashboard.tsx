'use client';

const stats = [
  { name: 'Total Leads', value: '2,847', change: '+12.5%', up: true },
  { name: 'Hot Leads', value: '142', change: '+8.2%', up: true },
  { name: 'Enriched', value: '78%', change: '+3.1%', up: true },
  { name: 'Conversion Rate', value: '4.8%', change: '+0.6%', up: true },
  { name: 'Emails Sent', value: '1,203', change: '+15%', up: true },
  { name: 'Reply Rate', value: '12.3%', change: '-1.2%', up: false },
];

const recentLeads = [
  { name: 'Sarah Chen', company: 'TechCorp', title: 'VP Engineering', score: 92, source: 'LinkedIn', time: '5m ago' },
  { name: 'James Wilson', company: 'DataFlow Inc', title: 'CTO', score: 87, source: 'Google Maps', time: '12m ago' },
  { name: 'Maria Garcia', company: 'GrowthLab', title: 'Head of Product', score: 74, source: 'Web Form', time: '23m ago' },
  { name: 'David Kim', company: 'CloudNine', title: 'Director Sales', score: 68, source: 'CSV Import', time: '1h ago' },
  { name: 'Lisa Park', company: 'AI Solutions', title: 'CEO', score: 95, source: 'Referral', time: '2h ago' },
];

const topSources = [
  { source: 'LinkedIn Scrape', leads: 842, percentage: 30 },
  { source: 'Web Forms', leads: 654, percentage: 23 },
  { source: 'Google Maps', leads: 512, percentage: 18 },
  { source: 'CSV Import', leads: 398, percentage: 14 },
  { source: 'HubSpot Sync', leads: 256, percentage: 9 },
  { source: 'Email Finder', leads: 185, percentage: 6 },
];

export default function Dashboard() {
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
          <p className="text-gray-500 text-sm mt-1">Overview of your lead intelligence pipeline</p>
        </div>
        <div className="flex space-x-3">
          <button className="btn-secondary text-sm">Export Report</button>
          <button className="btn-primary text-sm">+ Add Lead</button>
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
        {stats.map((stat) => (
          <div key={stat.name} className="card">
            <p className="text-xs text-gray-500 font-medium">{stat.name}</p>
            <p className="text-2xl font-bold mt-1">{stat.value}</p>
            <p className={`text-xs mt-1 ${stat.up ? 'text-green-600' : 'text-red-500'}`}>
              {stat.change} vs last week
            </p>
          </div>
        ))}
      </div>

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Recent Hot Leads */}
        <div className="lg:col-span-2 card">
          <div className="flex justify-between items-center mb-4">
            <h2 className="font-semibold text-gray-900">Recent Hot Leads</h2>
            <button className="text-blue-600 text-sm hover:underline">View all</button>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-gray-500 border-b">
                  <th className="pb-3 font-medium">Lead</th>
                  <th className="pb-3 font-medium">Score</th>
                  <th className="pb-3 font-medium">Source</th>
                  <th className="pb-3 font-medium">Time</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {recentLeads.map((lead, i) => (
                  <tr key={i} className="hover:bg-gray-50">
                    <td className="py-3">
                      <div className="font-medium text-gray-900">{lead.name}</div>
                      <div className="text-gray-500 text-xs">{lead.title} at {lead.company}</div>
                    </td>
                    <td className="py-3">
                      <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${
                        lead.score >= 80 ? 'bg-red-100 text-red-800' :
                        lead.score >= 50 ? 'bg-yellow-100 text-yellow-800' :
                        'bg-blue-100 text-blue-800'
                      }`}>
                        {lead.score}
                      </span>
                    </td>
                    <td className="py-3 text-gray-600">{lead.source}</td>
                    <td className="py-3 text-gray-400">{lead.time}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Lead Sources */}
        <div className="card">
          <h2 className="font-semibold text-gray-900 mb-4">Lead Sources</h2>
          <div className="space-y-3">
            {topSources.map((source) => (
              <div key={source.source}>
                <div className="flex justify-between text-sm">
                  <span className="text-gray-700">{source.source}</span>
                  <span className="text-gray-500">{source.leads}</span>
                </div>
                <div className="w-full bg-gray-100 rounded-full h-2 mt-1">
                  <div className="bg-blue-500 h-2 rounded-full" style={{ width: `${source.percentage}%` }}></div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Score Distribution + Activity */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Score Funnel */}
        <div className="card">
          <h2 className="font-semibold text-gray-900 mb-4">Score Distribution</h2>
          <div className="space-y-3">
            <div className="flex items-center space-x-4">
              <span className="w-16 text-sm text-gray-600">Hot</span>
              <div className="flex-1 bg-gray-100 rounded-full h-8 relative">
                <div className="bg-red-500 h-8 rounded-full flex items-center justify-end pr-3" style={{ width: '22%' }}>
                  <span className="text-white text-xs font-medium">142</span>
                </div>
              </div>
            </div>
            <div className="flex items-center space-x-4">
              <span className="w-16 text-sm text-gray-600">Warm</span>
              <div className="flex-1 bg-gray-100 rounded-full h-8 relative">
                <div className="bg-yellow-500 h-8 rounded-full flex items-center justify-end pr-3" style={{ width: '45%' }}>
                  <span className="text-white text-xs font-medium">892</span>
                </div>
              </div>
            </div>
            <div className="flex items-center space-x-4">
              <span className="w-16 text-sm text-gray-600">Cold</span>
              <div className="flex-1 bg-gray-100 rounded-full h-8 relative">
                <div className="bg-blue-400 h-8 rounded-full flex items-center justify-end pr-3" style={{ width: '63%' }}>
                  <span className="text-white text-xs font-medium">1,813</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Recent Activity */}
        <div className="card">
          <h2 className="font-semibold text-gray-900 mb-4">Recent Activity</h2>
          <div className="space-y-3">
            {[
              { action: 'Lead enriched', detail: 'Sarah Chen - added company data, tech stack', time: '2m', color: 'bg-green-500' },
              { action: 'Score updated', detail: 'James Wilson score: 72 -> 87 (email opened)', time: '5m', color: 'bg-blue-500' },
              { action: 'Scrape completed', detail: 'LinkedIn search: "CTO SaaS SF" - 23 leads found', time: '12m', color: 'bg-purple-500' },
              { action: 'Campaign sent', detail: 'Welcome sequence - 45 emails delivered', time: '30m', color: 'bg-yellow-500' },
              { action: 'Fraud blocked', detail: 'Spam lead rejected (disposable email)', time: '1h', color: 'bg-red-500' },
            ].map((item, i) => (
              <div key={i} className="flex items-start space-x-3">
                <div className={`w-2 h-2 rounded-full mt-2 ${item.color}`}></div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-gray-900">{item.action}</p>
                  <p className="text-xs text-gray-500 truncate">{item.detail}</p>
                </div>
                <span className="text-xs text-gray-400 whitespace-nowrap">{item.time}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
