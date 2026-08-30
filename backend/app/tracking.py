from __future__ import annotations

from dataclasses import dataclass
from math import hypot


@dataclass
class Track:
    track_id: str
    center_x: float
    center_y: float
    last_frame: int
    missed: int = 0


class CentroidTracker:
    """Small deterministic tracker for detector outputs in frame order.

    The current MediaPipe Pose detector emits one person; keeping this tracker
    separate makes the persisted Worker ID stable and gives future detectors a
    multi-person assignment boundary without changing the result contract.
    """

    def __init__(self, max_distance: float = 160.0, max_missed: int = 10, single_track_grace: bool = False):
        self.max_distance = max_distance
        self.max_missed = max_missed
        self.single_track_grace = single_track_grace
        self.tracks: list[Track] = []
        self.next_id = 1

    def update(self, centers: list[tuple[float, float]], frame_index: int) -> list[str]:
        available = set(range(len(self.tracks)))
        assigned: list[str] = []
        for x, y in centers:
            choice = min(available, key=lambda i: hypot(self.tracks[i].center_x - x, self.tracks[i].center_y - y), default=None)
            distance = hypot(self.tracks[choice].center_x - x, self.tracks[choice].center_y - y) if choice is not None else None
            can_grace_match = self.single_track_grace and len(centers) == 1 and len(self.tracks) == 1 and choice is not None
            if choice is not None and (distance <= self.max_distance or can_grace_match):
                track = self.tracks[choice]
                available.remove(choice)
                track.center_x, track.center_y, track.last_frame, track.missed = x, y, frame_index, 0
            else:
                track = Track(f"person-{self.next_id}", x, y, frame_index)
                self.next_id += 1
                self.tracks.append(track)
            assigned.append(track.track_id)
        for index in available:
            self.tracks[index].missed += 1
        self.tracks = [track for track in self.tracks if track.missed <= self.max_missed]
        return assigned
