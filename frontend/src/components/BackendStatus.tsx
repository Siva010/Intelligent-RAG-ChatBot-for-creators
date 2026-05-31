'use client';

import { useState, useEffect } from 'react';

export default function BackendStatus() {
  const [status, setStatus] = useState<'checking' | 'healthy' | 'error'>('checking');

  useEffect(() => {
    const checkHealth = async () => {
      try {
        const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000'}/health`);
        if (res.ok) {
          const data = await res.json();
          setStatus(data.celery_active ? 'healthy' : 'error');
        } else {
          setStatus('error');
        }
      } catch {
        setStatus('error');
      }
    };
    checkHealth();
    const interval = setInterval(checkHealth, 30000);
    return () => clearInterval(interval);
  }, []);

  if (status === 'checking') {
    return <span className="w-1.5 h-1.5 rounded-full bg-zinc-500 animate-pulse" title="Checking backend..." />;
  }
  
  if (status === 'healthy') {
    return <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" title="Systems operational" />;
  }

  return <span className="w-1.5 h-1.5 rounded-full bg-red-500 animate-pulse" title="Celery Worker Offline" />;
}
