import { useState } from 'react';
import { Navbar } from './components/Navbar';
import { Footer } from './components/Footer';
import { MissionControlDashboard } from './screens/MissionControlDashboard';
import { LiveSimulationControl } from './screens/LiveSimulationControl';
import { OptimizationEngine } from './screens/OptimizationEngine';
import { NetworkDiagnostics } from './screens/NetworkDiagnostics';
import { SystemSettings } from './screens/SystemSettings';

export function App() {
  const [currentTab, setCurrentTab] = useState<string>('dashboard');

  const [startLocation, setStartLocation] = useState<{ name: string; coords: [number, number] }>({
    name: 'Mumbai, Maharashtra, India',
    coords: [19.0760, 72.8777]
  });

  const [qpsoParams, setQpsoParams] = useState({
    beta_start: 1.0,
    swarm_size: 30,
    max_iter: 300,
    plateau_window: 50
  });

  const [optimizationResult, setOptimizationResult] = useState<any>(null);

  const handleStartOptimizationFromNav = () => {
    setCurrentTab('live-simulation');
  };

  return (
    <div className="min-h-screen bg-[#161120] text-[#e9def5] flex flex-col justify-between">
      <div>
        <Navbar
          currentTab={currentTab}
          onSelectTab={(tab) => setCurrentTab(tab)}
          onStartOptimization={handleStartOptimizationFromNav}
        />

        <main>
          {currentTab === 'dashboard' && (
            <MissionControlDashboard
              optimizationResult={optimizationResult}
              startLocation={startLocation}
              onNavigateToSimulation={() => setCurrentTab('live-simulation')}
              onNavigateToEngine={() => setCurrentTab('optimization-engine')}
            />
          )}

          {currentTab === 'live-simulation' && (
            <LiveSimulationControl
              startLocation={startLocation}
              setStartLocation={setStartLocation}
              optimizationResult={optimizationResult}
              setOptimizationResult={setOptimizationResult}
              qpsoParams={qpsoParams}
            />
          )}

          {currentTab === 'optimization-engine' && (
            <OptimizationEngine
              qpsoParams={qpsoParams}
              setQpsoParams={setQpsoParams}
              onDeploy={() => setCurrentTab('live-simulation')}
            />
          )}

          {currentTab === 'network-health' && (
            <NetworkDiagnostics />
          )}

          {currentTab === 'system-settings' && (
            <SystemSettings />
          )}
        </main>
      </div>

      <Footer />
    </div>
  );
}

export default App;
