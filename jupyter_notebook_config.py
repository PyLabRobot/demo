c.NotebookApp.tornado_settings = {
  'headers': {
    'Content-Security-Policy': "frame-ancestors http://127.0.0.1:5000 'self'"
  },
}

# trick notebook into thinking flask is the jupyter server
c.NotebookApp.base_url = '/notebook/'

# with https:
# Content-Security-Policy “default-src https: ‘unsafe-inline’; connect-src https: wss:”
# https://jupyter-notebook.readthedocs.io/en/stable/public_server.html#content-security-policy-csp

c.NotebookApp.open_browser = False
c.GatewayClient.url = "http://localhost:5000/notebook" # flask

#c.NotebookApp.cookie_options = {"SameSite": "None", "Secure": False}
