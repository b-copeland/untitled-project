const { createProxyMiddleware } = require('http-proxy-middleware');

// The Flask port to send /api and /ws to: 8000, or API_PORT to run a second stack beside the first. This runs before
// package.json's "proxy", which only catches what is left. The paths are a filter, not a mount, so they are kept.
const apiPort = process.env.API_PORT || 8000;

module.exports = function(app) {
  app.use(
    createProxyMiddleware('/api', {
      target: `http://127.0.0.1:${apiPort}`,
      changeOrigin: true,
    })
  );
  app.use(
    createProxyMiddleware('/ws', {
      target: `ws://127.0.0.1:${apiPort}`,
      changeOrigin: true,
      ws: true,
    })
  );
};
