from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.renderers import JSONRenderer
from rest_framework_extensions.routers import ExtendedDefaultRouter


# Create your views here.
class MaintenanceViewSet(viewsets.GenericViewSet):
    """Maintenance"""
    renderer_classes = [JSONRenderer]

    @action(methods=["GET", "POST"], detail=False)
    def check_health(self, request):
        return Response(dict(success=True, message='OK'))


MaintenanceRouter = ExtendedDefaultRouter()
# Maintenance subsystem
MaintenanceRouter.register(r'maintenance', MaintenanceViewSet, 'maintenance')
