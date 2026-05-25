'use client';

export default function Settings() {
  return (
    <div className="space-y-6 max-w-3xl">
      <h1 className="text-2xl font-bold text-gray-900">Settings</h1>

      {/* ICP Configuration */}
      <div className="card">
        <h2 className="font-semibold text-gray-900 mb-4">Ideal Customer Profile (ICP)</h2>
        <p className="text-sm text-gray-500 mb-4">Configure your ICP to improve lead scoring accuracy.</p>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Target Industries</label>
            <input type="text" placeholder="SaaS, FinTech, HealthTech (comma separated)" className="w-full px-3 py-2 border rounded-lg text-sm" />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Target Job Titles</label>
            <input type="text" placeholder="CTO, VP Engineering, Head of Product" className="w-full px-3 py-2 border rounded-lg text-sm" />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Company Size</label>
            <select className="w-full px-3 py-2 border rounded-lg text-sm">
              <option>Any size</option>
              <option>1-50 (Startup)</option>
              <option>51-200 (Growth)</option>
              <option>201-1000 (Mid-Market)</option>
              <option>1000+ (Enterprise)</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Target Tech Stack</label>
            <input type="text" placeholder="React, AWS, Stripe, HubSpot" className="w-full px-3 py-2 border rounded-lg text-sm" />
          </div>
          <button className="btn-primary text-sm">Save ICP Settings</button>
        </div>
      </div>

      {/* Scoring Configuration */}
      <div className="card">
        <h2 className="font-semibold text-gray-900 mb-4">Scoring Weights</h2>
        <div className="space-y-3">
          {[
            { name: 'Firmographic (title, company size)', value: 30 },
            { name: 'Behavioral (page visits, content)', value: 30 },
            { name: 'Engagement (email opens, replies)', value: 25 },
            { name: 'Enrichment quality', value: 15 },
          ].map((weight) => (
            <div key={weight.name} className="flex items-center space-x-4">
              <span className="text-sm text-gray-700 flex-1">{weight.name}</span>
              <input type="range" min="0" max="50" defaultValue={weight.value} className="w-32" />
              <span className="text-sm font-medium w-10 text-right">{weight.value}%</span>
            </div>
          ))}
        </div>
      </div>

      {/* API Keys */}
      <div className="card">
        <h2 className="font-semibold text-gray-900 mb-4">API Keys</h2>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">OpenAI API Key</label>
            <input type="password" placeholder="sk-..." className="w-full px-3 py-2 border rounded-lg text-sm" />
            <p className="text-xs text-gray-400 mt-1">Used for AI enrichment, scoring, and outreach generation</p>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Your API Key</label>
            <div className="flex space-x-2">
              <code className="flex-1 bg-gray-100 px-3 py-2 rounded-lg text-sm font-mono">lw_sk_abc123def456...</code>
              <button className="btn-secondary text-sm">Regenerate</button>
            </div>
          </div>
        </div>
      </div>

      {/* Team */}
      <div className="card">
        <h2 className="font-semibold text-gray-900 mb-4">Team</h2>
        <div className="space-y-3">
          {[
            { name: 'You', email: 'you@company.com', role: 'Owner' },
            { name: 'Sales Rep 1', email: 'rep1@company.com', role: 'Member' },
          ].map((member, i) => (
            <div key={i} className="flex items-center justify-between py-2 border-b last:border-0">
              <div>
                <p className="font-medium text-sm text-gray-900">{member.name}</p>
                <p className="text-xs text-gray-500">{member.email}</p>
              </div>
              <span className="text-xs bg-gray-100 px-2 py-0.5 rounded">{member.role}</span>
            </div>
          ))}
        </div>
        <button className="mt-4 btn-secondary text-sm">+ Invite Team Member</button>
      </div>
    </div>
  );
}
