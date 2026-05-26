'use client';
import { useState } from 'react';
import Sidebar from '@/components/Sidebar';
import Dashboard from '@/components/Dashboard';
import LeadsTable from '@/components/LeadsTable';
import Pipeline from '@/components/Pipeline';
import ScraperPanel from '@/components/ScraperPanel';
import Connectors from '@/components/Connectors';
import Campaigns from '@/components/Campaigns';
import Settings from '@/components/Settings';
import ChatAssistant from '@/components/ChatAssistant';

export default function Home() {
  const [activePage, setActivePage] = useState('dashboard');

  const renderPage = () => {
    switch (activePage) {
      case 'dashboard': return <Dashboard />;
      case 'leads': return <LeadsTable />;
      case 'pipeline': return <Pipeline />;
      case 'scrapers': return <ScraperPanel />;
      case 'connectors': return <Connectors />;
      case 'campaigns': return <Campaigns />;
      case 'chat': return <ChatAssistant />;
      case 'settings': return <Settings />;
      default: return <Dashboard />;
    }
  };

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar activePage={activePage} onNavigate={setActivePage} />
      <main className="flex-1 overflow-y-auto bg-gray-50">
        <div className="p-6 max-w-[1600px] mx-auto">
          {renderPage()}
        </div>
      </main>
    </div>
  );
}
