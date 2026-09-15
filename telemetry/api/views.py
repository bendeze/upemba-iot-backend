import uuid
from django.db import models
from rest_framework import viewsets

from telemetry.models import HealthStatus
from telemetry.models import SensorReading

from .serializers import HealthStatusSerializer
from .serializers import SensorReadingSerializer


class HealthStatusViewSet(viewsets.ReadOnlyModelViewSet):
    """
    This class handles the API endpoint that the Next.js Frontend calls to get Health Statuses.
    It is 'ReadOnly' because the frontend is never allowed to CREATE a health status.
    Health statuses are only created automatically by our Machine Learning background task.
    """
    
    queryset = HealthStatus.objects.all().order_by("-prediction_timestamp")
    serializer_class = HealthStatusSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        
        equipment = self.request.query_params.get("equipment")
        start_date = self.request.query_params.get("start_date")
        end_date = self.request.query_params.get("end_date")

        if equipment:
            try:
                val = uuid.UUID(str(equipment))
                queryset = queryset.filter(equipment_id=val)
            except (ValueError, AttributeError):
                # Fallback matching by MAC address or equipment name, or empty if invalid
                queryset = queryset.filter(
                    models.Q(equipment__mac_address=equipment) | models.Q(equipment__name__iexact=equipment)
                )
            
        if start_date:
            queryset = queryset.filter(prediction_timestamp__gte=start_date)
            
        if end_date:
            queryset = queryset.filter(prediction_timestamp__lte=end_date)
            
        return queryset


class SensorReadingViewSet(viewsets.ReadOnlyModelViewSet):
    """
    This class handles the API endpoint for raw Sensor Readings (Temperature, Voltage, etc).
    """
    queryset = SensorReading.objects.all().order_by("-timestamp")
    serializer_class = SensorReadingSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        equipment = self.request.query_params.get("equipment")
        start_date = self.request.query_params.get("start_date")
        end_date = self.request.query_params.get("end_date")

        if equipment:
            try:
                val = uuid.UUID(str(equipment))
                queryset = queryset.filter(equipment_id=val)
            except (ValueError, AttributeError):
                queryset = queryset.filter(
                    models.Q(equipment__mac_address=equipment) | models.Q(equipment__name__iexact=equipment)
                )

        if start_date:
            queryset = queryset.filter(timestamp__gte=start_date)
            
        if end_date:
            queryset = queryset.filter(timestamp__lte=end_date)

        return queryset
