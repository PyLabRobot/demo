c.NotebookApp.tornado_settings = {
  'headers': {
    'Content-Security-Policy': "frame-ancestors http://127.0.0.1:5001 127.0.0.1:8888 'self'"
  },
}

c.NotebookApp.allow_origin = '*'

# trick notebook into thinking flask is the jupyter server
c.NotebookApp.base_url = '/notebook/'

c.NotebookApp.custom_display_url = 'http://localhost:5001/'

# with https:
# Content-Security-Policy “default-src https: ‘unsafe-inline’; connect-src https: wss:”
# https://jupyter-notebook.readthedocs.io/en/stable/public_server.html#content-security-policy-csp

c.NotebookApp.open_browser = False

c.NotebookApp.token=''
c.NotebookApp.password=''

#c.NotebookApp.cookie_options = {"SameSite": "None", "Secure": False}


# culling notebooks
c.MappingKernelManager.cull_connected = False

# Shut down the server after N seconds with no kernels or terminals running and
#  no activity. This can be used together with culling idle kernels
#  (MappingKernelManager.cull_idle_timeout) to shutdown the notebook server when
#  it's not in use. This is not precisely timed: it may shut down up to a minute
#  later. 0 (the default) disables this automatic shutdown.
c.NotebookApp.shutdown_no_activity_timeout = 5*60 #1 after kernel has shut down, we don't care about the server anymore

# Whether to consider culling kernels which are busy. Only effective if
#  cull_idle_timeout > 0.
c.MappingKernelManager.cull_busy = True

## Timeout (in seconds) after which a kernel is considered idle and ready to be
#  culled. Values of 0 or lower disable culling. Very short timeouts may result
#  in kernels being culled for users with poor network connections.
c.MappingKernelManager.cull_idle_timeout = 5 * 60

## The interval (in seconds) on which to check for idle kernels exceeding the
#  cull timeout value.
c.MappingKernelManager.cull_interval = 1
