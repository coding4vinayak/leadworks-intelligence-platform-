'use client';

const companyData = {
  name: 'TechCorp',
  domain: 'techcorp.io',
  logo: 'https://logo.clearbit.com/techcorp.io',
  description: 'AI-powered developer tools for engineering teams',
  industry: 'Developer Tools / SaaS',
  founded: 2019,
  headquarters: 'San Francisco, CA',
  employees: '201-500',
  revenue: '$10M - $50M',
  funding: { total: '$45M', stage: 'Series B', lastRound: 'Jun 2023' },
  social: {
    linkedin: 'https://linkedin.com/company/techcorp',
    twitter: 'https://twitter.com/techcorp',
    github: 'https://github.com/techcorp',
  },
  techStack: {
    frontend: ['React', 'Next.js', 'Tailwind CSS'],
    backend: ['Node.js', 'Python', 'PostgreSQL'],
    infrastructure: ['AWS', 'Vercel', 'Cloudflare'],
    analytics: ['Mixpanel', 'Segment', 'Google Analytics'],
    marketing: ['HubSpot', 'Intercom', 'Mailchimp'],
    payment: ['Stripe'],
  },
  icpScore: 87,
  signals: [
    { signal: 'Hiring engineers', confidence: 'high', date: '2024-01-10' },
    { signal: 'New product launch', confidence: 'medium', date: '2024-01-05' },
    { signal: 'Series B funding', confidence: 'high', date: '2023-06-15' },
    { signal: 'Tech stack overlap (React, AWS)', confidence: 'high', date: '2024-01-12' },
  ],
  employees_known: [
    { name: 'Sarah Chen', title: 'VP Engineering', score: 92, linkedin: '#' },
    { name: 'Mike Lee', title: 'CTO', score: 88, linkedin: '#' },
    { name: 'Lisa Wang', title: 'Head of Product', score: 74, linkedin: '#' },
    { name: 'Tom Adams', title: 'Director of Sales', score: 68, linkedin: '#' },
  ],
};

export default function CompanyIntelligence() {
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="card">
        <div className="flex items-start justify-between">
          <div className="flex items-center space-x-4">
            <div className="w-14 h-14 bg-gray-100 rounded-xl flex items-center justify-center text-2xl font-bold text-gray-400">
              TC
            </div>
            <div>
              <h1 className="text-xl font-bold text-gray-900">{companyData.name}</h1>
              <p className="text-sm text-gray-500">{companyData.description}</p>
              <div className="flex items-center space-x-4 mt-1 text-xs text-gray-500">
                <span>{companyData.industry}</span>
                <span>•</span>
                <span>{companyData.headquarters}</span>
                <span>•</span>
                <span>{companyData.employees} employees</span>
              </div>
            </div>
          </div>
          <div className="text-right">
            <div className="text-xs text-gray-500">ICP Match</div>
            <div className="text-2xl font-bold text-green-600">{companyData.icpScore}%</div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Company Details */}
        <div className="card">
          <h3 className="font-semibold text-gray-900 mb-3">Company Info</h3>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between"><span className="text-gray-500">Founded</span><span>{companyData.founded}</span></div>
            <div className="flex justify-between"><span className="text-gray-500">Revenue</span><span>{companyData.revenue}</span></div>
            <div className="flex justify-between"><span className="text-gray-500">Employees</span><span>{companyData.employees}</span></div>
            <div className="flex justify-between"><span className="text-gray-500">Domain</span><span className="text-blue-600">{companyData.domain}</span></div>
          </div>
          <div className="mt-4 pt-4 border-t">
            <h4 className="text-sm font-medium text-gray-700 mb-2">Funding</h4>
            <div className="bg-green-50 rounded-lg p-3">
              <div className="text-lg font-bold text-green-700">{companyData.funding.total}</div>
              <div className="text-xs text-green-600">{companyData.funding.stage} • Last round: {companyData.funding.lastRound}</div>
            </div>
          </div>
        </div>

        {/* Tech Stack */}
        <div className="card">
          <h3 className="font-semibold text-gray-900 mb-3">Tech Stack</h3>
          <div className="space-y-3">
            {Object.entries(companyData.techStack).map(([category, techs]) => (
              <div key={category}>
                <p className="text-xs font-medium text-gray-500 uppercase mb-1">{category}</p>
                <div className="flex flex-wrap gap-1">
                  {techs.map((tech) => (
                    <span key={tech} className="text-xs bg-blue-50 text-blue-700 px-2 py-0.5 rounded">{tech}</span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Buying Signals */}
        <div className="card">
          <h3 className="font-semibold text-gray-900 mb-3">Buying Signals</h3>
          <div className="space-y-3">
            {companyData.signals.map((signal, i) => (
              <div key={i} className="flex items-start space-x-2">
                <div className={`w-2 h-2 rounded-full mt-1.5 ${
                  signal.confidence === 'high' ? 'bg-green-500' : 'bg-yellow-500'
                }`}></div>
                <div className="flex-1">
                  <p className="text-sm text-gray-900">{signal.signal}</p>
                  <p className="text-xs text-gray-400">{signal.date}</p>
                </div>
                <span className={`text-xs px-1.5 py-0.5 rounded ${
                  signal.confidence === 'high' ? 'bg-green-100 text-green-700' : 'bg-yellow-100 text-yellow-700'
                }`}>{signal.confidence}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Known Employees */}
      <div className="card">
        <div className="flex justify-between items-center mb-4">
          <h3 className="font-semibold text-gray-900">Known Contacts ({companyData.employees_known.length})</h3>
          <button className="text-sm text-blue-600 hover:underline">Find more on LinkedIn</button>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {companyData.employees_known.map((emp, i) => (
            <div key={i} className="border rounded-lg p-3 hover:shadow-md transition-shadow">
              <div className="flex justify-between items-start">
                <div>
                  <p className="font-medium text-sm text-gray-900">{emp.name}</p>
                  <p className="text-xs text-gray-500">{emp.title}</p>
                </div>
                <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${
                  emp.score >= 75 ? 'bg-red-100 text-red-800' :
                  emp.score >= 45 ? 'bg-yellow-100 text-yellow-800' :
                  'bg-blue-100 text-blue-800'
                }`}>{emp.score}</span>
              </div>
              <div className="mt-2 flex space-x-2">
                <button className="text-xs text-blue-600 hover:underline">View</button>
                <button className="text-xs text-gray-500 hover:underline">Enrich</button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
