from django.conf import settings


def static_version(request):
    return {"v": settings.STATIC_VERSION}
