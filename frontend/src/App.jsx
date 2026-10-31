import {BrowserRouter as Router, Routes, Route} from 'react-router-dom';
import Landing from './pages/Landing';
import Workspace from './pages/Workspace';
import CsvPage  from './pages/File';

function App() {
  return (
    <Router>
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/workspace" element={<Workspace />} />
        <Route path="/csv/:id" element={<CsvPage  />} />
      </Routes>

    </Router>
  );
}

export default App
