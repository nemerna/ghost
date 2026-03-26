/**
 * Application entry point
 */

import React from 'react';
import ReactDOM from 'react-dom/client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter } from 'react-router-dom';

// PatternFly styles
import '@patternfly/react-core/dist/styles/base.css';
import '@patternfly/patternfly/patternfly.css';

import { AuthProvider } from '@/auth';
import App from './App';

// Apply theme on startup: saved preference takes precedence over system preference.
function applySystemTheme() {
  const saved = localStorage.getItem('theme');
  const systemDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
  const isDark = saved === 'dark' || (saved === null && systemDark);

  document.documentElement.classList.toggle('pf-v6-theme-dark', isDark);

  // Only follow system changes when user has no saved preference
  if (saved === null) {
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
      document.documentElement.classList.toggle('pf-v6-theme-dark', e.matches);
    });
  }
}

applySystemTheme();

// Create React Query client
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000, // 5 minutes
      retry: 1,
    },
  },
});

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AuthProvider>
          <App />
        </AuthProvider>
      </BrowserRouter>
    </QueryClientProvider>
  </React.StrictMode>
);
