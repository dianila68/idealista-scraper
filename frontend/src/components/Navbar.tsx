import { NavLink } from 'react-router-dom';
import { useMe, useLogout } from '../hooks/useAuth';

export function Navbar() {
  const { data: user } = useMe();
  const logout = useLogout();

  return (
    <nav className="navbar">
      <NavLink to="/" className="navbar-brand">🏠 Idealista Scraper</NavLink>
      <div className="navbar-links">
        {user ? (
          <>
            <NavLink to="/listings" className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}>
              Annunci
            </NavLink>
            <NavLink to="/map" className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}>
              Mappa
            </NavLink>
            <NavLink to="/filters" className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}>
              Filtri
            </NavLink>
            <NavLink to="/profile" className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}>
              Profilo
            </NavLink>
            <button className="btn btn-ghost btn-sm" onClick={logout}>Esci</button>
          </>
        ) : (
          <>
            <NavLink to="/login" className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}>
              Accedi
            </NavLink>
            <NavLink to="/register" className="btn btn-primary btn-sm">
              Registrati
            </NavLink>
          </>
        )}
      </div>
    </nav>
  );
}
