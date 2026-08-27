import random
import numpy as np
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from inventory.models import Equipment
from telemetry.models import SensorReading


class Command(BaseCommand):
    help = (
        "Seeds 5,000 time-series sensor readings with PROGRESSIVE degradation episodes "
        "for Experiment B (evaluating short-term predictive anomaly forecasting on gradual drift)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--samples",
            type=int,
            default=5000,
            help="Total number of sequential telemetry records to generate (default: 5000).",
        )
        parser.add_argument(
            "--episodes",
            type=int,
            default=18,
            help="Number of progressive degradation ramp episodes to inject (default: 18).",
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("=" * 80))
        self.stdout.write(self.style.NOTICE(" SEEDING PROGRESSIVE DEGRADATION TELEMETRY (EXPERIMENT B)"))
        self.stdout.write(self.style.NOTICE("=" * 80))

        eq, created = Equipment.objects.get_or_create(
            mac_address="SIMULATED-PROGRESSIVE-01",
            defaults={"name": "Progressive Test Inverter", "equipment_type": "INVERTER"},
        )

        SensorReading.objects.filter(equipment=eq).delete()
        self.stdout.write("Existing progressive simulated data cleared.")

        total_samples = options["samples"]
        num_episodes = options["episodes"]
        base_time = timezone.now() - timedelta(minutes=total_samples * 5)

        # Baseline continuous arrays with realistic diurnal/noise variations
        np.random.seed(42)
        random.seed(42)

        # Time indices (1 step = 5 minutes)
        t_indices = np.arange(total_samples)
        
        # Diurnal thermal variation (mild day/night oscillation: +/- 3 deg C)
        diurnal_temp = 28.0 + 3.0 * np.sin(2 * np.pi * t_indices / (24 * 12)) + np.random.normal(0, 0.4, total_samples)
        base_volt = 220.0 + np.random.normal(0, 0.5, total_samples)
        base_vib_x = 0.04 + np.abs(np.random.normal(0, 0.015, total_samples))
        base_vib_y = 0.04 + np.abs(np.random.normal(0, 0.015, total_samples))
        base_vib_z = 0.05 + np.abs(np.random.normal(0, 0.015, total_samples))

        temp_arr = np.copy(diurnal_temp)
        volt_arr = np.copy(base_volt)
        vx_arr = np.copy(base_vib_x)
        vy_arr = np.copy(base_vib_y)
        vz_arr = np.copy(base_vib_z)

        # Distribute progressive degradation episodes with minimum spacing
        min_spacing = 160
        episode_starts = []
        curr_pos = 60
        for _ in range(num_episodes):
            pos = curr_pos + random.randint(30, 80)
            if pos + 35 < total_samples:
                episode_starts.append(pos)
                curr_pos = pos + min_spacing

        self.stdout.write(f"Injecting {len(episode_starts)} multi-step progressive degradation episodes...")

        for ep_idx, start_pos in enumerate(episode_starts):
            ep_type = ep_idx % 3  # Rotate through thermal, vibration, and voltage
            ramp_len = random.randint(12, 20)  # 12 to 20 steps of gradual precursor drift
            hold_len = random.randint(2, 4)    # Peak anomaly duration
            decay_len = random.randint(6, 10)  # Recovery after repair

            if ep_type == 0:
                # 1. Progressive Thermal Runaway (e.g. cooling fan dust accumulation / bearing friction)
                target_peak = random.uniform(46.0, 56.0)
                start_temp = temp_arr[start_pos]
                
                # Gradual linear/exponential precursor ramp
                for k in range(ramp_len):
                    idx = start_pos + k
                    if idx < total_samples:
                        progress = (k + 1) / ramp_len
                        temp_arr[idx] = start_temp + (target_peak - start_temp) * (progress ** 1.3) + np.random.normal(0, 0.3)
                        # Slight thermal coupling to vibration
                        vx_arr[idx] += 0.03 * progress

                # Peak hold
                for k in range(hold_len):
                    idx = start_pos + ramp_len + k
                    if idx < total_samples:
                        temp_arr[idx] = target_peak + np.random.normal(0, 0.4)

                # Post-intervention recovery to baseline
                for k in range(decay_len):
                    idx = start_pos + ramp_len + hold_len + k
                    if idx < total_samples:
                        decay_prog = 1.0 - ((k + 1) / decay_len)
                        temp_arr[idx] = diurnal_temp[idx] + (target_peak - diurnal_temp[idx]) * (decay_prog ** 2)

            elif ep_type == 1:
                # 2. Progressive Mechanical Bearing Wear / Rotor Imbalance
                target_peak = random.uniform(0.65, 1.20)
                start_vx = vx_arr[start_pos]

                for k in range(ramp_len):
                    idx = start_pos + k
                    if idx < total_samples:
                        progress = (k + 1) / ramp_len
                        added_vib = (target_peak - start_vx) * (progress ** 1.2) + np.random.normal(0, 0.01)
                        vx_arr[idx] = start_vx + added_vib
                        vy_arr[idx] = base_vib_y[idx] + added_vib * 0.85
                        vz_arr[idx] = base_vib_z[idx] + added_vib * 0.90
                        temp_arr[idx] += 4.0 * progress  # Friction heat buildup

                for k in range(hold_len):
                    idx = start_pos + ramp_len + k
                    if idx < total_samples:
                        vx_arr[idx] = target_peak + np.random.normal(0, 0.02)
                        vy_arr[idx] = target_peak * 0.85 + np.random.normal(0, 0.02)
                        vz_arr[idx] = target_peak * 0.90 + np.random.normal(0, 0.02)

                for k in range(decay_len):
                    idx = start_pos + ramp_len + hold_len + k
                    if idx < total_samples:
                        decay_prog = 1.0 - ((k + 1) / decay_len)
                        vx_arr[idx] = base_vib_x[idx] + (target_peak - base_vib_x[idx]) * (decay_prog ** 2)
                        vy_arr[idx] = base_vib_y[idx] + (target_peak * 0.85 - base_vib_y[idx]) * (decay_prog ** 2)
                        vz_arr[idx] = base_vib_z[idx] + (target_peak * 0.90 - base_vib_z[idx]) * (decay_prog ** 2)

            else:
                # 3. Progressive Overvoltage / Grid Surge
                target_peak = random.uniform(242.0, 258.0)
                start_volt = volt_arr[start_pos]

                for k in range(ramp_len):
                    idx = start_pos + k
                    if idx < total_samples:
                        progress = (k + 1) / ramp_len
                        volt_arr[idx] = start_volt + (target_peak - start_volt) * progress + np.random.normal(0, 0.4)

                for k in range(hold_len):
                    idx = start_pos + ramp_len + k
                    if idx < total_samples:
                        volt_arr[idx] = target_peak + np.random.normal(0, 0.4)

                for k in range(decay_len):
                    idx = start_pos + ramp_len + hold_len + k
                    if idx < total_samples:
                        decay_prog = 1.0 - ((k + 1) / decay_len)
                        volt_arr[idx] = base_volt[idx] + (target_peak - base_volt[idx]) * decay_prog

        # Assemble and persist bulk records
        readings_to_create = []
        for i in range(total_samples):
            r_time = base_time + timedelta(minutes=i * 5)
            readings_to_create.append(
                SensorReading(
                    equipment=eq,
                    temperature=round(float(temp_arr[i]), 2),
                    voltage=round(float(volt_arr[i]), 2),
                    vib_x=round(float(vx_arr[i]), 4),
                    vib_y=round(float(vy_arr[i]), 4),
                    vib_z=round(float(vz_arr[i]), 4),
                    timestamp=r_time,
                )
            )

        SensorReading.objects.bulk_create(readings_to_create, batch_size=1000)
        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully seeded {total_samples} progressive telemetry records across {len(episode_starts)} ramp episodes!"
            )
        )
