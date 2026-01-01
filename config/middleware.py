# core/middleware.py
from django.utils import translation

class ForcePersianMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Only force if there is no session/cookie/language already set
        if not request.COOKIES.get('django_language') and not request.session.get('django_language'):
            translation.activate('fa')
            request.LANGUAGE_CODE = 'fa'
        response = self.get_response(request)
        response.headers.setdefault("Content-Language", 'fa')
        return response
