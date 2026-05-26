'use client';
import { useState } from 'react';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  suggestions?: string[];
}

const initialMessages: Message[] = [
  {
    id: '1',
    role: 'assistant',
    content: "Hey! I'm your Leadworks AI assistant. I can help you find leads, analyze your pipeline, generate outreach, and more. What can I help you with?",
    timestamp: new Date().toISOString(),
    suggestions: ['Show my hot leads', "How's my pipeline?", 'Who should I contact today?'],
  },
];

export default function ChatAssistant() {
  const [messages, setMessages] = useState<Message[]>(initialMessages);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const sendMessage = async (text: string) => {
    if (!text.trim()) return;

    const userMsg: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: text,
      timestamp: new Date().toISOString(),
    };
    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setIsLoading(true);

    // Simulate AI response (in production: call /api/v1/chat/message)
    setTimeout(() => {
      const aiMsg: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: getResponse(text),
        timestamp: new Date().toISOString(),
        suggestions: ['Tell me more', 'Show details', 'What else?'],
      };
      setMessages(prev => [...prev, aiMsg]);
      setIsLoading(false);
    }, 1000);
  };

  return (
    <div className="flex flex-col h-[600px] card p-0 overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 border-b bg-gradient-to-r from-blue-600 to-indigo-600 text-white">
        <div className="flex items-center space-x-2">
          <div className="w-8 h-8 bg-white/20 rounded-full flex items-center justify-center text-sm">AI</div>
          <div>
            <h3 className="font-semibold text-sm">Leadworks Assistant</h3>
            <p className="text-xs text-blue-100">Ask anything about your leads</p>
          </div>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((msg) => (
          <div key={msg.id} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-[80%] rounded-2xl px-4 py-2 ${
              msg.role === 'user'
                ? 'bg-blue-600 text-white rounded-br-md'
                : 'bg-gray-100 text-gray-900 rounded-bl-md'
            }`}>
              <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
              {msg.suggestions && (
                <div className="flex flex-wrap gap-1 mt-2">
                  {msg.suggestions.map((s, i) => (
                    <button
                      key={i}
                      onClick={() => sendMessage(s)}
                      className="text-xs bg-white/80 text-blue-700 px-2 py-1 rounded-full hover:bg-white transition-colors border border-blue-200"
                    >
                      {s}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}
        {isLoading && (
          <div className="flex justify-start">
            <div className="bg-gray-100 rounded-2xl px-4 py-3 rounded-bl-md">
              <div className="flex space-x-1">
                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"></div>
                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{animationDelay: '0.1s'}}></div>
                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{animationDelay: '0.2s'}}></div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Input */}
      <div className="p-3 border-t bg-white">
        <div className="flex space-x-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && sendMessage(input)}
            placeholder="Ask about leads, pipeline, or get recommendations..."
            className="flex-1 px-4 py-2 border rounded-full text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <button
            onClick={() => sendMessage(input)}
            disabled={!input.trim() || isLoading}
            className="bg-blue-600 text-white px-4 py-2 rounded-full text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
          >
            Send
          </button>
        </div>
      </div>
    </div>
  );
}

function getResponse(msg: string): string {
  const lower = msg.toLowerCase();
  if (lower.includes('hot') || lower.includes('best')) {
    return `Here are your top hot leads:\n\n1. Sarah Chen - VP Engineering @ TechCorp (Score: 92)\n   Visited pricing 3x, opened all emails\n   Action: Book demo ASAP\n\n2. Lisa Park - CEO @ AI Solutions (Score: 95)\n   Referred by customer, Series B funded\n   Action: Send personalized intro\n\n3. James Wilson - CTO @ DataFlow (Score: 87)\n   Replied asking about integrations\n   Action: Schedule technical deep-dive`;
  }
  if (lower.includes('pipeline') || lower.includes('stats')) {
    return `Pipeline This Week:\n\n- New leads: 47 (+12%)\n- Hot leads: 12 (8 uncontacted!)\n- Emails sent: 234 | Open: 42% | Reply: 8.5%\n- Meetings booked: 6\n- Pipeline value: $485K (+$65K)\n\nAlert: 8 hot leads haven't been contacted yet!`;
  }
  if (lower.includes('contact') || lower.includes('recommend') || lower.includes('who')) {
    return `Today's Priority Actions:\n\n1. Follow up with James Wilson - replied 2 days ago\n2. Enrich 15 new LinkedIn leads from yesterday\n3. Re-engage David Kim - quiet for 7 days\n4. Call Maria Garcia - visited demo page twice today\n\nBest send time: 10:00 AM PST`;
  }
  return `I can help with:\n\n- "Show hot leads" - Find your best prospects\n- "How's my pipeline?" - Get stats and insights\n- "Who should I contact?" - Get daily priorities\n- "Explain score for [lead]" - Understand scoring\n- "Write email to [lead]" - Generate outreach\n\nWhat would you like to know?`;
}
