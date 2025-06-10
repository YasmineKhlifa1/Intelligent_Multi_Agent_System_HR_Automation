
import React from 'react';
import './SchedulerF.css';
import  Scheduler_Design from './Scheduler_DDDF'; 

function App() {
  return (
    <div className="app-container">
      <header className="main-content">
        {/* ✅ Inject your Chat Interface here         <ChatInterface/> */}
        <Scheduler_Design/>
      </header>
    </div>
  );
}
export default App;
