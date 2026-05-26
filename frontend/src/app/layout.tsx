import './globals.css';
import { Toaster } from 'react-hot-toast';

export const metadata = {
  title: 'Leadworks Intelligence Platform',
  description: 'AI-powered lead intelligence, scraping, enrichment, and automation',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="h-full bg-gray-50">
      <body className="h-full">
        <Toaster position="top-right" />
        {children}
      </body>
    </html>
  );
}
