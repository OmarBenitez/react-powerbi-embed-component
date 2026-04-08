import { useState } from 'react';
import PowerBIEmbed from './components/PowerBIEmbed';

const App = () => {
  const [reportUrl, setReportUrl] = useState(import.meta.env.VITE_DEFAULT_REPORT_URL || '');
  const [submittedUrl, setSubmittedUrl] = useState('');

  const onSubmit = (event) => {
    event.preventDefault();
    setSubmittedUrl(reportUrl.trim());
  };

  return (
    <main className="app-shell bg-light">
      <section className="container-fluid h-100 px-3 px-md-4 py-3 py-md-4">
        <div className="flat-shell h-100 p-3 p-md-4">
          <header className="mb-3">
            <h1 className="h3 fw-semibold mb-2">Power BI Report</h1>
            <p className="text-muted mb-0 small">
              Paste a full report URL. The backend will extract workspace, report, and page.
            </p>
          </header>

          <form className="row g-2 mb-3" onSubmit={onSubmit}>
            <div className="col-12 col-md-10">
              <input
                type="url"
                className="form-control"
                placeholder="https://app.powerbi.com/groups/.../reports/..."
                value={reportUrl}
                onChange={(event) => setReportUrl(event.target.value)}
              />
            </div>
            <div className="col-12 col-md-2 d-grid">
              <button type="submit" className="btn btn-dark">Load report</button>
            </div>
          </form>

          {submittedUrl ? (
            <PowerBIEmbed reportUrl={submittedUrl} />
          ) : (
            <div className="alert alert-secondary mb-0" role="alert">
              Enter a report URL and click <strong>Load report</strong>.
            </div>
          )}
        </div>
      </section>
    </main>
  );
};

export default App;
