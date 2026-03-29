import { BrowserRouter, Route, Routes } from 'react-router-dom'

import { Layout } from './components/Layout'
import { Archive } from './pages/Archive'
import { BriefingPage } from './pages/Briefing'
import { ClaimResearchPage } from './pages/ClaimResearch'
import { Home } from './pages/Home'
import { SettingsPage } from './pages/Settings'

function App() {
  return (
    <BrowserRouter>
      <Layout>
        <Routes>
          <Route element={<Home />} path="/" />
          <Route element={<Archive />} path="/archive" />
          <Route element={<BriefingPage />} path="/briefing/:date" />
          <Route element={<ClaimResearchPage />} path="/claim/:date/:claimId" />
          <Route element={<SettingsPage />} path="/settings" />
        </Routes>
      </Layout>
    </BrowserRouter>
  )
}

export default App
