from rest_framework import viewsets, filters

from inventory.models import Equipment
from inventory.models import MaintenanceLog

from .serializers import EquipmentSerializer
from .serializers import MaintenanceLogSerializer


class EquipmentViewSet(viewsets.ModelViewSet):
    queryset = Equipment.objects.all().order_by("id")
    serializer_class = EquipmentSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ["name", "mac_address", "equipement_type", "location_notes"]


class MaintenanceLogViewSet(viewsets.ModelViewSet):
    queryset = MaintenanceLog.objects.all()
    serializer_class = MaintenanceLogSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        equipment = self.request.query_params.get("equipment")
        start_date = self.request.query_params.get("start_date")
        end_date = self.request.query_params.get("end_date")
        
        if equipment:
            queryset = queryset.filter(equipment_id=equipment)
        if start_date:
            queryset = queryset.filter(timestamp__gte=start_date)
        if end_date:
            queryset = queryset.filter(timestamp__lte=end_date)
            
        return queryset.order_by("-timestamp")

    def perform_create(self, serializer):
        # Automatically set the author to the logged-in user if available
        serializer.save(
            author=self.request.user if self.request.user.is_authenticated else None,
        )
