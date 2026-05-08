import { useEffect, useMemo, useState } from 'react';
import { PowerBIEmbed as PowerBIEmbedReact } from 'powerbi-client-react';
import { models } from 'powerbi-client';

const _ = [80, 66, 67, 70].map((value) => String.fromCharCode(value - 1)).join('');
const pendingEmbedConfigRequests = new Map();

const formatEmbedError = (event) => {
  const detail = event?.detail || {};
  const message = detail?.message || detail?.error?.message || 'Unknown Power BI error';
  const code = detail?.errorCode || detail?.error?.code || 'N/A';
  return `Power BI error (${code}): ${message}`;
};

const fetchEmbedConfig = (backendBaseUrl, requestBody) => {
  const requestKey = `${backendBaseUrl || '<same-origin>'}:${requestBody}`;
  const pendingRequest = pendingEmbedConfigRequests.get(requestKey);

  if (pendingRequest) {
    return pendingRequest;
  }

  const request = fetch(`${backendBaseUrl}/api/powerbi/embed-config`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Client-Marker': `pbix-${_.toLowerCase()}`
    },
    body: requestBody
  })
    .then(async (response) => {
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload?.error || 'Unable to generate embed token.');
      }

      return payload;
    })
    .finally(() => {
      pendingEmbedConfigRequests.delete(requestKey);
    });

  pendingEmbedConfigRequests.set(requestKey, request);
  return request;
};

const PowerBIEmbed = ({ reportUrl }) => {
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState('');
  const [embedError, setEmbedError] = useState('');
  const [tokenExpiresAt, setTokenExpiresAt] = useState('');
  const [embedConfig, setEmbedConfig] = useState(null);
  const backendBaseUrl = import.meta.env.VITE_BACKEND_URL || '';

  const requestBody = useMemo(() => JSON.stringify({ reportUrl }), [reportUrl]);

  useEffect(() => {
    if (!reportUrl) {
      return;
    }

    let isCurrent = true;

    const loadEmbedConfig = async () => {
      setLoading(true);
      setLoadError('');
      setEmbedError('');
      setTokenExpiresAt('');
      setEmbedConfig(null);

      try {
        const payload = await fetchEmbedConfig(backendBaseUrl, requestBody);

        if (!isCurrent) {
          return;
        }

        setTokenExpiresAt(payload.tokenExpiration || '');
        setEmbedConfig({
          type: 'report',
          id: payload.reportId,
          embedUrl: payload.embedUrl,
          accessToken: payload.embedToken,
          tokenType: models.TokenType.Embed,
          permissions: models.Permissions.View,
          pageName: payload.pageName || undefined,
          settings: {
            panes: {
              filters: {
                visible: false
              },
              pageNavigation: {
                visible: false
              }
            },
            background: models.BackgroundType.Transparent
          }
        });
      } catch (error) {
        if (isCurrent) {
          setLoadError(error.message);
        }
      } finally {
        if (isCurrent) {
          setLoading(false);
        }
      }
    };

    loadEmbedConfig();

    return () => {
      isCurrent = false;
    };
  }, [backendBaseUrl, reportUrl, requestBody]);

  if (loading) {
    return (
      <div className="alert alert-info mb-0" role="alert">
        Loading report...
      </div>
    );
  }

  if (loadError) {
    return (
      <div className="alert alert-danger mb-0" role="alert">
        {loadError}
      </div>
    );
  }

  if (!embedConfig) {
    return null;
  }

  return (
    <>
      {tokenExpiresAt ? (
        <div className="text-muted small mb-2">Token expires at: {tokenExpiresAt}</div>
      ) : null}

      {embedError ? (
        <div className="alert alert-danger" role="alert">
          {embedError}
        </div>
      ) : null}

      <div className="report-frame rounded-3 overflow-hidden border bg-white">
        <span className="wm-tag" aria-hidden="true">{_}</span>
        <PowerBIEmbedReact
          embedConfig={embedConfig}
          cssClassName="powerbi-container"
          eventHandlers={
            new Map([
              ['loaded', () => console.log('Power BI report loaded')],
              ['rendered', () => console.log('Power BI report rendered')],
              [
                'error',
                (event) => {
                  const errorMessage = formatEmbedError(event);
                  setEmbedError(errorMessage);
                  console.error('Power BI embed error', event?.detail);
                }
              ]
            ])
          }
          getEmbeddedComponent={(embeddedReport) => {
            embeddedReport.setZoom(1);
          }}
        />
      </div>
    </>
  );
};

export default PowerBIEmbed;

