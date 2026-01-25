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

// Auto-detect dark mode from system preference (PatternFly 6)
function applySystemTheme() {
  const darkModeQuery = window.matchMedia('(prefers-color-scheme: dark)');
  
  const updateTheme = (isDark: boolean) => {
    if (isDark) {
      document.documentElement.classList.add('pf-v6-theme-dark');
    } else {
      document.documentElement.classList.remove('pf-v6-theme-dark');
    }
  };
  
  // Apply initial theme
  updateTheme(darkModeQuery.matches);
  
  // Listen for system preference changes
  darkModeQuery.addEventListener('change', (e) => updateTheme(e.matches));
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
