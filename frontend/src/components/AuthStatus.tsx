'use client';

import { signIn, signOut, useSession } from 'next-auth/react';
import { LogIn, LogOut, User } from 'lucide-react';

export default function AuthStatus() {
  const { data: session, status } = useSession();

  if (status === 'loading') {
    return <div className="animate-pulse w-24 h-8 bg-white/5 rounded-md"></div>;
  }

  if (session) {
    return (
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2 text-xs font-mono text-zinc-400 bg-white/5 px-3 py-1.5 rounded-full border border-white/10">
          <User className="w-3.5 h-3.5 text-[#00B2FF]" />
          <span>{session.user?.email || session.user?.name}</span>
        </div>
        <button
          onClick={() => signOut()}
          className="flex items-center gap-2 px-3 py-1.5 text-xs font-medium text-zinc-300 hover:text-white hover:bg-white/10 rounded-md transition-colors"
        >
          <LogOut className="w-3.5 h-3.5" />
          Sign Out
        </button>
      </div>
    );
  }

  return (
    <button
      onClick={() => signIn()}
      className="flex items-center gap-2 px-4 py-1.5 text-sm font-semibold text-white bg-gradient-to-r from-[#00B2FF] to-[#0055FF] hover:from-[#33C4FF] hover:to-[#3377FF] rounded-md transition-all shadow-lg shadow-blue-900/20"
    >
      <LogIn className="w-4 h-4" />
      Sign In
    </button>
  );
}
