function TopNav({ connected }) {
  return (
    <header className="top-nav">
      <div
        className="isro-brand"
        aria-label="Indian Space Research Organisation"
      >
        <img className="isro-logo" src="/isro-logo.jpg" alt="ISRO" />
        <div className="isro-title">
          <strong>Indian Space Research Organisation</strong>
          <span>FSOC Optical Communication</span>
        </div>
      </div>
      <div className="nav-divider" />
      <div className="nav-product">
        <span>Virtual Camera Tracking System</span>
      </div>
      <div className="nav-meta">
        <span
          className={connected ? "online-indicator" : "offline-indicator"}
        />
        <span>{connected ? "System Online" : "System Offline"}</span>
        <span className="nav-time">{new Date().toLocaleDateString()}</span>
        <button
          className="settings-button"
          type="button"
          aria-label="Open settings"
        >
          &#9881;
        </button>
      </div>
    </header>
  );
}

export default TopNav;
