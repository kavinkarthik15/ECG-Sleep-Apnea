import { useEffect, useState } from 'react'
import { Activity, BookOpen, CircleHelp, Home, Menu, X } from 'lucide-react'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { checkHealth } from '../../services/api'

export function AppLayout() {
  const [online, setOnline] = useState(false)
  const [menuOpen, setMenuOpen] = useState(false)
  const navigate = useNavigate()

  useEffect(() => { checkHealth().then((data) => setOnline(data.status === 'healthy' && data.model_loaded)).catch(() => setOnline(false)) }, [])
  const links = [{ to: '/', label: 'Overview', icon: Home }, { to: '/analyze', label: 'Analyze ECG', icon: Activity }, { to: '/about', label: 'About', icon: BookOpen }]

  return <div className="app-shell">
    <header className="site-header">
      <button className="brand" onClick={() => navigate('/')} aria-label="Go to overview"><span className="brand-mark"><Activity size={20} /></span><span><b>ECG</b> Apnea Screening</span></button>
      <nav className={`main-nav ${menuOpen ? 'is-open' : ''}`} aria-label="Primary navigation">{links.map(({ to, label, icon: Icon }) => <NavLink key={to} to={to} end={to === '/'} onClick={() => setMenuOpen(false)}><Icon size={16} />{label}</NavLink>)}</nav>
      <div className="header-actions"><span className={`system-status ${online ? 'online' : 'offline'}`}><span className="status-dot" />{online ? 'System online' : 'Service offline'}</span><button className="mobile-menu icon-button" onClick={() => setMenuOpen(!menuOpen)} aria-label="Toggle navigation">{menuOpen ? <X size={20} /> : <Menu size={20} />}</button></div>
    </header>
    <main><Outlet /></main>
    <footer className="site-footer"><span><Activity size={15} /> ECG-Based Sleep Apnea Screening System</span><span>Academic research prototype</span><a href="/about"><CircleHelp size={14} /> About this project</a></footer>
  </div>
}