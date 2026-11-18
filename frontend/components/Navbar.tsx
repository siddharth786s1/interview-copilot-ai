'use client';

import React from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  Mic2,
  LayoutDashboard,
  FileText,
  BookOpen,
  History,
  GraduationCap,
  Settings as SettingsIcon,
  Activity,
} from 'lucide-react';

const NAV_ITEMS = [
  { href: '/', label: 'Dashboard', icon: LayoutDashboard },
  { href: '/audio-test', label: 'Audio Test', icon: Mic2 },
  { href: '/resume', label: 'Resume', icon: FileText },
  { href: '/knowledge-base', label: 'Knowledge Base', icon: BookOpen },
  { href: '/history', label: 'History', icon: History },
  { href: '/mock', label: 'Mock Interview', icon: GraduationCap },
  { href: '/settings', label: 'Settings', icon: SettingsIcon },
];

export function Navbar() {
  const pathname = usePathname();

  return (
    <header className="sticky top-0 z-40 w-full border-b border-zinc-800 bg-zinc-950/80 backdrop-blur">
      <div className="flex h-16 items-center justify-between px-6">
        <div className="flex items-center gap-6">
          <Link href="/" className="flex items-center gap-2.5">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
              <Mic2 className="h-5 w-5" />
            </div>
            <div>
              <span className="font-semibold text-zinc-100 text-sm tracking-tight">Interview Copilot AI</span>
              <span className="block text-[10px] text-zinc-500 uppercase font-mono tracking-wider">Personal Assistant</span>
            </div>
          </Link>

          <nav className="hidden md:flex items-center gap-1 pl-4 border-l border-zinc-800">
            {NAV_ITEMS.map((item) => {
              const Icon = item.icon;
              const isActive = pathname === item.href;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`flex items-center gap-2 px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
                    isActive
                      ? 'bg-zinc-800 text-zinc-100 shadow-sm'
                      : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-900/60'
                  }`}
                >
                  <Icon className="h-3.5 w-3.5" />
                  {item.label}
                </Link>
              );
            })}
          </nav>
        </div>

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-950/40 border border-emerald-800/40 text-[11px] text-emerald-400 font-mono">
            <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
            <Activity className="h-3 w-3" />
            <span>Local Engine Ready</span>
          </div>
        </div>
      </div>
    </header>
  );
}
