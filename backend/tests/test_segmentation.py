from pathlib import Path
import pytest
from app.cv.segmentation import Region, segment_regions, regions_to_structure_ids

SPINE_STRUCTURES = str(Path(__file__).resolve().parents[2] / "content" / "spine" / "structures.yaml")


def test_unknown_or_unlabelled_regions_map_to_none():
    regions = [Region((0, 0, 10, 10), 100, "Lumbar region"),
               Region((0, 0, 5, 5), 25, "Flux capacitor"),
               Region((0, 0, 5, 5), 25, None)]
    mapped = [sid for _, sid in regions_to_structure_ids(regions, SPINE_STRUCTURES)]
    assert mapped == ["spine.lumbar_region", None, None]


@pytest.mark.integration
def test_regions_map_only_known_ids(spine_diagram_bytes):
    pytest.importorskip("ultralytics")
    regions = segment_regions(spine_diagram_bytes)
    assert all(r.mask_area > 0 and len(r.bbox) == 4 for r in regions)
    mapped = regions_to_structure_ids(regions, SPINE_STRUCTURES)
    assert all(sid is None or sid.startswith("spine.") for _, sid in mapped)
