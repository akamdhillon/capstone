import { useCallback, useEffect } from 'react';
import { AppProvider, useApp } from './context/AppContext';
import { API_BASE_URL } from './config';
import type { ViewType } from './context/AppContext';
import { IdleView } from './views/IdleView';
import { DashboardView } from './views/DashboardView';
import { AnalysisView } from './views/AnalysisView';
import { EnrollmentView } from './views/EnrollmentView';
import { PostureView } from './views/PostureView';
import { DailySummaryView } from './views/DailySummaryView';
import { EyeCheckView } from './views/EyeCheckView';
import { SkinCheckView } from './views/SkinCheckView';
import { VoiceIndicator } from './components/VoiceIndicator';
import { DebugOverlay } from './components/DebugOverlay';
import { useVoiceWebSocket } from './hooks/useVoiceWebSocket';
import './index.css';

function AppContent() {
  const { currentView, setView, setTriggerRecognition, setCurrentUser, setGreeting } = useApp();

  // Space bar: skip "Hey Clarity" and go straight to listening (testing)
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.code !== 'Space' || e.repeat) return;
      const target = e.target as HTMLElement;
      if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable) return;
      fetch(`${API_BASE_URL}/api/voice/trigger`, { method: 'POST' }).catch(() => {});
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, []);

  useVoiceWebSocket(useCallback((data) => {
    if (data.navigate) {
      const validViews: ViewType[] = ['idle', 'dashboard', 'analysis', 'enrollment', 'posture', 'summary', 'eyes', 'skin'];
      if (validViews.includes(data.navigate as ViewType)) {
        setView(data.navigate as ViewType);
      }
    }
    if (data.action === 'recognize') {
      setTriggerRecognition(true);
    }
    if (data.action === 'recognize_result') {
      setTriggerRecognition(false);
      if (data.match && data.display_name) {
        setGreeting(`Good day, ${data.display_name}.`);
        setCurrentUser({
          id: (data.user_id as string) ?? crypto.randomUUID(),
          name: data.display_name as string,
          created_at: new Date().toISOString(),
        });
        setView('dashboard');
      }
    }
  }, [setView, setTriggerRecognition, setCurrentUser, setGreeting]));

  return (
    <>
      <VoiceIndicator />
      <DebugOverlay />

      {(() => {
        switch (currentView) {
          case 'idle':
            return <IdleView />;
          case 'dashboard':
            return <DashboardView />;
          case 'analysis':
            return <AnalysisView />;
          case 'enrollment':
            return <EnrollmentView />;
          case 'posture':
            return <PostureView />;
          case 'summary':
            return <DailySummaryView />;
          case 'eyes':
            return <EyeCheckView />;
          case 'skin':
            return <SkinCheckView />;
          default:
            return <IdleView />;
        }
      })()}
    </>
  );
}

function App() {
  return (
    <AppProvider>
      <AppContent />
    </AppProvider>
  );
}

export default App;
