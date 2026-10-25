"""Deterministic workspace rotation and pop-up timing, independent of Pygame."""
NAMES = ('Security overview', 'PHP watch', 'Exploited in the wild', 'Observatory')


class WorkspaceCycle:
    def __init__(self, duration=32, initial=0):
        self.duration = max(20, float(duration))
        self.index = initial % len(NAMES)
        self.since = 0.
        self.automatic = True

    def tick(self, now):
        if self.automatic and now-self.since >= self.duration:
            steps = int((now-self.since)//self.duration)
            self.index = (self.index+steps) % len(NAMES)
            self.since += steps*self.duration
        return self.index, max(0., now-self.since)

    def select(self, index, now):
        self.index = index % len(NAMES)
        self.since = now

    def step(self, delta, now):
        self.select(self.index+delta, now)


def window_progress(age, delay=0., duration=.65):
    return max(0., min(1., (age-delay)/duration))


def terminal_progress(age, opens=7., closes=23.):
    if age < opens or age >= closes:
        return 0.
    return min(window_progress(age, opens), max(0., (closes-age)/.65))
