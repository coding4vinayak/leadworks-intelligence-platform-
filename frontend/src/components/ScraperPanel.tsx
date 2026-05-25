'use client';
import { useState } from 'react';

const scraperTypes = [
  { id: 'linkedin', name: 'LinkedIn Search', desc: 'Find professionals by title, company, location', icon: '🔗' },
  { id: 'google_maps', name: 'Google Maps', desc: 'Find businesses with phones, websites, reviews', icon: '📍' },
  { id: 'website', name: 'Website Scraper', desc: 'Extract emails, phones, team members from any URL', icon: '🌐' },
  { id: 'email_finder', name: 'Email Finder', desc: 'Find email for a person using name + company', icon: '📧' },
  { id: 'tech_stack', name: 'Tech Stack', desc: 'Detect technologies used by a company', icon: '🔧' },
  { id: 'find_leads', name: 'Multi-Source Search', desc: 'Search all sources at once for maximum coverage', icon: '🚀' },
];

export default function ScraperPanel() {
  const [activeType, setActiveType] = useState('linkedin');
  const [isRunning, setIsRunning] = useState(false);
  const [results, setResults] = useState<any[]>([]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Scrapers</h1>
        <p className="text-gray-500 text-sm mt-1">Find leads from multiple sources automatically</p>
      </div>

      {/* Scraper Type Selection */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        {scraperTypes.map((type) => (
          <button
            key={type.id}
            onClick={() => setActiveType(type.id)}
            className={`p-3 rounded-xl border-2 text-left transition-all ${
              activeType === type.id
                ? 'border-blue-500 bg-blue-50'
                : 'border-gray-200 hover:border-gray-300 bg-white'
            }`}
          >
            <div className="text-2xl mb-1">{type.icon}</div>
            <div className="font-medium text-sm text-gray-900">{type.name}</div>
            <div className="text-xs text-gray-500 mt-0.5">{type.desc}</div>
          </button>
        ))}
      </div>

      {/* Scraper Form */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="card">
          <h3 className="font-semibold text-gray-900 mb-4">
            {scraperTypes.find(t => t.id === activeType)?.name} Configuration
          </h3>

          {activeType === 'linkedin' && (
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Keywords / Query</label>
                <input type="text" placeholder="e.g. CTO SaaS startup" className="w-full px-3 py-2 border rounded-lg text-sm" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Job Title</label>
                <input type="text" placeholder="e.g. VP Engineering" className="w-full px-3 py-2 border rounded-lg text-sm" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Location</label>
                <input type="text" placeholder="e.g. San Francisco, CA" className="w-full px-3 py-2 border rounded-lg text-sm" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Max Results</label>
                <input type="number" defaultValue={25} className="w-full px-3 py-2 border rounded-lg text-sm" />
              </div>
            </div>
          )}

          {activeType === 'google_maps' && (
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Business Type</label>
                <input type="text" placeholder="e.g. marketing agencies, dentists" className="w-full px-3 py-2 border rounded-lg text-sm" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Location</label>
                <input type="text" placeholder="e.g. New York, NY" className="w-full px-3 py-2 border rounded-lg text-sm" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Min Rating</label>
                <select className="w-full px-3 py-2 border rounded-lg text-sm">
                  <option>Any rating</option>
                  <option value="3">3+ stars</option>
                  <option value="4">4+ stars</option>
                  <option value="4.5">4.5+ stars</option>
                </select>
              </div>
            </div>
          )}

          {activeType === 'email_finder' && (
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">First Name</label>
                  <input type="text" placeholder="John" className="w-full px-3 py-2 border rounded-lg text-sm" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Last Name</label>
                  <input type="text" placeholder="Doe" className="w-full px-3 py-2 border rounded-lg text-sm" />
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Company Domain</label>
                <input type="text" placeholder="example.com" className="w-full px-3 py-2 border rounded-lg text-sm" />
              </div>
              <div className="flex items-center space-x-2">
                <input type="checkbox" defaultChecked className="rounded" />
                <label className="text-sm text-gray-700">Verify emails (SMTP check)</label>
              </div>
            </div>
          )}

          {activeType === 'website' && (
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">URL to Scrape</label>
                <input type="text" placeholder="https://example.com" className="w-full px-3 py-2 border rounded-lg text-sm" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Depth (pages to follow)</label>
                <input type="number" defaultValue={2} className="w-full px-3 py-2 border rounded-lg text-sm" />
              </div>
            </div>
          )}

          {activeType === 'tech_stack' && (
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Domain</label>
                <input type="text" placeholder="example.com" className="w-full px-3 py-2 border rounded-lg text-sm" />
              </div>
              <div className="flex items-center space-x-2">
                <input type="checkbox" className="rounded" />
                <label className="text-sm text-gray-700">Deep scan (multiple pages)</label>
              </div>
            </div>
          )}

          <button
            onClick={() => setIsRunning(true)}
            disabled={isRunning}
            className="mt-6 w-full btn-primary disabled:opacity-50"
          >
            {isRunning ? 'Scraping...' : 'Start Scraping'}
          </button>
        </div>

        {/* Results */}
        <div className="card">
          <h3 className="font-semibold text-gray-900 mb-4">Results</h3>
          {results.length === 0 ? (
            <div className="text-center py-12 text-gray-400">
              <div className="text-4xl mb-3">🔍</div>
              <p className="text-sm">Configure and run a scraper to see results here</p>
            </div>
          ) : (
            <div className="space-y-2">{/* results would render here */}</div>
          )}
        </div>
      </div>
    </div>
  );
}
