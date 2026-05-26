'use client';

const stages = [
  { name: 'New', count: 142, value: '$0', color: 'bg-blue-500', leads: [
    { name: 'Alex Johnson', company: 'DevTools', score: 56 },
    { name: 'Maria Garcia', company: 'GrowthLab', score: 74 },
    { name: 'Tom Roberts', company: 'ScaleMkt', score: 81 },
  ]},
  { name: 'Contacted', count: 89, value: '$45K', color: 'bg-yellow-500', leads: [
    { name: 'James Wilson', company: 'DataFlow', score: 87 },
    { name: 'Priya Patel', company: 'FastGrowth', score: 79 },
  ]},
  { name: 'Qualified', count: 54, value: '$120K', color: 'bg-orange-500', leads: [
    { name: 'Sarah Chen', company: 'TechCorp', score: 92 },
    { name: 'Lisa Park', company: 'AI Solutions', score: 95 },
  ]},
  { name: 'Nurturing', count: 32, value: '$80K', color: 'bg-purple-500', leads: [
    { name: 'David Kim', company: 'CloudNine', score: 68 },
  ]},
  { name: 'Converted', count: 18, value: '$250K', color: 'bg-green-500', leads: [
    { name: 'Mike Brown', company: 'Acme Corp', score: 98 },
  ]},
];

export default function Pipeline() {
  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Pipeline</h1>
          <p className="text-gray-500 text-sm mt-1">Drag & drop leads between stages</p>
        </div>
        <div className="flex items-center space-x-4">
          <div className="text-right">
            <p className="text-sm text-gray-500">Total Pipeline Value</p>
            <p className="text-2xl font-bold text-gray-900">$495K</p>
          </div>
        </div>
      </div>

      {/* Pipeline Columns */}
      <div className="flex space-x-4 overflow-x-auto pb-4">
        {stages.map((stage) => (
          <div key={stage.name} className="flex-shrink-0 w-72">
            {/* Stage Header */}
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center space-x-2">
                <div className={`w-3 h-3 rounded-full ${stage.color}`}></div>
                <h3 className="font-semibold text-gray-900">{stage.name}</h3>
                <span className="bg-gray-200 text-gray-600 text-xs px-2 py-0.5 rounded-full">{stage.count}</span>
              </div>
              <span className="text-sm text-gray-500">{stage.value}</span>
            </div>

            {/* Cards */}
            <div className="space-y-2">
              {stage.leads.map((lead, i) => (
                <div key={i} className="bg-white rounded-lg border border-gray-200 p-3 shadow-sm hover:shadow-md transition-shadow cursor-pointer">
                  <div className="flex justify-between items-start">
                    <div>
                      <p className="font-medium text-gray-900 text-sm">{lead.name}</p>
                      <p className="text-gray-500 text-xs">{lead.company}</p>
                    </div>
                    <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${
                      lead.score >= 75 ? 'bg-red-100 text-red-800' :
                      lead.score >= 45 ? 'bg-yellow-100 text-yellow-800' :
                      'bg-blue-100 text-blue-800'
                    }`}>{lead.score}</span>
                  </div>
                </div>
              ))}
              {/* Add card button */}
              <button className="w-full py-2 border-2 border-dashed border-gray-200 rounded-lg text-gray-400 text-sm hover:border-blue-300 hover:text-blue-500 transition-colors">
                + Add lead
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
