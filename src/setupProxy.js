const { createProxyMiddleware } = require('http-proxy-middleware');

// The Flask port to send /api and /ws to: 8000, or API_PORT to run a second stack beside the first.
const apiPort = process.env.API_PORT || 8000;

module.exports = function(app) {
  app.use(
    'api',
    createProxyMiddleware({
      target: `http://127.0.0.1:${apiPort}`,
      changeOrigin: true,
    })
  );
  app.use(
    'ws',
    createProxyMiddleware({
      target: `ws://127.0.0.1:${apiPort}`,
      changeOrigin: true,
      ws: true,
    })
  );
};