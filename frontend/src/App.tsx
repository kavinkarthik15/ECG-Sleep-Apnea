import { Navigate, Route, Routes } from 'react-router-dom'
import { AppLayout } from './components/layout/AppLayout'
import { AboutPage } from './pages/AboutPage'
import { AnalyzePage } from './pages/AnalyzePage'
import { HomePage } from './pages/HomePage'
import { ResultsPage } from './pages/ResultsPage'

function App() {
  return <Routes><Route element={<AppLayout />}><Route path="/" element={<HomePage />} /><Route path="/analyze" element={<AnalyzePage />} /><Route path="/results" element={<ResultsPage />} /><Route path="/about" element={<AboutPage />} /><Route path="*" element={<Navigate to="/" replace />} /></Route></Routes>
}

export default App
