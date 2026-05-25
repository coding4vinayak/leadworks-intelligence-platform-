'use client';
import { useState } from 'react';

const mockLeads = [
  { id: '1', name: 'Sarah Chen', email: 'sarah@techcorp.com', company: 'TechCorp', title: 'VP Engineering', score: 92, status: 'qualified', source: 'linkedin_scrape', enriched: true, tags: ['saas', 'enterprise'] },
  { id: '2', name: 'James Wilson', email: 'james@dataflow.io', company: 'DataFlow Inc', title: 'CTO', score: 87, status: 'contacted', source: 'google_maps', enriched: true, tags: ['ai', 'startup'] },
  { id: '3', name: 'Maria Garcia', email: 'maria@growthlab.co', company: 'GrowthLab', title: 'Head of Product', score: 74, status: 'new', source: 'web_form', enriched: true, tags: ['growth'] },
  { id: '4', name: 'David Kim', email: 'david@cloudnine.io', company: 'CloudNine', title: 'Director Sales', score: 68, status: 'nurturing', source: 'csv_import', enriched: false, tags: [] },
  { id: '5', name: 'Lisa Park', email: 'lisa@aisolutions.com', company: 'AI Solutions', title: 'CEO', score: 95, status: 'qualified', source: 'referral', enriched: true, tags: ['c-level', 'ai'] },
  { id: '6', name: 'Tom Roberts', email: 'tom@scalemkt.com', company: 'ScaleMkt', title: 'CMO', score: 81, status: 'new', source: 'linkedin_scrape', enriched: true, tags: ['marketing'] },
  { id: '7', name: 'Priya Patel', email: 'priya@fastgrowth.io', company: 'FastGrowth', title: 'VP Sales', score: 79, status: 'contacted', source: 'email_finder', enriched: true, tags: ['saas'] },
  { id: '8', name: 'Alex Johnson', email: 'alex@devtools.co', company: 'DevTools', title: 'Engineering Lead', score: 56, status: 'new', source: 'website_scrape', enriched: false, tags: ['devtools'] },
];

export default function LeadsTable() {
  const [search, setSearch] = useState('');
  const [selectedLeads, setSelectedLeads] = useState<Set<string>>(new Set());
  const [statusFilter, setStatusFilter] = useState('all');

  const filteredLeads = mockLeads.filter(lead => {
    const matchesSearch = !search || 
      lead.name.toLowerCase().includes(search.toLowerCase()) ||
      lead.email.toLowerCase().includes(search.toLowerCase()) ||
      lead.company.toLowerCase().includes(search.toLowerCase());
    const matchesStatus = statusFilter === 'all' || lead.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  const toggleSelect = (id: string) => {
    const newSelected = new Set(selectedLeads);
    if (newSelected.has(id)) newSelected.delete(id);
    else newSelected.add(id);
    setSelectedLeads(newSelected);
  };

  const selectAll = () => {
    if (selectedLeads.size === filteredLeads.length) setSelectedLeads(new Set());
    else setSelectedLeads(new Set(filteredLeads.map(l => l.id)));
  };

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold text-gray-900">Leads</h1>
        <div className="flex space-x-3">
          <button className="btn-secondary text-sm">Import CSV</button>
          <button className="btn-primary text-sm">+ Add Lead</button>
        </div>
      </div>

      {/* Filters */}
      <div className="card">
        <div className="flex flex-wrap gap-3 items-center">
          <input
            type="text"
            placeholder="Search leads..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="flex-1 min-w-[200px] px-3 py-2 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="px-3 py-2 border rounded-lg text-sm"
          >
            <option value="all">All Status</option>
            <option value="new">New</option>
            <option value="contacted">Contacted</option>
            <option value="qualified">Qualified</option>
            <option value="nurturing">Nurturing</option>
            <option value="converted">Converted</option>
          </select>
          {selectedLeads.size > 0 && (
            <div className="flex items-center space-x-2 border-l pl-3">
              <span className="text-sm text-gray-600">{selectedLeads.size} selected</span>
              <button className="text-xs btn-secondary py-1 px-2">Enrich</button>
              <button className="text-xs btn-secondary py-1 px-2">Score</button>
              <button className="text-xs btn-secondary py-1 px-2">Tag</button>
              <button className="text-xs text-red-600 hover:underline">Delete</button>
            </div>
          )}
        </div>
      </div>

      {/* Table */}
      <div className="card p-0 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b">
            <tr>
              <th className="px-4 py-3 text-left">
                <input type="checkbox" onChange={selectAll} checked={selectedLeads.size === filteredLeads.length && filteredLeads.length > 0} className="rounded" />
              </th>
              <th className="px-4 py-3 text-left font-medium text-gray-600">Lead</th>
              <th className="px-4 py-3 text-left font-medium text-gray-600">Company</th>
              <th className="px-4 py-3 text-left font-medium text-gray-600">Score</th>
              <th className="px-4 py-3 text-left font-medium text-gray-600">Status</th>
              <th className="px-4 py-3 text-left font-medium text-gray-600">Source</th>
              <th className="px-4 py-3 text-left font-medium text-gray-600">Enriched</th>
              <th className="px-4 py-3 text-left font-medium text-gray-600">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {filteredLeads.map((lead) => (
              <tr key={lead.id} className="hover:bg-gray-50">
                <td className="px-4 py-3">
                  <input type="checkbox" checked={selectedLeads.has(lead.id)} onChange={() => toggleSelect(lead.id)} className="rounded" />
                </td>
                <td className="px-4 py-3">
                  <div className="font-medium text-gray-900">{lead.name}</div>
                  <div className="text-gray-500 text-xs">{lead.email}</div>
                </td>
                <td className="px-4 py-3">
                  <div className="text-gray-900">{lead.company}</div>
                  <div className="text-gray-500 text-xs">{lead.title}</div>
                </td>
                <td className="px-4 py-3">
                  <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-bold ${
                    lead.score >= 75 ? 'bg-red-100 text-red-800' :
                    lead.score >= 45 ? 'bg-yellow-100 text-yellow-800' :
                    'bg-blue-100 text-blue-800'
                  }`}>{lead.score}</span>
                </td>
                <td className="px-4 py-3">
                  <span className="capitalize text-gray-700 text-xs bg-gray-100 px-2 py-0.5 rounded">{lead.status}</span>
                </td>
                <td className="px-4 py-3 text-gray-600 text-xs">{lead.source.replace('_', ' ')}</td>
                <td className="px-4 py-3">
                  {lead.enriched ? (
                    <span className="text-green-600 text-xs font-medium">Yes</span>
                  ) : (
                    <button className="text-blue-600 text-xs hover:underline">Enrich</button>
                  )}
                </td>
                <td className="px-4 py-3">
                  <button className="text-gray-400 hover:text-gray-600">
                    <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20"><path d="M10 6a2 2 0 110-4 2 2 0 010 4zM10 12a2 2 0 110-4 2 2 0 010 4zM10 18a2 2 0 110-4 2 2 0 010 4z" /></svg>
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <div className="px-4 py-3 border-t bg-gray-50 flex justify-between items-center">
          <span className="text-sm text-gray-500">Showing {filteredLeads.length} of {mockLeads.length} leads</span>
          <div className="flex space-x-2">
            <button className="px-3 py-1 border rounded text-sm">Previous</button>
            <button className="px-3 py-1 border rounded text-sm bg-blue-600 text-white">1</button>
            <button className="px-3 py-1 border rounded text-sm">2</button>
            <button className="px-3 py-1 border rounded text-sm">Next</button>
          </div>
        </div>
      </div>
    </div>
  );
}
