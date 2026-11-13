class NoCacheStaticMiddleware:
    """Tell the browser to re-check JS/CSS on every load, so it never runs
    an old cached copy after the code changes (local dev tool, so speed is fine)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.path.startswith("/static/") or request.path == "/" or request.path.startswith("/runs/"):
            response["Cache-Control"] = "no-cache, must-revalidate"
        return response
