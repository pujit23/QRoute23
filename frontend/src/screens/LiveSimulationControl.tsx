import React, { useState } from 'react';
import { Play, RefreshCw, Layers, Truck, Clock, ShieldAlert } from 'lucide-react';
import { RouteMap } from '../components/RouteMap';
import { LocationSearchInput } from '../components/LocationSearchInput';
import { runOptimization } from '../api/client';

interface LiveSimulationProps {
  startLocation: { name: string; coords: [number, number] };
  setStartLocation: (loc: { name: string; coords: [number, number] }) => void;
  optimizationResult: any;
  setOptimizationResult: (res: any) => void;
  qpsoParams: any;
}

export const LiveSimulationControl: React.FC<LiveSimulationProps> = ({
  startLocation,
  setStartLocation,
  optimizationResult,
  setOptimizationResult,
  qpsoParams
}) => {
  const [selectedPreset, setSelectedPreset] = useState<string>('manhattan-core');
  const [destinationLocation, setDestinationLocation] = useState<{ name: string; coords: [number, number] }>({
    name: 'New Delhi, Delhi, India',
    coords: [28.6139, 77.2090]
  });
  const [vehicleCount, setVehicleCount] = useState<number>(1);
  const [roundTrip] = useState<boolean>(false);
  const [loading, setLoading] = useState<boolean>(false);

  const presets = [
    { id: 'manhattan-core', label: 'Simulating: Manhattan Core', status: 'ACTIVE', color: 'text-[#ff5719]' },
    { id: 'london-grid', label: 'Simulating: London Grid', status: 'STANDBY', color: 'text-[#e6beb2]/60' },
    { id: 'tokyo-hub', label: 'Simulating: Tokyo Hub', status: 'STANDBY', color: 'text-[#e6beb2]/60' }
  ];

  const [intermediateStops, setIntermediateStops] = useState<{ name: string; coords: [number, number] }[]>([]);

  const handleAddStop = () => {
    setIntermediateStops([
      ...intermediateStops,
      { name: 'Central Park, NY', coords: [40.785091, -73.968285] }
    ]);
  };

  const handleRemoveStop = (idx: number) => {
    setIntermediateStops(intermediateStops.filter((_, i) => i !== idx));
  };

  const handleUpdateStop = (idx: number, loc: { name: string; coords: [number, number] }) => {
    const updated = [...intermediateStops];
    updated[idx] = loc;
    setIntermediateStops(updated);
  };

  const handleRunOptimization = async (presetOverride?: string) => {
    setLoading(true);
    try {
      if (presetOverride) {
        // Run preset optimization
        const res = await runOptimization({
          preset: presetOverride,
          vehicle_count: vehicleCount,
          round_trip: roundTrip,
          qpso_params: qpsoParams
        });
        setOptimizationResult(res);
      } else {
        // Build custom stops list from intermediateStops + destinationLocation
        const allStops = [
          ...intermediateStops,
          { name: destinationLocation.name, coords: destinationLocation.coords }
        ];

        const res = await runOptimization({
          start_location: startLocation,
          stops: allStops,
          vehicle_count: vehicleCount,
          round_trip: roundTrip,
          qpso_params: qpsoParams
        });
        setOptimizationResult(res);
      }
    } catch (err) {
      console.error("Optimization error:", err);
    } finally {
      setLoading(false);
    }
  };

  const metrics = optimizationResult?.metrics || {
    total_distance_km: 142.8,
    total_time_min: 118,
    fuel_liters: 11.9,
    cost_inr: 1142,
    time_saved_hrs: 2.4,
    co2_reduction_kg: 18.5
  };

  return (
    <div className="max-w-[1440px] mx-auto px-6 py-8 space-y-6">
      
      {/* Search Header Bar (Section 4.1 Global Search) */}
      <div className="quantum-glow-card p-4 rounded-xl space-y-4">
        <div className="flex flex-col md:flex-row items-center gap-4">
          <div className="w-full md:w-1/2">
            <LocationSearchInput
              label="Origin (From)"
              placeholder="Type any origin address or city on Earth..."
              value={startLocation.name}
              onSelectLocation={(loc) => setStartLocation(loc)}
            />
          </div>
          <div className="w-full md:w-1/2">
            <LocationSearchInput
              label="Destination (To)"
              placeholder="Type destination..."
              value={destinationLocation.name}
              onSelectLocation={(loc) => setDestinationLocation(loc)}
            />
          </div>
          <div className="w-full md:w-auto flex items-end gap-2">
            <button
              onClick={() => handleRunOptimization()}
              disabled={loading}
              className="w-full md:w-auto btn-ember-gradient px-6 py-2.5 text-xs uppercase font-semibold flex items-center justify-center gap-2 mt-4 md:mt-0"
            >
              {loading ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4 fill-white" />}
              <span>{loading ? 'Optimizing...' : 'Run Quantum Router'}</span>
            </button>
          </div>
        </div>

        {/* Intermediate Waypoints (if any) */}
        {intermediateStops.length > 0 && (
          <div className="space-y-3 pt-3 border-t border-[#5c4037]/30">
            <div className="text-xs font-mono text-[#ffb59e] uppercase">Intermediate Waypoints</div>
            {intermediateStops.map((stop, idx) => (
              <div key={idx} className="flex items-center gap-3">
                <div className="flex-1">
                  <LocationSearchInput
                    label={`Waypoint ${idx + 1}`}
                    placeholder="Type intermediate stop address..."
                    value={stop.name}
                    onSelectLocation={(loc) => handleUpdateStop(idx, loc)}
                  />
                </div>
                <button
                  onClick={() => handleRemoveStop(idx)}
                  className="mt-5 p-2 rounded-lg bg-[#110b1b] border border-[#ff4444]/40 text-[#ff6666] hover:bg-[#ff4444]/10 transition"
                  title="Remove Waypoint"
                >
                  ✕
                </button>
              </div>
            ))}
          </div>
        )}

        <div className="flex justify-start">
          <button
            onClick={handleAddStop}
            className="text-xs font-mono text-[#9dcaff] hover:text-[#e9def5] flex items-center gap-1.5 transition"
          >
            <span>+ Add Intermediate Waypoint</span>
          </button>
        </div>
      </div>

      {/* Main Two-Pane Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        
        {/* Left Sidebar Pane (~320px) */}
        <div className="lg:col-span-3 space-y-6 bg-[#1e1929] border border-[#5c4037] p-5 rounded-2xl">
          <div>
            <h3 className="text-base font-normal text-[#e9def5]">Active Simulations</h3>
            <p className="text-xs text-[#e6beb2]/70 mt-1 leading-relaxed">
              Quantum routing algorithms actively processing high-density urban grids.
            </p>
          </div>

          {/* Preset Selector Rows */}
          <div className="space-y-3">
            {presets.map((preset) => {
              const isSelected = selectedPreset === preset.id;
              return (
                <button
                  key={preset.id}
                  onClick={() => {
                    setSelectedPreset(preset.id);
                    handleRunOptimization(preset.id);
                  }}
                  className={`w-full text-left p-3.5 rounded-xl border transition flex items-center justify-between ${
                    isSelected
                      ? 'bg-[#221d2d] border-[#ff5719] shadow-md shadow-[#ff5719]/10'
                      : 'bg-[#110b1b] border-[#5c4037]/50 hover:border-[#5c4037]'
                  }`}
                >
                  <div className="flex items-center gap-2.5">
                    <Layers className={`w-4 h-4 ${isSelected ? 'text-[#ff5719]' : 'text-[#e6beb2]/50'}`} />
                    <span className="text-xs font-mono font-medium text-[#e9def5]">{preset.label}</span>
                  </div>
                  <span className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded ${
                    isSelected ? 'bg-[#ff5719]/20 text-[#ffb59e] border border-[#ff5719]/30' : 'bg-[#221d2d] text-[#e6beb2]/40'
                  }`}>
                    {isSelected ? 'ACTIVE' : preset.status}
                  </span>
                </button>
              );
            })}
          </div>

          {/* Fleet Controls */}
          <div className="space-y-3 pt-3 border-t border-[#5c4037]/30">
            <div className="flex items-center justify-between">
              <label className="text-xs font-mono text-[#ffb59e] uppercase">Fleet Size</label>
              <span className="text-xs font-mono font-bold text-[#e9def5] bg-[#110b1b] px-2 py-0.5 rounded border border-[#5c4037]">
                {vehicleCount} Vehicle{vehicleCount > 1 ? 's' : ''}
              </span>
            </div>
            <input
              type="range"
              min={1}
              max={4}
              value={vehicleCount}
              onChange={(e) => setVehicleCount(parseInt(e.target.value))}
              className="w-full accent-[#ffb59e] bg-[#110b1b] h-2 rounded-lg cursor-pointer"
            />
          </div>

          {/* Global Controls */}
          <div className="space-y-3 pt-3 border-t border-[#5c4037]/30">
            <span className="text-[10px] font-mono text-[#e6beb2]/60 uppercase tracking-wider">GLOBAL CONTROLS</span>
            
            <button
              onClick={() => handleRunOptimization()}
              className="w-full btn-ember-gradient py-2.5 px-3 text-xs uppercase font-semibold flex items-center justify-center gap-2"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              <span>⇅ Re-route All Entities</span>
            </button>

            <button
              onClick={() => alert("Emergency Override Initiated: All vehicles holding position.")}
              className="w-full bg-[#110b1b] border border-[#ff4444] text-[#ff6666] hover:bg-[#ff4444]/10 py-2.5 px-3 rounded-lg text-xs font-mono font-semibold flex items-center justify-center gap-2 transition"
            >
              <ShieldAlert className="w-3.5 h-3.5" />
              <span>⚠ Emergency Override</span>
            </button>
          </div>
        </div>

        {/* Right Map Pane */}
        <div className="lg:col-span-9 space-y-4">
          <div className="quantum-glow-card rounded-2xl p-4 relative">
            
            {/* Top Floating Status Chips */}
            <div className="absolute top-7 left-7 z-10 flex items-center gap-2">
              <div className="bg-[#110b1b]/90 border border-[#5c4037] px-3 py-1.5 rounded-lg text-xs font-mono text-[#ffb59e] backdrop-blur-md">
                ● NODE: {optimizationResult?.run_id || 'RUN-4092'}
              </div>
              <div className="bg-[#110b1b]/90 border border-[#5c4037] px-3 py-1.5 rounded-lg text-xs font-mono text-[#9dcaff] backdrop-blur-md">
                LATENCY: {optimizationResult?.telemetry?.execution_ms || 12}ms
              </div>
            </div>

            <RouteMap
              startLocation={startLocation}
              routes={optimizationResult?.routes || []}
              height="550px"
            />

            {/* Bottom-Overlaid KPI Cards */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mt-4">
              
              {/* Card 1: Time Saved */}
              <div className="bg-[#110b1b] border border-[#5c4037] p-4 rounded-xl space-y-2">
                <div className="flex items-center justify-between text-xs font-mono text-[#ffb59e]">
                  <span>Time Saved</span>
                  <Clock className="w-3.5 h-3.5" />
                </div>
                <div className="text-2xl font-light text-[#e9def5]">{metrics.time_saved_hrs || 2.4} hrs</div>
                <div className="w-full bg-[#221d2d] h-1.5 rounded-full overflow-hidden">
                  <div className="bg-[#ff5719] h-full w-[75%]"></div>
                </div>
                <div className="text-[10px] font-mono text-[#e6beb2]/60">+14% vs avg</div>
              </div>

              {/* Card 2: CO2 Reduction */}
              <div className="bg-[#110b1b] border border-[#5c4037] p-4 rounded-xl space-y-2">
                <div className="flex items-center justify-between text-xs font-mono text-[#9dcaff]">
                  <span>CO2 Reduction</span>
                  <Layers className="w-3.5 h-3.5" />
                </div>
                <div className="text-2xl font-light text-[#e9def5]">{metrics.co2_reduction_kg || 18.5} kg</div>
                <div className="w-full bg-[#221d2d] h-1.5 rounded-full overflow-hidden">
                  <div className="bg-[#9dcaff] h-full w-[85%]"></div>
                </div>
                <div className="text-[10px] font-mono text-[#9dcaff]">Optimal Zone</div>
              </div>

              {/* Card 3: Active Vehicles */}
              <div className="bg-[#110b1b] border border-[#5c4037] p-4 rounded-xl space-y-2">
                <div className="flex items-center justify-between text-xs font-mono text-[#d0bcff]">
                  <span>Active Vehicles</span>
                  <Truck className="w-3.5 h-3.5" />
                </div>
                <div className="text-2xl font-light text-[#e9def5]">{vehicleCount} units</div>
                <div className="text-[10px] font-mono text-[#d0bcff] flex items-center gap-1">
                  <span>Mixed Fleet Active</span>
                </div>
              </div>

            </div>

          </div>
        </div>

      </div>

    </div>
  );
};
