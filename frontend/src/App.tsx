import React from 'react';
import { AuthProvider } from './context/AuthContext';
import { ChatProvider } from './context/ChatContext';
import { AppShell } from './components/layout/AppShell';

export const App: React.FC = () => {
  return (
    <AuthProvider>
      <ChatProvider>
        <AppShell />
      </ChatProvider>
    </AuthProvider>
  );
};

export default App;
