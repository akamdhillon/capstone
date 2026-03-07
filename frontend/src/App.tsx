import { useEffect } from 'react';
import { AppProvider, useApp } from './context/AppContext';
import type { ViewType } from './context/AppContext';
import { IdleView } from './views/IdleView';
import { AnalysisView } from './views/AnalysisView';
import { EnrollmentView } from './views/EnrollmentView';
import { PostureView } from './views/PostureView';
import { VoiceIndicator } from './components/VoiceIndicator';
import './index.css';

function AppContent() {
  const { currentView, setView, setTriggerRecognition } = useApp();

  // ── Global WebSocket listener for voice-driven navigation ──
  useEffect(() => {
    const ws = new WebSocket('ws://localhost:8000/ws/voice');
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.navigate) {
          const validViews: ViewType[] = ['idle', 'analysis', 'enrollment', 'posture'];
          if (validViews.includes(data.navigate)) {
            setView(data.navigate as ViewType);
          }
        }

        // Handle voice action triggers
        if (data.action === 'recognize') {
          setTriggerRecognition(true);
        }
      } catch { /* ignore non-JSON */ }
    };
    ws.onerror = () => { /* silently reconnect handled by browser */ };
    return () => ws.close();
  }, [setView, setTriggerRecognition]);

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
