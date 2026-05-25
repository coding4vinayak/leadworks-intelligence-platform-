'use client';

const timelineEvents = [
  { id: '1', type: 'lead_created', title: 'Lead Created', detail: 'Imported via LinkedIn scrape', time: '2024-01-15 09:15', icon: '➕', color: 'bg-blue-500' },
  { id: '2', type: 'enriched', title: 'Auto-Enriched', detail: 'Added: company size, tech stack, funding data', time: '2024-01-15 09:16', icon: '✨', color: 'bg-purple-500' },
  { id: '3', type: 'scored', title: 'Score: 72/100', detail: 'Category: Warm. Signals: VP title, mid-market, tech match', time: '2024-01-15 09:16', icon: '📊', color: 'bg-yellow-500' },
  { id: '4', type: 'email_sent', title: 'Email Sent', detail: 'Subject: "Quick question about your roadmap"', time: '2024-01-16 10:00', icon: '📧', color: 'bg-green-500' },
  { id: '5', type: 'email_opened', title: 'Email Opened', detail: 'Opened 3 times (San Francisco, iPhone)', time: '2024-01-16 14:23', icon: '👁️', color: 'bg-green-400' },
  { id: '6', type: 'page_visited', title: 'Visited Website', detail: 'Pricing page (3 min), Features page (1 min)', time: '2024-01-16 14:30', icon: '🌐', color: 'bg-indigo-500' },
  { id: '7', type: 'scored', title: 'Score Updated: 72 → 87', detail: 'Signals: email opened, pricing page, return visitor', time: '2024-01-16 14:31', icon: '🔥', color: 'bg-red-500' },
  { id: '8', type: 'slack_alert', title: 'Slack Alert Sent', detail: 'Hot lead alert sent to #sales-alerts', time: '2024-01-16 14:31', icon: '💬', color: 'bg-pink-500' },
  { id: '9', type: 'assigned', title: 'Assigned to Alice', detail: 'Auto-routed via score-based strategy', time: '2024-01-16 14:32', icon: '👤', color: 'bg-teal-500' },
  { id: '10', type: 'email_replied', title: 'Lead Replied!', detail: '"Sure, I have 15 min Thursday. Calendar link?"', time: '2024-01-17 09:45', icon: '🎉', color: 'bg-green-600' },
  { id: '11', type: 'meeting_booked', title: 'Meeting Booked', detail: 'Thursday Jan 18, 2:00 PM PST - Demo call', time: '2024-01-17 10:02', icon: '📅', color: 'bg-blue-600' },
  { id: '12', type: 'status_changed', title: 'Status → Qualified', detail: 'Moved to qualified pipeline stage', time: '2024-01-17 10:05', icon: '✅', color: 'bg-green-700' },
];

interface Props {
  leadId?: string;
}

export default function LeadTimeline({ leadId }: Props) {
  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <h2 className="text-lg font-semibold text-gray-900">Activity Timeline</h2>
        <div className="flex space-x-2">
          <select className="text-xs border rounded px-2 py-1">
            <option>All Events</option>
            <option>Emails</option>
            <option>Score Changes</option>
            <option>Page Visits</option>
            <option>System Events</option>
          </select>
        </div>
      </div>

      <div className="relative">
        {/* Timeline line */}
        <div className="absolute left-4 top-0 bottom-0 w-0.5 bg-gray-200"></div>

        <div className="space-y-4">
          {timelineEvents.map((event) => (
            <div key={event.id} className="relative flex items-start space-x-4 ml-1">
              {/* Dot */}
              <div className={`relative z-10 flex items-center justify-center w-7 h-7 rounded-full ${event.color} text-white text-xs`}>
                {event.icon}
              </div>

              {/* Content */}
              <div className="flex-1 min-w-0 bg-white border border-gray-100 rounded-lg p-3 shadow-sm hover:shadow-md transition-shadow">
                <div className="flex justify-between items-start">
                  <div>
                    <p className="font-medium text-sm text-gray-900">{event.title}</p>
                    <p className="text-xs text-gray-500 mt-0.5">{event.detail}</p>
                  </div>
                  <span className="text-xs text-gray-400 whitespace-nowrap ml-2">
                    {new Date(event.time).toLocaleString('en-US', {
                      month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'
                    })}
                  </span>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
