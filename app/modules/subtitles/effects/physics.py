from dataclasses import dataclass


@dataclass(frozen=True)
class KineticSegment:
    start: int
    end: int
    from_y: float
    to_y: float


class KineticPhysicsEngine:
    """Builds a compact gravity-and-bounce trajectory for ASS dialogues."""

    minimum_duration_ms = 250

    def gravity_drop(self, start, end, base_y, drop_height_px, bounce_elasticity):
        duration = end - start
        if duration < self.minimum_duration_ms:
            return ()

        impact = start + round(duration * 0.70)
        midpoint = start + round(duration * 0.35)
        rebound = start + round(duration * 0.85)
        start_y = base_y - drop_height_px
        # The midpoint follows the quadratic fall distance at half the fall time.
        midpoint_y = start_y + drop_height_px * 0.25
        rebound_y = base_y - drop_height_px * bounce_elasticity
        points = (
            (start, start_y),
            (midpoint, midpoint_y),
            (impact, base_y),
            (rebound, rebound_y),
            (end, base_y),
        )
        return tuple(
            KineticSegment(segment_start, segment_end, from_y, to_y)
            for (segment_start, from_y), (segment_end, to_y) in zip(
                points,
                points[1:],
            )
            if segment_end > segment_start
        )
