import type { Metadata } from 'next';
import './globals.css';
import { Navbar } from '@/components/Navbar';

export const metadata: Metadata = {
  title: 'Interview Copilot AI',
  description: 'Personal real-time AI interview assistant',
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-zinc-950 text-zinc-100 antialiased font-sans selection:bg-emerald-500/20 selection:text-emerald-300">
        <Navbar />
        <main className="flex-1">{children}</main>
      </body>
    </html>
  );
}
