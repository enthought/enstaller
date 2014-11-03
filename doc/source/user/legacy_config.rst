Configuration
=============

When used from the command line, `enpkg` looks for the file
`.enstaller4rc` in the following locations:

* `sys.prefix`
* `sys.real_prefix` (if under a virtual environment)
* in `~`

The first found file is considered.

Examples
--------

A simple example is as follows::

    # To use an http proxy
    proxy = 'http://john:doe@acme.com:3128'
    
    # If auth has been set up by `--userpass`
    EPD_auth = 'ZGF2aWRjQGVudGhvdWdodC5jb206Xl5kNHYxZGMhIw=='

    # To disable SSL verification (insecure)
    verify_ssl = False

To use custom legacy repositories::

    # Disable canopy mode
    use_webservice = False
    
    # Set up local repositories
    IndexedRepos = [
        'http://www.enthought.com/repo/GPL/eggs/{PLATFORM}/',
        'http://www.enthought.com/repo/free/{PLATFORM}/',
        'http://www.enthought.com/repo/commercial/{PLATFORM}/',
    ]

To use API token against a `brood` store::

    store_url = "brood+https://brood.acme.com"
    api_token = "<api_token>"
