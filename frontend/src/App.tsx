import { AppProvider, useApp } from './context/AppContext';
import { IdleView } from './views/IdleView';
import { AnalysisView } from './views/AnalysisView';
import { EnrollmentView } from './views/EnrollmentView';
import { VoiceIndicator } from './components/VoiceIndicator';
import './index.css';

function AppContent() {
  const { currentView } = useApp();

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
