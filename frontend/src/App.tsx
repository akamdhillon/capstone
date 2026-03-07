import { useCallback } from 'react';
import { AppProvider, useApp } from './context/AppContext';
import type { ViewType } from './context/AppContext';
import { IdleView } from './views/IdleView';
import { AnalysisView } from './views/AnalysisView';
import { EnrollmentView } from './views/EnrollmentView';
import { PostureView } from './views/PostureView';
import { VoiceIndicator } from './components/VoiceIndicator';
import { useVoiceWebSocket } from './hooks/useVoiceWebSocket';
import './index.css';

function AppContent() {
  const { currentView, setView, setTriggerRecognition } = useApp();

  // ── Global WebSocket listener for voice-driven navigation ──
  useVoiceWebSocket(useCallback((data) => {
    if (data.navigate) {
      const validViews: ViewType[] = ['idle', 'analysis', 'enrollment', 'posture'];
      if (validViews.includes(data.navigate as ViewType)) {
        setView(data.navigate as ViewType);
      }
    }
    if (data.action === 'recognize') {
      setTriggerRecognition(true);
    }
  }, [setView, setTriggerRecognition]));

  // Render the appropriate view
  return (
    <>
      <VoiceIndicator />
      {(() => {
        switch (currentView) {
          case 'idle':
            return <IdleView />;
          case 'analysis':
            return <AnalysisView />;
          case 'enrollment':
            return <EnrollmentView />;
          case 'posture':
            return <PostureView />;
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
