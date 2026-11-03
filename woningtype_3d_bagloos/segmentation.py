"""Spatial DSM roof zones; deliberately not a LoD2/3DBAG reconstruction."""
from math import floor


def quantile(values, fraction):
    ordered = sorted(values)
    return ordered[int((len(ordered) - 1) * fraction)]


class RoofZones:
    """Separate substantial upper roof zones from lower connecting roofs.

    A regular, footprint-clipped grid preserves where heights occur. Connected
    components discard isolated chimneys/pixels. No location or BAG ID is used.
    Thresholds are relative NAP heights, so terrain altitude cancels out.
    """

    def __init__(self, samples, origin, spacing, expected):
        self.samples = samples
        self.origin = origin
        self.spacing = spacing
        self.main = set()
        self.level = None
        self.reliable = False
        if len(samples) < 24 or len(samples) < .8 * expected:
            return
        values = list(samples.values())
        self.level = quantile(values, .8)
        lower = quantile(values, .1)
        # Sloping main roofs retain their broad upper surfaces. Flat buildings
        # need no artificial height step. This is a roof zone, not a ridge pixel.
        self.threshold = (self.level - 1.75 if quantile(values, .9) - lower > 1.5
                          else lower - .5)
        remaining = {p for p, h in samples.items() if h >= self.threshold}
        minimum = max(6.0, len(samples) * spacing * spacing * .04)
        while remaining:
            seed = remaining.pop()
            component, queue = {seed}, [seed]
            while queue:
                x, y = queue.pop()
                for p in ((x-1, y), (x+1, y), (x, y-1), (x, y+1)):
                    if (p in remaining and
                            abs(samples[p] - samples[x, y]) <= 1.25):
                        remaining.remove(p)
                        component.add(p)
                        queue.append(p)
            if len(component) * spacing * spacing >= minimum:
                self.main.update(component)
        self.reliable = len(self.main) >= max(12, len(samples) * .12)

    def at(self, x, y):
        """True=main zone, False=lower zone, None=no trustworthy sample."""
        if not self.reliable:
            return None
        p = (floor((x-self.origin[0])/self.spacing),
             floor((y-self.origin[1])/self.spacing))
        if p not in self.samples:
            return None
        if p in self.main:
            return True
        # High discarded components may be trees/chimneys; not low roofs.
        return False if self.samples[p] < self.threshold else None
