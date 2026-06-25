from django.db import models
from django.utils.translation import gettext_lazy as _

from inventory.models import Equipment


class HealthStatus(models.Model):
    """
    This is the database table that stores the results from our Machine Learning model.
    Every time the ML pipeline runs, it creates a new row here.
    """
    
    # We define 3 specific statuses so that we only ever use these exact words.
    class Status(models.TextChoices):
        NORMAL = "NORMAL", _("Normal")
        WARNING = "WARNING", _("Warning")
        CRITICAL = "CRITICAL", _("Critical")

    # This connects the HealthStatus to a specific piece of Equipment.
    # 'CASCADE' means if the equipment is deleted, all its health history is also deleted.
    equipment = models.ForeignKey(
        Equipment,
        on_delete=models.CASCADE,
        related_name="health_assessments",
    )

    # The raw mathematical output from our Scikit-Learn Isolation Forest.
    # We save this so we can plot it on charts later.
    anomaly_score = models.FloatField(_("Anomaly Score"))

    # The human-readable status (NORMAL/WARNING/CRITICAL).
    # This is what the frontend uses to decide which color LED to turn on.
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.NORMAL,
        db_index=True, # Makes searching by status much faster
    )

    # Automatically records the exact date and time the prediction was made.
    prediction_timestamp = models.DateTimeField(auto_now_add=True)

    # --- System Performance Metrics (Section 3.5) ---
    processing_latency_ms = models.FloatField(_("Processing Latency (ms)"), null=True, blank=True)
    cpu_load_percent = models.FloatField(_("CPU Load (%)"), null=True, blank=True)
    ram_allocation_mb = models.FloatField(_("RAM Allocation (MB)"), null=True, blank=True)

    class Meta:
        verbose_name = _("Health Status")
        verbose_name_plural = _("Health Statuses")
        # When we ask the database for health statuses, give us the newest ones first.
        ordering = ["-prediction_timestamp"]

    def __str__(self):
        # How this object appears in the Django Admin panel
        return f"{self.equipment.name} - {self.status}"
