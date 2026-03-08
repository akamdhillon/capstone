import { useCallback } from 'react';
import { AppProvider, useApp } from './context/AppContext';
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
import { useVoiceWebSocket } from './hooks/useVoiceWebSocket';
import './index.css';

function AppContent() {
  const { currentView, setView, setTriggerRecognition } = useApp();

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
  }, [setView, setTriggerRecognition]));

  return (
    <>
      <VoiceIndicator />

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
